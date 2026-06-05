# Live Lift Sweep — Engineering (objective signal), K=3

- **Author:** Claude (Executor)
- **Date:** 2026-06-05
- **Pipeline:** canonical `PlannerAgent` (decompose → PlanExecutor → SharedExecutionContext → merge)
- **Baseline:** one strong single cloud call (`qwen3-coder:480b-cloud`)
- **Isolation:** ON — all writes + reads redirected to a throwaway `runtime/benchmark_vault`
- **Report data:** `runtime/lift_report.md`, `runtime/lift_reports.json`

## What was built first
`core/eval/benchmark_vault.py` — an `isolated_vault()` context manager that, for the
duration of a run, redirects the three pollution/leak points to a throwaway dir and
restores them after: (1) distillation + state/memory via `runtime_context.PROJECT_ROOT`,
(2) `save_memory` via `memory_writer.MEMORIES_DIR`, (3) retrieval via a fresh
`context_builder._index` over the empty isolated vault. `run_benchmark` gained a
`categories` filter and `isolate=True` default. +9 offline tests (lift suite 31 → 40);
`run_tests.py` 10/10, 295 → 304 checks.

**Isolation verified live:** real vault unchanged at 5 notes / 3 memories; the throwaway
vault absorbed **28 distilled notes** that would otherwise have polluted it.

## Headline result — ZERO lift, large negative cost

| Metric (Engineering, per-case avg) | Baseline | Pipeline |
| :--- | :---: | :---: |
| Score (infra errors excluded) | **1.00 ± 0.00** | **1.00 ± 0.00** |
| Raw lift | — | **0.00** (not significant) |
| LLM calls | 1.0 | **16.8** |
| Latency | 4.4 s | **950.7 s** (~215×) |
| Extra tokens | — | **+57k / case** |
| Infra-failure rate (of 12 trials) | **0 / 12** | **7 / 12 (58%)** |
| **Earns its cost?** | — | **❌ NO** |

Per case: `dedupe` and `is_balanced` → pipeline matched baseline (1.00 = 1.00, 0 lift).
`parse_latency` and `merge_intervals` → **all 3 pipeline trials died as infra errors**
(local-model timeout / canned fallback), scoring 0.

## Why (root causes, not just numbers)
1. **Grader saturation = no headroom.** A single strong cloud call already scores a
   perfect 1.00 on every one of these well-specified function-writing tasks. There is
   nothing for orchestration to improve. These cases **cannot show positive lift** — the
   ceiling is already hit by the baseline.
2. **Orchestration is strictly worse on cost here:** ~16× the calls, ~215× the latency,
   +57k tokens — to reproduce a result the baseline gets in one 4-second call.
3. **Orchestration *introduces* failure modes the baseline avoids.** 58% of pipeline
   trials failed as infra errors vs 0% baseline:
   - The local floor `qwen3.5:4b` enters **catastrophic repetition loops** on the
     "Return ONLY the markdown block" subtasks (hundreds of `Wait, I need to make sure I
     don't add any Widths/Lengths…` lines → `[NO FINAL ANSWER GENERATED]`) and hits the
     **600 s read timeout**. When a decomposed subtask fails over cloud→local, the timeout
     kills the whole trial.
   - **Decomposition misroutes** trivial "write a function" goals to `retrieval-agent` /
     `research-agent` / `content-agent`, which over-analyze a one-line task into a 6-step,
     19-call plan.

## Verdict
The benchmark did exactly its job: it **refused to credit orchestration with lift it did
not earn.** On well-specified, single-shot engineering tasks, the canonical pipeline
delivers **no quality gain at ~16× cost and 58% added failure risk.** This is a real,
trustworthy (objective-grader) negative result — not a measurement artifact.

This does **not** prove orchestration is useless. It proves these **tasks have no
headroom**: a single 480B cloud call saturates them. Lift, if it exists, lives in tasks a
single call does *not* already nail.

## Next steps (recommended)
1. **Raise task difficulty until the baseline stops scoring 1.00.** Add objective
   engineering cases a single call genuinely fails (multi-file refactors, tasks needing
   iterative test-fix, long specs with interacting constraints). Only there can lift appear.
2. **Stop routing decomposed coding subtasks to the local thinking model.** Either cap
   local latency far below 600 s for benchmark/plan subtasks, force `prefer_cloud` inside
   PlanExecutor subtasks, or detect repetition-loop output and abort early.
3. **Fix decomposition routing** so a single self-contained "write function X" goal is NOT
   exploded into a research/retrieval/content pipeline (route trivial goals to one dev agent).
4. Keep Research/Architecture lift provisional until a cross-model judge (Phase D).
