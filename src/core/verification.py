# Generate -> verify -> correct loop. Pure: it owns retries, verifiers only
# judge, and the generation step is injected as a closure so this module has no
# dependency on agents, the LLM, or the sandbox. See VERIFICATION.md.

from core.log import get_logger


log = get_logger("verification")


class Verdict:

    # The result of checking one (task, output) pair. `feedback` is fed back
    # into the next generation, so it must be concrete and actionable.

    def __init__(self, ok, score=None, feedback="", source="verifier"):
        self.ok = bool(ok)
        # Default score follows ok so a verifier can pass/fail without grading.
        self.score = float(score) if score is not None else (1.0 if ok else 0.0)
        self.feedback = feedback or ""
        self.source = source

    def __repr__(self):
        return (
            f"Verdict(ok={self.ok}, score={self.score:.2f}, "
            f"source={self.source!r})"
        )


class Verifier:

    # Pluggable check. `applies` is a cheap relevance gate; `check` is the
    # judgement. A verifier never regenerates and never mutates state.

    name = "base"

    def applies(self, task, output, meta):
        return True

    def check(self, task, output, meta):
        raise NotImplementedError


class RefineResult:

    def __init__(self, output, verdict, ok, attempts):
        self.output = output
        self.verdict = verdict   # None when no verifier ran
        self.ok = ok
        self.attempts = attempts

    def __repr__(self):
        return (
            f"RefineResult(ok={self.ok}, attempts={self.attempts}, "
            f"verdict={self.verdict!r})"
        )


def aggregate(verifiers, task, output, meta):

    # AND semantics: all must pass. Feedback concatenated, score = min.
    verdicts = [v.check(task, output, meta) for v in verifiers]

    ok = all(v.ok for v in verdicts)

    score = min((v.score for v in verdicts), default=1.0)

    feedback = "\n\n".join(
        f"[{v.source}] {v.feedback}".strip()
        for v in verdicts if not v.ok and v.feedback
    )

    return Verdict(ok=ok, score=score, feedback=feedback, source="aggregate")


def refine(generate, task, verifiers=None, max_tries=2, meta=None):

    # generate(feedback, previous) -> str. Returns a RefineResult whose output
    # has always been verified (or is the best-scoring attempt on exhaustion).
    # No applicable verifiers => exactly one call, no behavior change.

    meta = meta or {}

    output = generate(None, None)

    active = [
        v for v in (verifiers or [])
        if _safe_applies(v, task, output, meta)
    ]

    if not active:
        return RefineResult(output, verdict=None, ok=True, attempts=1)

    best_output, best_verdict = output, None

    for attempt in range(1, max(1, max_tries) + 1):

        verdict = aggregate(active, task, output, meta)

        if best_verdict is None or verdict.score > best_verdict.score:
            best_output, best_verdict = output, verdict

        if verdict.ok:
            log.debug("verified on attempt %d (%s)", attempt, verdict)
            return RefineResult(output, verdict, ok=True, attempts=attempt)

        if attempt >= max_tries:
            break

        log.debug(
            "attempt %d failed (%s); regenerating with feedback",
            attempt, verdict,
        )

        output = generate(verdict.feedback, output)

    log.warning(
        "verification exhausted after %d tries; returning best attempt (%s)",
        max_tries, best_verdict,
    )

    return RefineResult(best_output, best_verdict, ok=False, attempts=max_tries)


def _safe_applies(verifier, task, output, meta):

    # A misbehaving verifier must never break generation.
    try:
        return verifier.applies(task, output, meta)
    except Exception as error:
        log.warning("verifier %s.applies raised: %s", verifier, error)
        return False
