# Graders answer "is this output correct for this task?" — exactly what a
# Verifier does, so graders ARE verifiers: grade(task, output) -> Verdict.
# The same definition of "correct" drives runtime self-correction AND offline
# eval scoring. See FEEDBACK_EVAL.md section 2.

import re

from core.verification import Verdict
from core.verifiers import SchemaVerifier, CodeVerifier


def _norm(text):
    return " ".join(str(text or "").split()).lower()


def contains_grader(expected):
    # Pass if every expected substring appears in the output (case-insensitive).
    needles = expected if isinstance(expected, list) else [expected]
    needles = [str(n) for n in needles]

    def grade(task, output):
        low = str(output or "").lower()
        missing = [n for n in needles if n.lower() not in low]
        if missing:
            return Verdict(False, feedback=f"missing: {missing}", source="contains")
        return Verdict(True, source="contains")

    return grade


def exact_grader(expected):
    target = _norm(expected)

    def grade(task, output):
        ok = _norm(output) == target
        return Verdict(ok, feedback="" if ok else "no exact match", source="exact")

    return grade


def regex_grader(pattern):
    rx = re.compile(pattern, re.DOTALL)

    def grade(task, output):
        ok = bool(rx.search(str(output or "")))
        return Verdict(ok, feedback="" if ok else "pattern not found", source="regex")

    return grade


def code_grader(test):
    # Reuses the Phase-3 sandboxed CodeVerifier: the sandbox IS the grader, so
    # scoring is objective and free (no LLM judge).
    verifier = CodeVerifier(execute=True, test=test)

    def grade(task, output):
        return verifier.check(task, output, {})

    return grade


def schema_grader(required_keys=None):
    verifier = SchemaVerifier(required_keys=required_keys)

    def grade(task, output):
        return verifier.check(task, output, {})

    return grade


_BUILDERS = {
    "contains": lambda spec: contains_grader(spec.get("expected", "")),
    "exact": lambda spec: exact_grader(spec.get("expected", "")),
    "regex": lambda spec: regex_grader(spec.get("pattern", "")),
    "code": lambda spec: code_grader(spec.get("test", "")),
    "schema": lambda spec: schema_grader(spec.get("required_keys")),
}


def make_grader(spec):
    # spec is a parsed eval case dict; "grader" names the kind.
    kind = spec.get("grader", "contains")
    builder = _BUILDERS.get(kind)
    if builder is None:
        raise ValueError(f"unknown grader: {kind}")
    return builder(spec)
