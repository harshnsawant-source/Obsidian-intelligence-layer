import time
from core.providers.registry import build_registry
from core.complexity import score_complexity, classify, LOW, HIGH
from core.escalation import record_escalation
from core.trace import TraceLog
from core.log import get_logger


log = get_logger("router")

CANNED_FALLBACK = (
    "[orchestrator] All providers are currently unavailable. "
    "Please retry shortly."
)


def _is_timeout_error(error):
    # True if the exception (or any base) is a timeout. Checked by class name so
    # the router stays decoupled from the HTTP library — covers requests'
    # ReadTimeout / ConnectTimeout / Timeout and any similarly named error.
    return any("Timeout" in cls.__name__ for cls in type(error).__mro__)


class TelemetryAccumulator:
    def __init__(self):
        self.active = False
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.latency = 0.0

    def reset(self):
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.latency = 0.0

    def record_call(self, prompt, completion, latency_s):
        if not self.active:
            return
        self.calls += 1
        p_tokens = int(len(prompt.split()) * 1.33) if prompt else 0
        c_tokens = int(len(completion.split()) * 1.33) if completion else 0
        self.prompt_tokens += p_tokens
        self.completion_tokens += c_tokens
        self.latency += latency_s


class ProviderRouter:

    # Picks a provider by privacy + complexity, then fails over down the list,
    # circuit-breaker aware, with the local model as the always-on floor.
    #
    # Economics here are inverted vs. the usual: the free cloud model is BOTH
    # faster and stronger than local, so:
    #   - sensitive work        -> local only (never leaves the device)
    #   - trivial work (LOW)     -> local first (preserve free-cloud quota)
    #   - everything else        -> best cloud first, local as floor
    # Genuinely hard tasks (HIGH) are still answered, but flagged for optional
    # manual escalation to Claude (Pro has no API, so this is human-in-loop).

    def __init__(self, providers=None):
        self.providers = providers if providers is not None else build_registry()
        self.telemetry = TelemetryAccumulator()
        self.trace = TraceLog()

    def _ordered(self, bar, sensitive):
        local = sorted([m for m in self.providers if m.local], key=lambda m: m.tier)
        cloud = sorted([m for m in self.providers if not m.local], key=lambda m: m.tier)
        if sensitive:
            return local
        if bar == LOW:
            return local + cloud
        return cloud + local

    def assess(self, prompt, history=None, expects_code=False):
        score = score_complexity(prompt, history, expects_code)
        return score, classify(score)

    def generate(self, prompt, fmt=None, max_tokens=8000,
                 sensitive=False, history=None, expects_code=False,
                 prefer_cloud=False):

        score, bar = self.assess(prompt, history, expects_code)

        if bar == HIGH and not sensitive:
            log.warning(
                "high-complexity task (score=%.2f) — flagged for manual "
                "Claude (Pro) escalation", score
            )
            record_escalation(prompt, score)

        order = self._ordered(bar, sensitive)

        # Cloud-pin: prefer_cloud opts a low-complexity call cloud-first for
        # quality (e.g. distillation); expects_code marks code generation, which
        # the local floor is unreliable at (repetition loops). Both reorder
        # cloud ahead of local while KEEPING local as the failover floor.
        # Privacy still wins: a sensitive run is local-only and never reordered.
        if (prefer_cloud or expects_code) and not sensitive:
            cloud = [m for m in order if not m.local]
            local = [m for m in order if m.local]
            order = cloud + local

        # Providers actually attempted (breaker-allowed), in order — recorded in
        # the trace so a failover is visible after the fact.
        tried = []

        for managed in order:

            if not managed.breaker.allow():
                continue

            tried.append(managed.name)

            try:
                t0 = time.time()
                output = managed.provider.generate(
                    prompt, fmt=fmt, max_tokens=max_tokens
                )
                t1 = time.time()
                managed.breaker.record_success()
                log.debug("served by %s (bar=%s)", managed.name, bar)

                # Record telemetry
                self.telemetry.record_call(prompt, output, t1 - t0)

                self.trace.record(
                    event="generate",
                    served_by=managed.name,
                    providers_tried=list(tried),
                    fallback_used=len(tried) > 1,
                    bar=bar,
                    score=round(score, 3),
                    prefer_cloud=bool(prefer_cloud),
                    expects_code=bool(expects_code),
                    sensitive=bool(sensitive),
                    latency=round(t1 - t0, 3),
                    ok=True,
                    output_kind="ok",
                )

                return output

            except Exception as error:
                severe = _is_timeout_error(error)
                managed.breaker.record_failure(severe=severe)
                log.warning("provider %s failed: %s", managed.name, error)
                self.trace.record(
                    event="provider_failure",
                    provider=managed.name,
                    bar=bar,
                    prefer_cloud=bool(prefer_cloud),
                    sensitive=bool(sensitive),
                    severe=severe,
                    error=str(error)[:200],
                )
                continue

        self.trace.record(
            event="generate",
            served_by=None,
            providers_tried=list(tried),
            fallback_used=False,
            bar=bar,
            score=round(score, 3),
            prefer_cloud=bool(prefer_cloud),
            expects_code=bool(expects_code),
            sensitive=bool(sensitive),
            ok=False,
            output_kind="canned",
        )

        log.error("all providers unavailable")
        return CANNED_FALLBACK
