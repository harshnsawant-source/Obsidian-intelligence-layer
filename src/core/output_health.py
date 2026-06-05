from collections import Counter


# Detect degenerate model output — output that technically "returned" but is
# unusable: empty, a no-final-answer sentinel, or a repetition loop. The Phase A
# sweep showed the local model emitting hundreds of identical lines ending in
# "[NO FINAL ANSWER GENERATED]"; because that is neither an exception nor the
# router's canned string, it was returned as a valid answer and threaded into
# the merge. The router uses is_degenerate() to treat such output as a provider
# failure and fail over instead.
#
# Thresholds are deliberately CONSERVATIVE — a false positive wastes one failover
# but a false negative poisons a run. Only a long, byte-identical line repeated
# many times (or an overwhelmingly repetitive body) trips the repetition check,
# so normal prose and code are unaffected.


# Sentinels the model adapter emits when a (reasoning) model produced no usable
# final answer.
NO_ANSWER_MARKERS = (
    "[NO FINAL ANSWER GENERATED]",
    "No response generated.",
)

# A line must be at least this long to count toward the repetition heuristics —
# short lines (`}`, `return None`, blank) repeat legitimately in real output.
_SUBSTANTIAL_LINE_CHARS = 20


def is_degenerate(
    text,
    min_repeat=10,
    min_lines_for_ratio=40,
    distinct_ratio_floor=0.25,
):
    """Return (is_degenerate, reason). reason is "" when healthy."""

    if not isinstance(text, str) or not text.strip():
        return True, "empty"

    for marker in NO_ANSWER_MARKERS:
        if marker in text:
            return True, "no_final_answer"

    substantial = [
        ln.strip()
        for ln in text.splitlines()
        if len(ln.strip()) >= _SUBSTANTIAL_LINE_CHARS
    ]

    if substantial:
        counts = Counter(substantial)
        line, freq = counts.most_common(1)[0]

        # One long line repeated many times == a loop.
        if freq >= min_repeat:
            return True, f"repeated_line_x{freq}"

        # Or an overwhelmingly repetitive body (few distinct lines among many).
        if len(substantial) >= min_lines_for_ratio:
            distinct_ratio = len(counts) / len(substantial)
            if distinct_ratio < distinct_ratio_floor:
                return True, f"low_distinct_ratio_{distinct_ratio:.2f}"

    return False, ""


def is_failed_output(text, extra_markers=()):
    """True if `text` should be treated as a FAILED subtask result — either
    degenerate (see is_degenerate) or matching a caller-supplied failure marker.

    Callers pass the router's canned all-providers-down sentinel as an extra
    marker (output_health stays decoupled from the router, so no circular
    import). Returns (is_failed, reason); reason is "" when usable.
    """
    if isinstance(text, str):
        for marker in extra_markers:
            if marker and marker in text:
                return True, "canned_fallback"
    return is_degenerate(text)
