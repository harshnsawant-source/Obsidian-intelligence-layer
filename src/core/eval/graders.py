# Graders answer "is this output correct for this task?" — exactly what a
# Verifier does, so graders ARE verifiers: grade(task, output) -> Verdict.
# The same definition of "correct" drives runtime self-correction AND offline
# eval scoring. See FEEDBACK_EVAL.md section 2.

import re
import base64
import secrets

from core.verification import Verdict
from core.verifiers import SchemaVerifier, CodeVerifier, extract_code
from core.sandbox import run_python


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


def _build_fractional_harness(code, tests, nonce):
    # Re-exec the submission into a FRESH namespace for each hidden test (true
    # isolation: no mutable state leaks between tests), tally passes, and write
    # the result with a per-run NONCE the submission cannot predict (so a model
    # printing a fake result line cannot spoof the score). The submission is
    # base64-embedded (no quote-collision risk) and its stdout is swallowed.
    b64 = base64.b64encode(code.encode("utf-8")).decode("ascii")
    # Tests are base64-embedded too, so a test ending in a quote (e.g. == '0 B')
    # cannot break the harness's string quoting.
    test_items = ",\n".join(
        "    base64.b64decode('"
        + base64.b64encode(t.encode("utf-8")).decode("ascii")
        + "').decode('utf-8')"
        for t in tests
    )
    return (
        "import sys, io, math, base64\n"
        "__SRC = base64.b64decode('" + b64 + "').decode('utf-8')\n"
        "__CODE = compile(__SRC, '<submission>', 'exec')\n"
        "__TESTS = [\n" + test_items + "\n]\n"
        "__p = 0\n"
        "for __t in __TESTS:\n"
        "    __scope = {}\n"
        "    try:\n"
        "        sys.stdout = io.StringIO()\n"
        "        exec(__CODE, __scope)\n"
        "        exec(compile(__t, '<hidden_test>', 'exec'), __scope)\n"
        "        __p += 1\n"
        "    except Exception:\n"
        "        pass\n"
        "    finally:\n"
        "        sys.stdout = sys.__stdout__\n"
        "sys.stderr.write('__OIL_RESULT_" + nonce + "__ %d/%d\\n' % (__p, len(__TESTS)))\n"
    )


def fractional_code_grader(tests):
    # Partial-credit objective grader: score = (hidden tests passed)/(total).
    # The sandbox IS the grader (objective, no LLM judge). Nonce-protected.
    tests = [str(t) for t in (tests or [])]

    def grade(task, output):
        code = extract_code(output)
        if not code or not tests:
            return Verdict(False, score=0.0,
                           feedback="no code block or no hidden tests",
                           source="fractional_code")

        nonce = secrets.token_hex(8)
        script = _build_fractional_harness(code, tests, nonce)
        result = run_python(script, timeout=15)

        combined = (result.stdout or "") + "\n" + (result.stderr or "")
        match = re.search(r"__OIL_RESULT_" + re.escape(nonce) + r"__ (\d+)/(\d+)",
                          combined)
        if not match:
            return Verdict(False, score=0.0,
                           feedback="harness produced no result: "
                                    + result.error_text[:200],
                           source="fractional_code")

        passed, total = int(match.group(1)), int(match.group(2))
        score = (passed / total) if total else 0.0
        return Verdict(ok=(total > 0 and passed == total), score=score,
                       feedback=f"{passed}/{total} hidden tests passed",
                       source="fractional_code")

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
    # V2: partial-credit objective grading over HIDDEN tests (public tests drive
    # arm B's verify loop separately, so iteration can't teach to the grader).
    "fractional_code": lambda spec: fractional_code_grader(
        spec.get("hidden_tests") or spec.get("tests")
    ),
}


def make_grader(spec):
    # spec is a parsed eval case dict; "grader" names the kind.
    kind = spec.get("grader", "contains")
    builder = _BUILDERS.get(kind)
    if builder is None:
        raise ValueError(f"unknown grader: {kind}")
    return builder(spec)
