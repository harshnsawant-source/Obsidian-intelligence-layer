# Cheap, deterministic complexity scoring. NEVER calls an LLM — routing must
# be near-free, or you pay the very cost you are trying to avoid.

LOW = "low"
MEDIUM = "medium"
HIGH = "high"

_REASONING = (
    "architect", "design", "debug", "refactor", "prove", "trade-off",
    "tradeoff", "plan", "root cause", "optimize", "analyze", "why ",
    "compare", "strategy", "evaluate",
)

_CODE = (
    "traceback", "stack trace", "def ", "class ", "function", "bug",
    "implement", "exception", "compile",
)

_MULTISTEP = ("step", "then ", "after that", "first,", "finally", "subtask")


def score_complexity(prompt, history=None, expects_code=False):

    text = prompt or ""
    low = text.lower()

    score = 0.0
    score += min((len(text) / 4) / 2000, 0.30)            # length / long-context

    if any(k in low for k in _REASONING):
        score += 0.30
    if expects_code or "```" in text or any(k in low for k in _CODE):
        score += 0.25
    if low.count("\n") > 8 or any(k in low for k in _MULTISTEP):
        score += 0.10
    if history and len(history) > 6:
        score += 0.05

    return min(score, 1.0)


def classify(score):
    if score < 0.25:
        return LOW
    if score < 0.6:
        return MEDIUM
    return HIGH
