# Concrete verifiers. Each judges one output shape and returns a Verdict whose
# feedback is concrete enough to drive a useful correction pass. See
# VERIFICATION.md section 3.

import re
import json

from core.verification import Verifier, Verdict
from core.sandbox import run_python
from core.llm_engine import query_llm
from core.log import get_logger


log = get_logger("verifiers")

_CODE_FENCE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL)


def extract_code(text):

    # Prefer fenced ```python blocks; fall back to the whole string.
    if not text:
        return ""
    blocks = _CODE_FENCE.findall(text)
    if blocks:
        return "\n\n".join(b.strip() for b in blocks)
    return text.strip()


def extract_json(text):

    # Lenient JSON extraction: strip fences, else grab the first {...} / [...].
    # Returns the parsed object or None. Mirrors planner._parse_steps.
    if not text:
        return None
    s = str(text).strip()
    try:
        return json.loads(s)
    except Exception:
        pass
    for open_c, close_c in (("{", "}"), ("[", "]")):
        start = s.find(open_c)
        end = s.rfind(close_c)
        if start != -1 and end > start:
            try:
                return json.loads(s[start:end + 1])
            except Exception:
                continue
    return None


class SchemaVerifier(Verifier):

    # Structured output: must be parseable JSON, optionally containing all of
    # `required_keys` (only checked when the parsed value is a dict). Cheap,
    # deterministic, no LLM.

    name = "schema"

    def __init__(self, required_keys=None):
        self.required_keys = list(required_keys or [])

    def check(self, task, output, meta):
        data = extract_json(output)

        if data is None:
            return Verdict(
                ok=False,
                feedback="Output was not valid JSON. Return a single valid "
                         "JSON value with no prose around it.",
                source=self.name,
            )

        if self.required_keys and isinstance(data, dict):
            missing = [k for k in self.required_keys if k not in data]
            if missing:
                return Verdict(
                    ok=False,
                    feedback=f"JSON is missing required keys: {missing}.",
                    source=self.name,
                )

        return Verdict(ok=True, source=self.name)


class CodeVerifier(Verifier):

    # Code: extract it and run it in the sandbox. Optionally append a test
    # snippet (meta["test"] or the constructor `test`) executed after the code.
    #
    # OPT-IN: executing model-generated code is the real risk surface, so this
    # only runs when execute=True. With execute=False it is a no-op (applies
    # returns False), which keeps it safe to attach by default.

    name = "code"

    def __init__(self, execute=False, timeout=10, test=None):
        self.execute = execute
        self.timeout = timeout
        self.test = test

    def applies(self, task, output, meta):
        if not self.execute:
            return False
        return bool(extract_code(output))

    def check(self, task, output, meta):
        code = extract_code(output)
        test = meta.get("test") if meta else None
        test = test or self.test
        if test:
            code = f"{code}\n\n{test}"

        result = run_python(code, timeout=self.timeout)

        if result.ok:
            return Verdict(ok=True, source=self.name)

        return Verdict(
            ok=False,
            feedback="The code failed when executed:\n" + result.error_text,
            source=self.name,
        )


class CriticVerifier(Verifier):

    # Prose / reasoning: a second model call reviews the output against the
    # task and returns a JSON judgement. Costs one extra LLM call, so attach it
    # only where the second pass pays off (final answers, synthesis).

    name = "critic"

    def __init__(self, sensitive=False, threshold=0.6):
        self.sensitive = sensitive
        self.threshold = threshold

    def check(self, task, output, meta):
        prompt = f"""You are a strict reviewer. Judge whether the RESPONSE
fully and correctly satisfies the TASK. Reply with ONLY a JSON object:
{{"ok": <true|false>, "score": <0.0-1.0>, "issues": "<specific, actionable problems, or empty>"}}

TASK:
{task}

RESPONSE:
{output}"""

        raw = query_llm(prompt, fmt="json", max_tokens=600,
                        sensitive=self.sensitive)

        data = extract_json(raw)

        if not isinstance(data, dict):
            # Critic itself failed to produce a verdict — do not block the
            # output on a flaky reviewer; pass with a neutral score.
            log.debug("critic returned unparseable verdict; passing through")
            return Verdict(ok=True, score=0.5, source=self.name)

        score = data.get("score")
        try:
            score = float(score)
        except (TypeError, ValueError):
            score = 1.0 if data.get("ok") else 0.0

        ok = bool(data.get("ok")) and score >= self.threshold

        return Verdict(
            ok=ok,
            score=score,
            feedback=str(data.get("issues", "")).strip(),
            source=self.name,
        )
