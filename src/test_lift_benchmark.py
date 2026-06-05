import sys
import json
import tempfile
import shutil
import math
from pathlib import Path

# Add src to python path if not present
sys.path.insert(0, str(Path(__file__).resolve().parent))

import core.eval.lift_benchmark as lift_benchmark
from core.llm_engine import _router
from core.router import CANNED_FALLBACK
from core.eval.graders import Verdict

PASS = []
FAIL = []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("PASS" if cond else "FAIL"), "-", name)


# ---- test loading --------------------------------------------------------
cases = lift_benchmark.load_benchmark_cases()
check("load_benchmark_cases: loaded cases successfully", len(cases) > 0)
if cases:
    check("load_benchmark_cases: contains categories", all(c.category is not None for c in cases))


# ---- test math helpers ---------------------------------------------------
m, s = lift_benchmark.mean_std([1.0, 2.0, 3.0])
check("mean_std: calculates correct mean", abs(m - 2.0) < 1e-9)
check("mean_std: calculates correct std", abs(s - 1.0) < 1e-9)

m_single, s_single = lift_benchmark.mean_std([42.0])
check("mean_std: handles single item std", abs(s_single - 0.0) < 1e-9)


# ---- test run_trial with stubbed telemetry -------------------------------
class FakeCase:
    def __init__(self):
        self.task = "mock task"
        self.grader = lambda t, o: Verdict(ok=True, score=1.0, feedback="good")

def mock_runner(task):
    # Simulate making 2 LLM calls with some mock latency/tokens
    _router.telemetry.record_call("prompt 1", "completion 1", 0.1)
    _router.telemetry.record_call("prompt 2", "completion 2", 0.15)
    return "done"

case = FakeCase()
trial_res = lift_benchmark.run_trial(case, mock_runner)
check("run_trial: records correct score", trial_res["score"] == 1.0)
check("run_trial: records correct call count", trial_res["calls"] == 2)
check("run_trial: tracks estimated latency", abs(trial_res["latency"] - 0.25) < 0.01)
check("run_trial: tracks prompt tokens", trial_res["prompt_tokens"] > 0)
check("run_trial: tracks completion tokens", trial_res["completion_tokens"] > 0)


# ---- test analyze_results aggregation & cost-adjusted lift --------------
mock_raw_results = {
    "c1": {
        "category": "Engineering",
        "baseline": [
            {"score": 0.5, "calls": 1, "latency": 1.0},
            {"score": 0.5, "calls": 1, "latency": 1.0},
            {"score": 0.5, "calls": 1, "latency": 1.0}
        ],
        "pipeline": [
            {"score": 1.0, "calls": 3, "latency": 3.0},
            {"score": 1.0, "calls": 3, "latency": 3.0},
            {"score": 1.0, "calls": 3, "latency": 3.0}
        ]
    },
    "c2": {
        "category": "Research",
        "baseline": [
            {"score": 0.8, "calls": 1, "latency": 1.0},
            {"score": 0.8, "calls": 1, "latency": 1.0},
            {"score": 0.8, "calls": 1, "latency": 1.0}
        ],
        "pipeline": [
            {"score": 0.8, "calls": 4, "latency": 4.0},
            {"score": 0.8, "calls": 4, "latency": 4.0},
            {"score": 0.8, "calls": 4, "latency": 4.0}
        ]
    }
}

report = lift_benchmark.analyze_results(mock_raw_results)
check("analyze_results: contains categories in report", len(report["categories"]) == 2)

c1_agg = next(c for c in report["cases"] if c["id"] == "c1")
check("analyze_results: c1 baseline score mean is 0.5", c1_agg["baseline_score_mean"] == 0.5)
check("analyze_results: c1 pipeline score mean is 1.0", c1_agg["pipeline_score_mean"] == 1.0)
check("analyze_results: c1 extra calls is 2", c1_agg["extra_calls"] == 2.0)
check("analyze_results: c1 raw lift is 0.5", c1_agg["raw_lift"] == 0.5)
check("analyze_results: c1 cost-adjusted lift is 0.25", abs(c1_agg["cost_adjusted_lift"] - 0.25) < 1e-9)

c2_agg = next(c for c in report["cases"] if c["id"] == "c2")
check("analyze_results: c2 raw lift is 0.0", abs(c2_agg["raw_lift"]) < 1e-9)
check("analyze_results: c2 cost-adjusted lift is 0.0", abs(c2_agg["cost_adjusted_lift"]) < 1e-9)

cat_eng = next(c for c in report["categories"] if c["category"] == "Engineering")
check("analyze_results: category Engineering earns cost", cat_eng["earns_cost"] is True)

cat_res = next(c for c in report["categories"] if c["category"] == "Research")
check("analyze_results: category Research does not earn cost", cat_res["earns_cost"] is False)


# ---- test save_reports file output ---------------------------------------
tmpdir = tempfile.mkdtemp(prefix="oil_lift_")
try:
    lift_benchmark.LIFT_REPORT_JSON = Path(tmpdir) / "lift_reports.json"
    lift_benchmark.LIFT_REPORT_MD = Path(tmpdir) / "lift_report.md"
    
    lift_benchmark.save_reports(report)
    check("save_reports: json file created", lift_benchmark.LIFT_REPORT_JSON.exists())
    check("save_reports: md file created", lift_benchmark.LIFT_REPORT_MD.exists())
    
    md_content = lift_benchmark.LIFT_REPORT_MD.read_text(encoding="utf-8")
    check("save_reports: md table has header", "| Category |" in md_content)
    check("save_reports: md contains YES earns cost", "✅ YES" in md_content)
    check("save_reports: md contains NO earns cost", "❌ NO" in md_content)
