import json
import time
import math
import contextlib
from pathlib import Path

from core.llm_engine import _router, query_llm
from core.router import CANNED_FALLBACK
from core.distillation_gate import distillation_suppressed
from core.eval.graders import make_grader

SRC = Path(__file__).resolve().parents[2]
BENCHMARK_CASES = SRC / "core" / "eval" / "benchmark_cases.jsonl"
LIFT_REPORT_JSON = SRC.parent / "runtime" / "lift_reports.json"
LIFT_REPORT_MD = SRC.parent / "runtime" / "lift_report.md"

# A category "earns its cost" only when the raw lift clears the noise floor:
# raw_lift > SIGNIFICANCE_K * standard_error_of_the_difference. With non-
# deterministic model output and small K, a tiny positive lift inside the
# variance band is noise, not signal — the std must gate the verdict.
SIGNIFICANCE_K = 1.0


class BenchmarkCase:

    def __init__(self, spec):
        self.id = spec.get("id", "case")
        self.category = spec.get("category", "General")
        self.task = spec.get("task", "")
        self.kind = spec.get("grader", "contains")
        # Grader reliability — surfaced in the report so readers know which
        # categories carry an objective lift signal vs a shallow/keyword one.
        #   objective  -> sandbox-executed code (ground truth)
        #   numeric    -> single numeric answer
        #   structural -> schema/shape only
        #   shallow    -> keyword presence (does NOT measure quality)
        self.signal = spec.get("signal", "unknown")
        self.spec = spec
        self.grader = make_grader(spec)


def load_benchmark_cases():
    if not BENCHMARK_CASES.exists():
        print(f"Error: Cases file not found at {BENCHMARK_CASES}")
        return []
    cases = []
    for line in BENCHMARK_CASES.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            cases.append(BenchmarkCase(json.loads(line)))
        except Exception as e:
            print(f"Failed to load case line: {e}")
    return cases


def run_trial(case, runner_fn):
    # Reset router telemetry and run one trial.
    _router.telemetry.reset()
    _router.telemetry.active = True

    # Benchmark hygiene: reset every provider's circuit breaker so a trial never
    # inherits breaker state (e.g. a local breaker left OPEN by a prior trial),
    # which would make per-trial failure attribution order-dependent.
    for managed in _router.providers:
        managed.breaker.reset()

    score = 0.0
    output = ""
    error = None

    try:
        output = runner_fn(case.task)
        verdict = case.grader(case.task, output)
        score = float(verdict.score)
    except Exception as e:
        error = str(e)

    _router.telemetry.active = False

    # Infra failure (exception, or the router's all-providers-down canned
    # string) is NOT a quality signal. Flagged so it can be excluded from the
    # score means — a transient outage must not falsely depress the pipeline.
    infra_error = bool(error) or (
        isinstance(output, str) and CANNED_FALLBACK in output
    )

    return {
        "score": score,
        "calls": _router.telemetry.calls,
        "prompt_tokens": _router.telemetry.prompt_tokens,
        "completion_tokens": _router.telemetry.completion_tokens,
        "latency": _router.telemetry.latency,
        "error": error,
        "infra_error": infra_error,
    }


def mean_std(values):
    n = len(values)
    if n == 0:
        return 0.0, 0.0
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / max(1, n - 1)
    std = math.sqrt(variance)
    return mean, std


def _aggregate(trials):
    # Aggregate a list of trial dicts, EXCLUDING infra failures from the score
    # statistics (falling back to all trials only if every trial was infra).
    valid = [t for t in trials if not t.get("infra_error")]
    used = valid if valid else trials

    scores = [t["score"] for t in used]
    calls = [t.get("calls", 0) for t in used]
    tokens = [
        t.get("prompt_tokens", 0) + t.get("completion_tokens", 0) for t in used
    ]
    latency = [t.get("latency", 0.0) for t in used]

    score_mean, score_std = mean_std(scores)
    calls_mean, _ = mean_std(calls)
    tokens_mean, _ = mean_std(tokens)
    latency_mean, _ = mean_std(latency)

    return {
        "n": len(used),
        "infra_errors": len(trials) - len(valid),
        "score_mean": score_mean,
        "score_std": score_std,
        "calls_mean": calls_mean,
        "tokens_mean": tokens_mean,
        "latency_mean": latency_mean,
    }


