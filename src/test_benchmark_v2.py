import sys

import core.eval.graders as g
import core.eval.arms as arms
import core.eval.lift_benchmark as lb
from core.eval.benchmark_cases_v2 import CASES

PASS = []
FAIL = []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("PASS" if cond else "FAIL"), "-", name)


def block(src):
    return "```python\n" + src + "\n```"


# ===== fractional grader =====================================================
gr = g.fractional_code_grader([
    "assert f(1) == 1", "assert f(2) == 2", "assert f(3) == 99",
])
v = gr("t", block("def f(x):\n    return x"))
check("fractional: partial credit (2/3)", abs(v.score - 2.0 / 3.0) < 1e-9 and not v.ok)

full = g.fractional_code_grader(["assert f(1) == 2", "assert f(5) == 6"])
check("fractional: all pass -> 1.0 ok",
      full("t", block("def f(x):\n    return x + 1")).score == 1.0)

check("fractional: syntax error -> 0.0",
      gr("t", block("def f(x) return x")).score == 0.0)

check("fractional: no code block -> 0.0", gr("t", "just prose").score == 0.0)

# Spoofing: submission prints a fake result line with a WRONG nonce -> ignored;
# the real (random-nonce) harness line wins. f returns 0 -> all fail -> 0.0.
spoof = block(
    "import sys\n"
    "sys.stderr.write('__OIL_RESULT_deadbeef__ 3/3\\n')\n"
    "def f(x):\n    return 0"
)
gr3 = g.fractional_code_grader(["assert f(1)==1", "assert f(2)==2", "assert f(3)==3"])
check("fractional: spoofed result ignored (real nonce wins)",
      gr3("t", spoof).score == 0.0)

# Isolation: a test mutating submission-level state must NOT affect another.
iso = g.fractional_code_grader([
    "G.append(1)\nassert G == [1]",   # mutates G
    "assert G == []",                  # fresh submission -> G empty again
])
check("fractional: hidden tests isolated (fresh submission per test)",
      iso("t", block("G = []")).score == 1.0)


# ===== case-catalog self-consistency ========================================
for case in CASES:
    hidden = g.make_grader({"grader": "fractional_code",
                            "hidden_tests": case["hidden_tests"]})
    public = g.make_grader({"grader": "fractional_code",
                            "hidden_tests": case["public_tests"]})
    rv = hidden(case["task"], block(case["reference"]))
    pv = public(case["task"], block(case["reference"]))
    check(f"case {case['id']}: reference passes ALL hidden", rv.score == 1.0 and rv.ok)
    check(f"case {case['id']}: reference passes ALL public", pv.score == 1.0)


# ===== arms (stubbed; real sandbox verifier) ================================
_real_q = arms.query_llm

# Arm A: exactly one call.
calls = {"n": 0}
def _count_q(prompt, *a, **k):
    calls["n"] += 1
    return block("def f(x):\n    return x")
arms.query_llm = _count_q
arms.arm_baseline("task", ["assert f(1)==1"])
check("arm A: single call", calls["n"] == 1)

# Arm B: first attempt fails public test -> retries via correction -> passes.
seq = {"n": 0}
def _retry_q(prompt, *a, **k):
    seq["n"] += 1
    return block("def f(x):\n    return x + 2") if seq["n"] == 1 \
        else block("def f(x):\n    return x + 1")
arms.query_llm = _retry_q
outB = arms.arm_verified_single("make f", ["assert f(1) == 2"])
check("arm B: retries on public failure then passes",
      seq["n"] == 2 and "x + 1" in outB)

# Arm C: planner provides the initial attempt; SAME verify loop corrects it.
import agents.planner_agent as pa
_real_planner = pa.PlannerAgent

class _FakePlannerWrong:
    made = 0
    def __init__(self):
        _FakePlannerWrong.made += 1
    def run(self, task):
        return block("def f(x):\n    return x + 99")   # wrong -> public fails

corr = {"n": 0}
def _corr_q(prompt, *a, **k):
    corr["n"] += 1
    return block("def f(x):\n    return x + 1")        # correct
pa.PlannerAgent = _FakePlannerWrong
arms.query_llm = _corr_q
try:
    outC = arms.arm_verified_planner("make f", ["assert f(1) == 2"])
    check("arm C: planner used for initial attempt",
          _FakePlannerWrong.made >= 1)
    check("arm C: same verify loop corrects via single call",
          corr["n"] >= 1 and "x + 1" in outC)
finally:
    pa.PlannerAgent = _real_planner
    arms.query_llm = _real_q


