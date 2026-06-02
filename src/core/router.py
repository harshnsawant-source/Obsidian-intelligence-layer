from core.providers.registry import build_registry
from core.complexity import score_complexity, classify, LOW, HIGH
from core.escalation import record_escalation
from core.log import get_logger


log = get_logger("router")

CANNED_FALLBACK = (
    "[orchestrator] All providers are currently unavailable. "
    "Please retry shortly."
)


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
                 sensitive=False, history=None, expects_code=False):

        score, bar = self.assess(prompt, history, expects_code)

        if bar == HIGH and not sensitive:
            log.warning(
                "high-complexity task (score=%.2f) — flagged for manual "
                "Claude (Pro) escalation", score
            )
            record_escalation(prompt, score)

        for managed in self._ordered(bar, sensitive):

            if not managed.breaker.allow():
                continue

            try:
                output = managed.provider.generate(
                    prompt, fmt=fmt, max_tokens=max_tokens
                )
                managed.breaker.record_success()
                log.debug("served by %s (bar=%s)", managed.name, bar)
                return output

            except Exception as error:
                managed.breaker.record_failure()
                log.warning("provider %s failed: %s", managed.name, error)
                continue

        log.error("all providers unavailable")
        return CANNED_FALLBACK