def _lift_record(baseline, pipeline):
    # Compute lift + cost-adjusted lift (by calls AND by tokens) + latency delta
    # + a variance-aware significance flag, from two aggregate dicts.
    raw_lift = pipeline["score_mean"] - baseline["score_mean"]

    extra_calls = pipeline["calls_mean"] - baseline["calls_mean"]
    extra_tokens = pipeline["tokens_mean"] - baseline["tokens_mean"]
    extra_latency = pipeline["latency_mean"] - baseline["latency_mean"]

    cost_adjusted_lift = raw_lift / extra_calls if extra_calls > 0 else raw_lift
    lift_per_1k_tokens = (
        raw_lift / (extra_tokens / 1000.0) if extra_tokens > 0 else raw_lift
    )

    # Standard error of the difference of means.
    se = math.sqrt(
        (pipeline["score_std"] ** 2) / max(1, pipeline["n"])
        + (baseline["score_std"] ** 2) / max(1, baseline["n"])
    )
    significant = raw_lift > SIGNIFICANCE_K * se

    return {
        "baseline_score_mean": baseline["score_mean"],
        "baseline_score_std": baseline["score_std"],
        "pipeline_score_mean": pipeline["score_mean"],
        "pipeline_score_std": pipeline["score_std"],
        "baseline_calls_mean": baseline["calls_mean"],
        "pipeline_calls_mean": pipeline["calls_mean"],
        "baseline_latency_mean": baseline["latency_mean"],
        "pipeline_latency_mean": pipeline["latency_mean"],
        "raw_lift": raw_lift,
        "extra_calls": extra_calls,
        "extra_tokens": extra_tokens,
        "extra_latency": extra_latency,
        "cost_adjusted_lift": cost_adjusted_lift,
        "lift_per_1k_tokens": lift_per_1k_tokens,
        "standard_error": se,
        "significant": significant,
        "infra_errors": baseline["infra_errors"] + pipeline["infra_errors"],
    }