# ===== analyze_v2: lifts, MDE, Holm, falsifiable null =======================
def trials(score, calls=1, wall=1.0, n=6):
    return [{"score": score, "calls": calls, "prompt_tokens": 10,
             "completion_tokens": 10, "latency": wall, "wall": wall,
             "infra_error": False} for _ in range(n)]

# A clear lift: B and C beat A; C a touch above B.
res = {
    "c1": {"id": "c1", "category": "spec", "arms": {
        "A": trials(0.40, calls=1, wall=1.0),
        "B": trials(0.85, calls=3, wall=3.0),
        "C": trials(0.88, calls=12, wall=20.0),
    }},
}
rep = lb.analyze_v2(res, k_sig=2.0, cost_axis="wall")
cat = rep["categories"][0]
check("analyze_v2: B-A lift computed", abs(cat["pairs"]["B-A"]["lift"] - 0.45) < 1e-9)
check("analyze_v2: MDE reported", "mde" in cat["pairs"]["B-A"])
check("analyze_v2: B-A earns cost (significant + cost-positive)",
      cat["pairs"]["B-A"]["earns_cost"] is True)
check("analyze_v2: Holm fields present",
      "significant_holm" in cat["pairs"]["C-B"])

# Falsifiable NULL: all arms equal -> nothing earns cost.
null = {
    "c1": {"id": "c1", "category": "spec", "arms": {
        "A": trials(0.50, calls=1, wall=1.0),
        "B": trials(0.50, calls=3, wall=3.0),
        "C": trials(0.50, calls=12, wall=20.0),
    }},
}
repn = lb.analyze_v2(null, k_sig=2.0, cost_axis="wall")
catn = repn["categories"][0]
check("analyze_v2: NULL -> no pair earns cost (falsifiable)",
      all(not p["earns_cost"] for p in catn["pairs"].values()))


# ===== calibration: elimination only (no mid-band selection) ================
_real_trial = lb.run_trial_v2
_scores = {"hi": 0.95, "lo": 0.05, "mid": 0.5, "noisy": None}

def _fake_trial(task, runner_fn, grader):
    # score keyed by the case id smuggled via task text
    if "HI" in task:
        s = 0.95
    elif "LO" in task:
        s = 0.05
    elif "NOISY" in task:
        s = 0.0 if (_fake_trial.k % 2 == 0) else 1.0  # std ~0.5
    else:
        s = 0.5
    _fake_trial.k += 1
    return {"score": s, "calls": 1, "prompt_tokens": 0, "completion_tokens": 0,
            "latency": 0.0, "wall": 0.0, "infra_error": False}
_fake_trial.k = 0

cal_cases = [
    {"id": "ceil", "category": "x", "task": "HI", "public_tests": [], "hidden_tests": ["assert True"]},
    {"id": "floor", "category": "x", "task": "LO", "public_tests": [], "hidden_tests": ["assert True"]},
    {"id": "mid", "category": "x", "task": "MID", "public_tests": [], "hidden_tests": ["assert True"]},
    {"id": "noisy", "category": "x", "task": "NOISY", "public_tests": [], "hidden_tests": ["assert True"]},
]
lb.run_trial_v2 = _fake_trial
try:
    cal = lb.run_calibration(cal_cases, K=6, isolate=False)
finally:
    lb.run_trial_v2 = _real_trial

verdicts = {r["id"]: r["verdict"] for r in cal["cases"]}
check("calibration: ceiling dropped", verdicts["ceil"] == "drop:ceiling")
check("calibration: floor dropped", verdicts["floor"] == "drop:floor")
check("calibration: high-variance dropped", verdicts["noisy"] == "drop:high-variance")
check("calibration: mid-band kept (no selection bias)", verdicts["mid"] == "keep")
check("calibration: kept list correct", cal["kept"] == ["mid"])


# Regression: run_calibration must work through the REAL isolated_vault path
# (isolate=True). The earlier test used isolate=False and missed a NameError.
_orig_A = arms.ARMS["A"]
arms.ARMS["A"] = lambda task, pub: block("def f(x):\n    return x")
try:
    tiny = [{"id": "t", "category": "x", "task": "t",
             "public_tests": [], "hidden_tests": ["assert f(1) == 1"]}]
    cal = lb.run_calibration(tiny, K=1, isolate=True, keep_vault=False)
    check("calibration: isolate=True path runs (regression)",
          isinstance(cal.get("kept"), list) and len(cal["cases"]) == 1)
finally:
    arms.ARMS["A"] = _orig_A


print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
