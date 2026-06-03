import sys

from core.verification import refine, aggregate, Verdict, Verifier
from core.sandbox import run_python
import core.verifiers as vf
from core.verifiers import SchemaVerifier, CodeVerifier, CriticVerifier
import agents.base_agent as ba
from agents.base_agent import BaseAgent

PASS = []
FAIL = []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("PASS" if cond else "FAIL"), "-", name)


# ---- helpers -------------------------------------------------------------

class StubVerifier(Verifier):
    # Passes once output contains the magic token; otherwise fails with feedback.
    def __init__(self, token="GOOD", score_fail=0.3):
        self.token = token
        self.score_fail = score_fail

    def check(self, task, output, meta):
        if self.token in (output or ""):
            return Verdict(ok=True, score=1.0, source="stub")
        return Verdict(ok=False, score=self.score_fail,
                       feedback=f"must contain {self.token}", source="stub")


# ---- refine loop ---------------------------------------------------------

# Test 1: no verifiers -> single call, no behavior change
calls = []
def gen_once(fb, prev):
    calls.append(fb)
    return "anything"
r = refine(gen_once, "t", verifiers=[], max_tries=3)
check("refine: no verifiers -> 1 call", len(calls) == 1)
check("refine: no verifiers -> ok, verdict None", r.ok and r.verdict is None)

# Test 2: passes on first attempt
calls = []
def gen_good(fb, prev):
    calls.append(fb)
    return "this is GOOD"
r = refine(gen_good, "t", verifiers=[StubVerifier()], max_tries=3)
check("refine: pass first try -> 1 call", len(calls) == 1 and r.attempts == 1)
check("refine: pass first try -> ok", r.ok)

# Test 3: fail then pass; feedback is fed back into regeneration
seen_feedback = []
def gen_fix(fb, prev):
    seen_feedback.append(fb)
    return "bad" if fb is None else "now GOOD"
r = refine(gen_fix, "t", verifiers=[StubVerifier()], max_tries=3)
check("refine: retry then pass -> ok", r.ok and r.attempts == 2)
check("refine: first call has no feedback", seen_feedback[0] is None)
check("refine: retry receives feedback", "must contain GOOD" in (seen_feedback[1] or ""))

# Test 4: exhaustion returns best-scoring attempt, ok=False
attempt_n = {"i": 0}
def gen_improving(fb, prev):
    # never satisfies StubVerifier but second attempt scores higher
    attempt_n["i"] += 1
    return f"attempt{attempt_n['i']}"
class ScoreVerifier(Verifier):
    def check(self, task, output, meta):
        score = 0.2 if output == "attempt1" else 0.5
        return Verdict(ok=False, score=score, feedback="nope", source="score")
r = refine(gen_improving, "t", verifiers=[ScoreVerifier()], max_tries=2)
check("refine: exhausted -> ok False", r.ok is False and r.attempts == 2)
check("refine: returns best-scoring attempt", r.output == "attempt2")

# Test 5: aggregate AND semantics
a = aggregate([StubVerifier("A"), StubVerifier("B")], "t", "has A only", {})
check("aggregate: one failing -> overall fail", a.ok is False)
check("aggregate: feedback names failing verifier", "must contain B" in a.feedback)
a2 = aggregate([StubVerifier("A"), StubVerifier("B")], "t", "has A and B", {})
check("aggregate: all pass -> ok", a2.ok)


# ---- SchemaVerifier ------------------------------------------------------

sv = SchemaVerifier()
check("schema: valid JSON passes", sv.check("t", '{"a": 1}', {}).ok)
check("schema: fenced JSON passes", sv.check("t", '```json\n{"a":1}\n```', {}).ok)
check("schema: prose fails", sv.check("t", "no json here", {}).ok is False)
svk = SchemaVerifier(required_keys=["name", "id"])
check("schema: missing key fails", svk.check("t", '{"name":"x"}', {}).ok is False)
check("schema: all keys present passes", svk.check("t", '{"name":"x","id":1}', {}).ok)


# ---- sandbox + CodeVerifier ---------------------------------------------

res = run_python("print('hello'); x = 1 + 1\nassert x == 2")
check("sandbox: clean run ok", res.ok and "hello" in res.stdout)
res_bad = run_python("raise ValueError('boom')")
check("sandbox: exception -> not ok", res_bad.ok is False)
check("sandbox: stderr captured", "boom" in res_bad.stderr)
res_to = run_python("import time; time.sleep(5)", timeout=1)
check("sandbox: timeout flagged", res_to.timed_out and res_to.ok is False)

cv_off = CodeVerifier(execute=False)
check("code: execute=False is a no-op (applies False)",
      cv_off.applies("t", "```python\nprint(1)\n```", {}) is False)
cv = CodeVerifier(execute=True)
good = "```python\nprint('ok')\n```"
check("code: good code passes", cv.check("t", good, {}).ok)
bad = "```python\nraise RuntimeError('kaboom')\n```"
v_bad = cv.check("t", bad, {})
check("code: failing code fails with stderr feedback",
      v_bad.ok is False and "kaboom" in v_bad.feedback)
# meta test snippet appended after the code
withfn = "```python\ndef add(a, b):\n    return a + b\n```"
v_test = cv.check("t", withfn, {"test": "assert add(2, 3) == 5"})
check("code: meta test snippet runs and passes", v_test.ok)
v_test_bad = cv.check("t", withfn, {"test": "assert add(2, 3) == 6"})
check("code: meta test snippet catches wrong code", v_test_bad.ok is False)


# ---- CriticVerifier (LLM stubbed) ----------------------------------------

vf.query_llm = lambda *a, **k: '{"ok": true, "score": 0.9, "issues": ""}'
check("critic: approves good output", CriticVerifier().check("t", "answer", {}).ok)
vf.query_llm = lambda *a, **k: '{"ok": false, "score": 0.2, "issues": "vague"}'
v_crit = CriticVerifier().check("t", "answer", {})
check("critic: rejects bad output with issues",
      v_crit.ok is False and "vague" in v_crit.feedback)
vf.query_llm = lambda *a, **k: "not json at all"
check("critic: unparseable verdict passes through (no false block)",
      CriticVerifier().check("t", "answer", {}).ok)


# ---- BaseAgent distillation gate -----------------------------------------

distilled = []

class FakeDistill:
    def execute(self, ctx, data):
        distilled.append(data.get("task"))

ba.build_context = lambda task, *a, **k: ""
ba.save_memory = lambda name, result: "fake.md"
ba.load_skill = lambda name: FakeDistill()
ba.RuntimeContext = lambda: None

# Agent whose verifier passes -> output should distill
class PassAgent(BaseAgent):
    verifiers = [StubVerifier()]
    def __init__(self):
        super().__init__("pass-agent", "spec")

# Agent whose verifier always fails -> output must NOT distill
class FailAgent(BaseAgent):
    verifiers = [StubVerifier()]
    max_verify_tries = 2
    def __init__(self):
        super().__init__("fail-agent", "spec")

ba.query_llm = lambda *a, **k: "this is GOOD"
distilled.clear()
PassAgent().run("do x")
check("gate: verified output IS distilled", len(distilled) == 1)

ba.query_llm = lambda *a, **k: "this is bad"   # never contains GOOD
distilled.clear()
out = FailAgent().run("do y")
check("gate: failed-verification output NOT distilled", len(distilled) == 0)
check("gate: failed output still returned to caller", out == "this is bad")


print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