def analyze_results(results):
    categories = {}
    aggregated_cases = []

    for case_id, data in results.items():
        cat = data["category"]
        categories.setdefault(cat, {"baseline": [], "pipeline": []})

        b_agg = _aggregate(data["baseline"])
        p_agg = _aggregate(data["pipeline"])

        record = _lift_record(b_agg, p_agg)
        record["id"] = case_id
        record["category"] = cat
        record["signal"] = data.get("signal", "unknown")
        aggregated_cases.append(record)

        # Roll raw trials up to the category level.
        categories[cat]["baseline"].extend(data["baseline"])
        categories[cat]["pipeline"].extend(data["pipeline"])

    category_summary = []
    for cat, data in categories.items():
        b_agg = _aggregate(data["baseline"])
        p_agg = _aggregate(data["pipeline"])

        record = _lift_record(b_agg, p_agg)
        record["category"] = cat
        # Orchestration earns its cost only if the lift is BOTH statistically
        # above the noise floor AND positive per extra call.
        record["earns_cost"] = bool(
            record["significant"] and record["cost_adjusted_lift"] > 0.0
        )
        category_summary.append(record)

    return {
        "cases": aggregated_cases,
        "categories": category_summary,
        "significance_k": SIGNIFICANCE_K,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def save_reports(report):
    LIFT_REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    LIFT_REPORT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    md_lines = [
        "# Orchestration Lift Benchmark Report",
        f"Generated: {report['timestamp']}",
        f"Significance gate: raw_lift > {report.get('significance_k', 1.0)} x standard_error",
        "",
        "Pipeline = canonical PlannerAgent (SharedExecutionContext). "
        "Baseline = single strong cloud call.",
        "",
        "## Summary by Category",
        "",
        "| Category | Baseline Score | Pipeline Score | Extra Calls | "
        "Cost-Adjusted Lift | Significant | Earns Cost? |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]
    for c in report["categories"]:
        earns_str = "✅ YES" if c["earns_cost"] else "❌ NO"
        sig_str = "yes" if c["significant"] else "no (within noise)"
        md_lines.append(
            f"| {c['category']} | {c['baseline_score_mean']:.2f} ± {c['baseline_score_std']:.2f} | "
            f"{c['pipeline_score_mean']:.2f} ± {c['pipeline_score_std']:.2f} | "
            f"{c['extra_calls']:.1f} | {c['cost_adjusted_lift']:.3f} | {sig_str} | {earns_str} |"
        )

    md_lines.extend([
        "",
        "## Detailed Case Breakdown",
        "",
        "| Case ID | Category | Signal | Baseline | Pipeline | Raw Lift | "
        "Extra Calls | Lift/1k tok | Infra Errs |",
        "| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
    ])
    for c in report["cases"]:
        md_lines.append(
            f"| {c['id']} | {c['category']} | {c.get('signal', '?')} | "
            f"{c['baseline_score_mean']:.2f} ± {c['baseline_score_std']:.2f} | "
            f"{c['pipeline_score_mean']:.2f} ± {c['pipeline_score_std']:.2f} | "
            f"{c['raw_lift']:.2f} | {c['extra_calls']:.1f} | "
            f"{c['lift_per_1k_tokens']:.4f} | {c['infra_errors']} |"
        )

    md_lines.append("")
    md_lines.append(
        "> Trust order: `objective` (sandbox code) > `numeric` > `structural` "
        "> `shallow` (keyword presence — does NOT measure quality)."
    )

    LIFT_REPORT_MD.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"\nReports written to:\n- {LIFT_REPORT_JSON}\n- {LIFT_REPORT_MD}")


def run_benchmark(K=3, categories=None, isolate=True, keep_vault=False):
    # Imported here (not at module top) so the offline unit tests can import this
    # module without pulling the full agent stack.
    from core.eval.benchmark_vault import isolated_vault

    cases = load_benchmark_cases()

    # Optional category filter (e.g. ["Engineering"]) — lets us run only the
    # categories with a trustworthy `objective` grader signal.
    if categories:
        wanted = {c.lower() for c in categories}
        cases = [c for c in cases if c.category.lower() in wanted]

    print(f"Loaded {len(cases)} benchmark cases. Running {K} trials each...")
    if isolate:
        print("Vault isolation: ON (writes + reads redirected to a throwaway "
              "benchmark vault; the real vault is untouched).")

    # isolated_vault redirects all distillation/memory writes AND retrieval reads
    # to a throwaway directory so the pipeline (PlannerAgent.run) cannot pollute
    # or read the real vault. A no-op nullcontext when isolation is disabled.
    vault_cm = isolated_vault(keep=keep_vault) if isolate else contextlib.nullcontext()

    # Suppress distillation for the whole run (benchmark hygiene): the learning
    # loop is the only writer to the knowledge vault on a benchmark path, so
    # turning it off keeps the isolated vault empty -> no trial can pollute it or
    # retrieve another trial's distilled artifacts. Applies even when
    # isolate=False, so a benchmark run can never distil into the real vault.
    with vault_cm, distillation_suppressed():
        return _run_cases(cases, K)


def _run_cases(cases, K):
    results = {}

    for case in cases:
        print(f"\nRunning Case [{case.id}] ({case.category}, signal={case.signal})")

        # Run A — baseline: ONE strong single call (fair, well-formed prompt).
        def baseline_runner(task):
            prompt = f"""You are an advanced AI assistant performing a complex task.
Solve the task systematically and provide a complete, correct, and self-contained response.

Task:
{task}

Response:"""
            return query_llm(prompt, prefer_cloud=True)

        # Run B — the CANONICAL pipeline: dispatch() applies the cheapest
        # sufficient path (direct single agent by default; PlannerAgent only
        # when needs_planning() finds strong evidence). This measures the
        # planner-bypass system, not the planner in isolation.
        def pipeline_runner(task):
            from core.agent_engine import dispatch
            return dispatch(task)

        baseline_trials = [run_trial(case, baseline_runner) for _ in range(K)]
        pipeline_trials = [run_trial(case, pipeline_runner) for _ in range(K)]

        results[case.id] = {
            "id": case.id,
            "category": case.category,
            "signal": case.signal,
            "baseline": baseline_trials,
            "pipeline": pipeline_trials,
        }

    report = analyze_results(results)
    save_reports(report)
    return report


# ===========================================================================
# Benchmark V2 — additive parallel path (V1 above is untouched).
# Three arms (A baseline / B verified-single / C verified-planner), fractional
# objective grading on hidden tests, independent calibration, MDE + Holm.
# ===========================================================================

import random  # noqa: E402

LIFT_V2_JSON = SRC.parent / "runtime" / "lift_v2_reports.json"
LIFT_V2_MD = SRC.parent / "runtime" / "lift_v2_report.md"

# Pairwise comparisons: B-A (verification), C-B (decomposition), C-A (total).
V2_PAIRS = [("B", "A"), ("C", "B"), ("C", "A")]


def run_trial_v2(task, runner_fn, grader):
    # Like run_trial but: arm-agnostic (runner passed in), grades with the case's
    # fractional grader, and captures WALL-CLOCK (telemetry latency counts only
    # successful calls, so it understates the true cost of slow/failed paths).
    _router.telemetry.reset()
    _router.telemetry.active = True
    for managed in _router.providers:
        managed.breaker.reset()

    score = 0.0
    output = ""
    error = None

    t0 = time.time()
    try:
        output = runner_fn(task)
        score = float(grader(task, output).score)
    except Exception as e:
        error = str(e)
    wall = time.time() - t0

    _router.telemetry.active = False

    infra_error = bool(error) or (
        isinstance(output, str) and CANNED_FALLBACK in output
    )

    return {
        "score": score,
        "calls": _router.telemetry.calls,
        "prompt_tokens": _router.telemetry.prompt_tokens,
        "completion_tokens": _router.telemetry.completion_tokens,
        "latency": _router.telemetry.latency,
        "wall": wall,
        "error": error,
        "infra_error": infra_error,
    }


def _arm_aggregate(trials):
    valid = [t for t in trials if not t.get("infra_error")]
    used = valid if valid else trials

    score_mean, score_std = mean_std([t["score"] for t in used])
    calls_mean, _ = mean_std([t.get("calls", 0) for t in used])
    tokens_mean, _ = mean_std(
        [t.get("prompt_tokens", 0) + t.get("completion_tokens", 0) for t in used]
    )
    wall_mean, _ = mean_std([t.get("wall", 0.0) for t in used])

    return {
        "n": len(used),
        "infra_errors": len(trials) - len(valid),
        "score_mean": score_mean,
        "score_std": score_std,
        "calls_mean": calls_mean,
        "tokens_mean": tokens_mean,
        "wall_mean": wall_mean,
    }


def _one_sided_p(z):
    # P(Z >= z) for a standard normal.
    return 0.5 * math.erfc(z / math.sqrt(2))


_COST_KEY = {"wall": "wall_mean", "calls": "calls_mean", "tokens": "tokens_mean"}


def _pair_lift(hi, lo, k_sig, cost_axis):
    lift = hi["score_mean"] - lo["score_mean"]
    se = math.sqrt(
        (hi["score_std"] ** 2) / max(1, hi["n"])
        + (lo["score_std"] ** 2) / max(1, lo["n"])
    )
    if se > 0:
        z = lift / se
        p = _one_sided_p(z)
    else:
        z = float("inf") if lift > 0 else 0.0
        p = 0.0 if lift > 0 else 1.0

    cost_key = _COST_KEY[cost_axis]
    extra = hi[cost_key] - lo[cost_key]
    cost_adjusted = (lift / extra) if extra > 0 else lift

    return {
        "lift": lift,
        "se": se,
        "z": (None if z == float("inf") else z),
        "p": p,
        "mde": k_sig * se,           # smallest lift we could call significant
        "extra_cost": extra,
        "cost_adjusted": cost_adjusted,
        "significant_raw": (z >= k_sig),
    }


def analyze_v2(results, k_sig=2.0, cost_axis="wall"):
    from collections import defaultdict

    cases_out = []
    cat_trials = defaultdict(lambda: defaultdict(list))

    for cid, data in results.items():
        case_rec = {"id": cid, "category": data["category"], "arms": {}}
        for arm, trials in data["arms"].items():
            case_rec["arms"][arm] = _arm_aggregate(trials)
            cat_trials[data["category"]][arm].extend(trials)
        cases_out.append(case_rec)

    cat_out = []
    family = []   # all (category, pair) tests -> Holm corrected together
    for cat, arms in cat_trials.items():
        aggs = {a: _arm_aggregate(ts) for a, ts in arms.items()}
        pairs = {}
        for hi, lo in V2_PAIRS:
            if hi in aggs and lo in aggs:
                rec = _pair_lift(aggs[hi], aggs[lo], k_sig, cost_axis)
                pairs[f"{hi}-{lo}"] = rec
                family.append(rec)
        cat_out.append({"category": cat, "arms": aggs, "pairs": pairs})

    # Holm-Bonferroni step-down over the whole family (one-sided alpha from k_sig).
    alpha = _one_sided_p(k_sig)
    m = len(family)
    stop = False
    for i, rec in enumerate(sorted(family, key=lambda r: r["p"])):
        thresh = alpha / (m - i) if (m - i) > 0 else alpha
        sig = (not stop) and (rec["p"] <= thresh)
        if not sig:
            stop = True
        rec["holm_threshold"] = thresh
        rec["significant_holm"] = sig
        rec["earns_cost"] = bool(sig and rec["cost_adjusted"] > 0.0)

    return {
        "cases": cases_out,
        "categories": cat_out,
        "k_sig": k_sig,
        "cost_axis": cost_axis,
        "alpha": alpha,
        "family_size": m,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def save_reports_v2(report):
    LIFT_V2_JSON.parent.mkdir(parents=True, exist_ok=True)
    LIFT_V2_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Benchmark V2 Report",
        f"Generated: {report['timestamp']}",
        f"k_sig={report['k_sig']} (one-sided alpha={report['alpha']:.4f}), "
        f"cost_axis={report['cost_axis']}, Holm family={report['family_size']}",
        "",
        "Arms: A=baseline | B=verified-single | C=verified-planner "
        "(verification identical in B and C).",
        "",
        "| Category | Pair | Lift | MDE | Cost-adj | Holm sig | Earns cost? |",
        "| :--- | :--- | :---: | :---: | :---: | :---: | :---: |",
    ]
    for c in report["categories"]:
        for name, r in c["pairs"].items():
            lines.append(
                f"| {c['category']} | {name} | {r['lift']:.3f} | {r['mde']:.3f} | "
                f"{r['cost_adjusted']:.3f} | "
                f"{'yes' if r['significant_holm'] else 'no'} | "
                f"{'✅ YES' if r['earns_cost'] else '❌ NO'} |"
            )
    lines.append("")
    lines.append("> A null result (no pair earns cost) is a valid, expected outcome: "
                 "it means the cheaper arm wins. 'no Holm sig' with lift < MDE means "
                 "underpowered, not necessarily zero lift.")
    LIFT_V2_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nV2 reports written to:\n- {LIFT_V2_JSON}\n- {LIFT_V2_MD}")


def run_calibration(cases, K=5, ceiling=0.9, floor=0.1, max_std=0.35,
                    seed=0, isolate=True, keep_vault=False):
    # INDEPENDENT calibration: arm A only. ELIMINATES obvious ceiling/floor/
    # high-variance cases (no mid-band selection -> no regression-to-mean bias).
    # These trials are NOT reused by run_v2 (the deciding run draws fresh trials).
    from core.eval.arms import ARMS
    from core.eval.benchmark_vault import isolated_vault

    vault_cm = isolated_vault(keep=keep_vault) if isolate else contextlib.nullcontext()
    rows = []
    with vault_cm, distillation_suppressed():
        for case in cases:
            grader = make_grader(
                {"grader": "fractional_code", "hidden_tests": case["hidden_tests"]}
            )
            pub = case["public_tests"]
            trials = [
                run_trial_v2(case["task"], (lambda t, p=pub: ARMS["A"](t, p)), grader)
                for _ in range(K)
            ]
            agg = _arm_aggregate(trials)
            if agg["score_mean"] >= ceiling:
                verdict = "drop:ceiling"
            elif agg["score_mean"] <= floor:
                verdict = "drop:floor"
            elif agg["score_std"] >= max_std:
                verdict = "drop:high-variance"
            else:
                verdict = "keep"
            rows.append({
                "id": case["id"],
                "baseline_mean": agg["score_mean"],
                "baseline_std": agg["score_std"],
                "infra_errors": agg["infra_errors"],
                "verdict": verdict,
            })

    return {
        "k_cal": K,
        "thresholds": {"ceiling": ceiling, "floor": floor, "max_std": max_std},
        "cases": rows,
        "kept": [r["id"] for r in rows if r["verdict"] == "keep"],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def run_v2(cases, K=8, arms=("A", "B", "C"), k_sig=2.0, cost_axis="wall",
           seed=0, isolate=True, keep_vault=False):
    # Deciding run. Arm execution order is RANDOMIZED per trial so a transient
    # outage cannot systematically bias one arm. Fresh trials (never the
    # calibration ones).
    from core.eval.arms import ARMS
    from core.eval.benchmark_vault import isolated_vault

    rng = random.Random(seed)
    results = {}
    vault_cm = isolated_vault(keep=keep_vault) if isolate else contextlib.nullcontext()

    with vault_cm, distillation_suppressed():
        for case in cases:
            grader = make_grader(
                {"grader": "fractional_code", "hidden_tests": case["hidden_tests"]}
            )
            pub = case["public_tests"]
            per_arm = {a: [] for a in arms}
            for _ in range(K):
                order = list(arms)
                rng.shuffle(order)
                for a in order:
                    runner = (lambda t, _a=a, p=pub: ARMS[_a](t, p))
                    per_arm[a].append(run_trial_v2(case["task"], runner, grader))
            results[case["id"]] = {
                "id": case["id"],
                "category": case["category"],
                "arms": per_arm,
            }

    report = analyze_v2(results, k_sig=k_sig, cost_axis=cost_axis)
    save_reports_v2(report)
    return report


if __name__ == "__main__":
    # Usage: python -m core.eval.lift_benchmark [K] [Category[,Category...]] [--keep-vault]
    #   K           number of trials per case (default 3)
    #   Category    comma-separated category filter, e.g. Engineering
    #   --keep-vault leave the isolated benchmark vault on disk for inspection
    import sys

    args = [a for a in sys.argv[1:] if a != "--keep-vault"]
    keep = "--keep-vault" in sys.argv

    K_val = 3
    cats = None
    for a in args:
        if a.isdigit():
            K_val = int(a)
        else:
            cats = [c.strip() for c in a.split(",") if c.strip()]

    run_benchmark(K=K_val, categories=cats, keep_vault=keep)
