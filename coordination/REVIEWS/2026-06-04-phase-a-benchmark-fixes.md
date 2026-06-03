# Review + Fix Report — Phase A Lift Benchmark Hardening

- **Author:** Claude (Executor)
- **Date:** 2026-06-04
- **Commit:** `714b017` (code) — supersedes the uncommitted Phase-A state
- **Status:** Done, 10/10 suites / 295 checks green

## Why
An independent review of `coordination/` vs the actual code found that the
Phase-A lift benchmark — the metric meant to **gate all future development** —
would have produced misleading numbers. Fixed before any lift run is trusted.

## Findings → fixes

| # | Finding | Fix | File |
|---|---|---|---|
| 1 | **Benchmark measured the wrong pipeline** — `pipeline_runner` used the bare DAG `Planner`, which uses none of Phase 4/5/5.1 (`SharedExecutionContext`, structured reasoning). It contradicted principles #6/#7. | Pipeline now runs the canonical `PlannerAgent` (→ PlanExecutor → SharedExecutionContext). | `lift_benchmark.py` |
| 2 | **Graders too weak** — 4/5 categories used 3-keyword `contains`/schema graders a single call satisfies trivially → false "no lift". | +3 objective sandbox-code cases; every case tagged `signal` (objective/numeric/structural/shallow); shallow graders strengthened and explicitly marked non-quality. | `benchmark_cases.jsonl` |
| 3 | **Gate ignored variance** — `earns_cost = lift > 0` while `std` was computed but unused. | Significance gate: `raw_lift > SIGNIFICANCE_K·SE` **and** cost-adjusted lift > 0. | `lift_benchmark.py` |
| 4 | **Cost = call-count only** — conflates a 480B cloud call with a 4B local call. | Report cost-adjusted lift by calls, by tokens (per-1k), and latency separately. | `lift_benchmark.py` |
| 5 | **Infra failures contaminated lift** — an exception/canned-fallback scored 0 and dragged the pipeline mean. | Infra failures flagged (`infra_error`) and excluded from score means; counted in the report. | `lift_benchmark.py` |
| 6 | **Snapshot cited a commit that didn't contain the benchmark** (`4bf6db0`); two divergent `CURRENT_SYSTEM_STATE.md` and two roadmaps. | Committed the feature (`714b017`); rewrote the canonical snapshot to cite it; removed the root duplicate; `coordination/ROADMAP.md` now points to the canonical `docs/ROADMAP.md`. | coordination/, docs/ |

## Verification
- `python run_tests.py` → **10/10 suites, 295 checks**, green.
- `test_lift_benchmark.py` → 31 checks (added: significance gate, infra exclusion, canned-fallback detection).
- Confirmed `run_benchmark` source contains `PlannerAgent` and no bare `Planner()`.

## Remaining limitations (honest)
- **Only Engineering/code cases give a trustworthy (objective) lift signal.** Research/Architecture remain `shallow` until a cross-model judge (Phase D) can score quality. The report tags this; weight conclusions accordingly.
- **The live benchmark pollutes the real vault** (`PlannerAgent.run()` distills). Needs an isolated benchmark vault before large runs — recommend before any K≥3 full sweep.
- Token cost is a `len(split)*1.33` estimate, not true tokenization.
- "Cost" today is really quota+latency (free cloud), not dollars — revisit at Phase D.

## Recommended next steps
1. Add an isolated vault for benchmark runs (avoid distillation pollution), then do a **live Engineering-only sweep** (objective signal) before trusting other categories.
2. Hold Research/Architecture lift as *provisional* until Phase D's cross-model judge.
3. Enforce the coordination rule now codified in the snapshot: *nothing is baseline until committed; one canonical doc per concern.*
