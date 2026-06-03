# Contribution protocol — the seam by which agents emit STRUCTURED reasoning
# (findings / decisions / artifacts / risks / assumptions) inside their normal
# text output, which the PlanExecutor then parses and merges into the shared
# context. Agents stay pure str->str; this is the single parse + prompt point.
#
# An agent opts in (via BaseAgent.contributes) to being PROMPTED for certain
# types; parsing is universal and harmless when no block is present.

import re
import json


CONTRIBUTION_TYPES = ("findings", "decisions", "artifacts", "risks", "assumptions")

_BLOCK = re.compile(r"```contributions\s*(.*?)```", re.DOTALL | re.IGNORECASE)

# The minimal required key per type — entries missing it are dropped as malformed.
_REQUIRED_KEY = {
    "findings": "finding",
    "decisions": "decision",
    "artifacts": "type",
    "risks": "risk",
    "assumptions": "assumption",
}

# Human-facing schema fragments for the prompt instruction.
_SCHEMAS = {
    "findings": '"findings": [{"finding": "...", "source": "...", "confidence": 0.0-1.0}]',
    "decisions": '"decisions": [{"decision": "...", "reasoning": "...", "tradeoffs": ["..."]}]',
    "artifacts": '"artifacts": [{"type": "architecture|schema|roadmap|implementation_plan|...", "content": "...", "metadata": {}}]',
    "risks": '"risks": [{"risk": "...", "severity": "low|medium|high", "mitigation": "..."}]',
    "assumptions": '"assumptions": [{"assumption": "...", "confidence": 0.0-1.0}]',
}


def build_instruction(types):

    # Prompt fragment telling an agent to optionally append a contributions
    # block for the given types. Empty types -> empty string (no behavior change).
    types = [t for t in (types or []) if t in _SCHEMAS]

    if not types:
        return ""

    fields = ",\n  ".join(_SCHEMAS[t] for t in types)

    return (
        "\n\nAfter your answer, IF you produced any structured reasoning, append "
        "a fenced block exactly like this (omit keys you have nothing for; omit "
        "the whole block if nothing applies):\n"
        "```contributions\n{\n  " + fields + "\n}\n```"
        "\nEmit ONLY the contribution types shown above for your role; do NOT "
        "copy, echo, or repeat any contributions block already present in the "
        "context."
    )


def strip_contributions(text):

    # Remove any ```contributions``` block(s) from an agent's output BEFORE it is
    # injected into another agent's prompt, so the receiving agent reasons over
    # the content and does not mimic the machine structure (Phase 5.1, issue 1).
    # Preserves all other reasoning; collapses the blank lines left behind.
    if not text:
        return text

    cleaned = _BLOCK.sub("", str(text))
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _loads(text):
    try:
        return json.loads(text)
    except Exception:
        return None


def parse_contributions(text):

    # Lenient: pull the ```contributions``` block (or, failing that, a bare {...}
    # that contains a known key), validate entries, drop malformed ones. Never
    # raises; returns {} when there is nothing usable.

    if not text:
        return {}

    raw = None

    match = _BLOCK.search(str(text))

    if match:
        raw = match.group(1).strip()

    data = _loads(raw) if raw else None

    if data is None:
        # Fallback: a bare {...} object that contains any contribution key.
        s = str(text)
        start, end = s.find("{"), s.rfind("}")
        if start != -1 and end > start:
            candidate = _loads(s[start:end + 1])
            if isinstance(candidate, dict) and any(
                k in candidate for k in CONTRIBUTION_TYPES
            ):
                data = candidate

    if not isinstance(data, dict):
        return {}

    out = {}

    for kind in CONTRIBUTION_TYPES:

        entries = data.get(kind)

        if not isinstance(entries, list):
            continue

        valid = [
            e for e in entries
            if isinstance(e, dict)
            and str(e.get(_REQUIRED_KEY[kind], "")).strip()
        ]

        if valid:
            out[kind] = valid

    return out