finally:
    shutil.rmtree(tmpdir, ignore_errors=True)


# ---- significance gate: small lift inside variance must NOT earn cost -----
noisy = {
    "c_noisy": {
        "category": "Noisy",
        "baseline": [
            {"score": 0.0, "calls": 1, "latency": 1.0},
            {"score": 1.0, "calls": 1, "latency": 1.0},
            {"score": 0.5, "calls": 1, "latency": 1.0},
        ],
        "pipeline": [
            {"score": 0.6, "calls": 3, "latency": 3.0},
            {"score": 0.4, "calls": 3, "latency": 3.0},
            {"score": 0.6, "calls": 3, "latency": 3.0},
        ],
    }
}
rep_noisy = lift_benchmark.analyze_results(noisy)
cat_noisy = rep_noisy["categories"][0]
check("significance: standard_error computed", cat_noisy["standard_error"] > 0)
check("significance: tiny lift within variance is not significant",
      cat_noisy["significant"] is False)
check("significance: noisy category does NOT earn cost",
      cat_noisy["earns_cost"] is False)


# ---- infra errors excluded from score means -------------------------------
infra = {
    "c_infra": {
        "category": "Infra",
        "baseline": [
            {"score": 0.5, "calls": 1, "latency": 1.0},
            {"score": 0.5, "calls": 1, "latency": 1.0},
        ],
        "pipeline": [
            {"score": 1.0, "calls": 3, "latency": 3.0},
            {"score": 0.0, "calls": 1, "latency": 1.0, "infra_error": True},
        ],
    }
}
rep_infra = lift_benchmark.analyze_results(infra)
c_infra = next(c for c in rep_infra["cases"] if c["id"] == "c_infra")
check("infra: failed trial excluded from pipeline mean",
      abs(c_infra["pipeline_score_mean"] - 1.0) < 1e-9)
check("infra: infra error counted", c_infra["infra_errors"] == 1)


# ---- run_trial flags canned-fallback output as an infra error -------------
def canned_runner(task):
    return CANNED_FALLBACK


fc = FakeCase()
fc.grader = lambda t, o: Verdict(ok=False, score=0.0, feedback="down")
trial_canned = lift_benchmark.run_trial(fc, canned_runner)
check("run_trial: canned fallback flagged as infra error",
      trial_canned["infra_error"] is True)


# ---- isolated benchmark vault: writes/reads redirect then restore ---------
import capability.core.runtime_context as runtime_context
import core.context_builder as context_builder
import core.memory_writer as memory_writer
from core.eval.benchmark_vault import isolated_vault

_orig = (
    runtime_context.PROJECT_ROOT,
    memory_writer.MEMORIES_DIR,
    context_builder._index,
)

iso_root = Path(tempfile.mkdtemp(prefix="oil_isovault_"))
try:
    with isolated_vault(root=iso_root, keep=True) as root:
        check("isolated_vault: yields the root", Path(root) == iso_root)
        check("isolated_vault: RuntimeContext root redirected",
              runtime_context.PROJECT_ROOT == iso_root)
        check("isolated_vault: save_memory dir under root",
              str(memory_writer.MEMORIES_DIR).startswith(str(iso_root)))
        check("isolated_vault: retrieval index vault under root",
              str(context_builder._index.vault).startswith(str(iso_root)))

        # A distillation write lands inside the isolated vault, not the real one.
        saved_path = runtime_context.RuntimeContext().knowledge.write(
            "iso_probe.md", "probe"
        )
        check("isolated_vault: knowledge write lands in isolated vault",
              str(saved_path).startswith(str(iso_root)))

        # save_memory also lands inside the isolated memories dir.
        mem_path = memory_writer.save_memory("iso_probe", "probe")
        check("isolated_vault: save_memory lands in isolated dir",
              str(mem_path).startswith(str(iso_root)))

    # After the context exits, every patched global is restored.
    check("isolated_vault: RuntimeContext root restored",
          runtime_context.PROJECT_ROOT == _orig[0])
    check("isolated_vault: MEMORIES_DIR restored",
          memory_writer.MEMORIES_DIR == _orig[1])
    check("isolated_vault: retrieval index restored",
          context_builder._index is _orig[2])
finally:
    shutil.rmtree(iso_root, ignore_errors=True)
    # Defensive: ensure globals are restored even if an assertion above raised.
    runtime_context.PROJECT_ROOT, memory_writer.MEMORIES_DIR, context_builder._index = _orig


# ---- distillation gate (benchmark hygiene) --------------------------------
from core.distillation_gate import distillation_enabled, distillation_suppressed

check("gate: enabled by default", distillation_enabled() is True)
with distillation_suppressed():
    check("gate: suppressed inside context", distillation_enabled() is False)
check("gate: restored after context", distillation_enabled() is True)

# Exception-safe restore.
try:
    with distillation_suppressed():
        raise RuntimeError("boom")
except RuntimeError:
    pass
check("gate: restored after exception", distillation_enabled() is True)

# Nested: inner exit must not re-enable while the outer is still active.
with distillation_suppressed():
    with distillation_suppressed():
        pass
    check("gate: still suppressed after inner exits", distillation_enabled() is False)
check("gate: restored after nested contexts", distillation_enabled() is True)


print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
