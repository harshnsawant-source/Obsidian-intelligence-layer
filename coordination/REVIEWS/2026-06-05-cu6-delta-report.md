# Delta Report — Engineering Sweep after CU6 (failure isolation)

- **Author:** Claude (Executor)
- **Date:** 2026-06-05
- **Compares:** CU3–CU5 run (commit `7fa22de`) vs CU6 run (commit `ec95a63`)
- **Conditions:** identical — K=3, Engineering, isolated vault, cloud reachable, trace-to-file.

## Headline (honest)

**CU6 did not move the benchmark** — and the trace explains exactly why, in a way
that *confirms* the next step rather than undermining CU6.

| Metric (Engineering, per-case) | CU3–CU5 | CU6 | Note |
| :--- | :---: | :---: | :--- |
| Baseline score | 1.00 | 1.00 | — |
| Pipeline score | 1.00 | 1.00 | zero lift (no headroom) |
| Infra failures | 7 / 12 | **8 / 12** | within noise (one trial flipped) |
| Pipeline latency | 183.5 s | 311.7 s | ↑ — but this is variance, not regression (see below) |
| Baseline latency | 6.2 s | 7.6 s | cloud was ~23% slower this run |
| Pipeline calls | 15.2 | 14.5 | ~same |
| Earns cost? | ❌ NO | ❌ NO | — |

## Why CU6 didn't move it — and why that's the right result

From the trace (132 records) + run log:

1. **CU6's PlanExecutor isolation never fired** (0 "isolated, not threaded" log
   lines). The plans did not schedule the failing retrieval as a *top-level step*.
2. **The retrieval failures came through the DELEGATE path** (development → retrieval),
   which CU6 *does* absorb — silently and correctly (returns "" instead of injecting
   canned text). So CU6's delegate guard is working; it just produces no log and no
   visible benchmark delta.
3. **The trials fail for a reason upstream of CU6:** the planner routed the
   self-contained coding tasks to **non-code agents**. `parse_latency` and
   `merge_intervals` decomposed entirely to **research-agent**; `dedupe` ran a
   **retrieval-agent** step that returned canned. CU6 can stop a failed step from
   *poisoning* a run — it cannot *manufacture code* from a research agent. There was
   no working code to rescue.
4. **A persistent circuit-breaker confound:** the `_router` is a shared singleton and
   `run_trial` resets telemetry but **not** breaker state. The first case's retrieval
   timeouts open the local breaker; that state bleeds into later cases, so every
   subsequent *sensitive* (local-only) retrieval call returns canned immediately
   (4 canned records had `providers_tried: []` = breaker open, 0 calls). This makes
   per-case infra **order-dependent** — a measurement artifact, not only a system trait.

Routing remained healthy where it mattered: **88/90 successful generations on cloud**,
all 9 failures were the local 120 s timeout on sensitive retrieval.

## On the latency increase (184 → 312 s)

Not a CU6 regression. Baseline latency *also* rose (6.2 → 7.6 s), so cloud was slower
this run. The category mean is dominated by which cases *pass*: passing cases run the
full ~15-call pipeline (dedupe 314 s, balanced 309 s this run vs 150/233 before);
failing cases bail in ~80 s. With K=3 and high cloud variance, this number is noisy and
should not be over-read.

## What this proves

- **CU6 is correct and necessary** (15 unit tests; isolation + delegate guard +
  degraded recording all proven). It is the safety net that stops a failed step from
  poisoning the merge — and the delegate guard is exercised live in this very run.
- **CU6 is provably NOT sufficient** to fix the benchmark, *because the failure is
  upstream of it*: the planner sends self-contained coding tasks to research/retrieval
  agents that cannot produce code. This is the over-decomposition / mis-routing the
  post-Phase-A review named — now demonstrated to be THE remaining failure driver.
- **This is the green light for the planner bypass:** route a self-contained coding
  task directly to `development-agent` (cloud-pinned), skipping the decomposition that
  produces no code and trips the local stalls. That is the next authorized step.

## Recommendations

1. **Proceed to the planner bypass** (authorized) — it targets the actual cause.
2. **Reset circuit-breaker state per trial** in the benchmark harness so per-case infra
   is not order-dependent. (Harness hygiene; fold into the bypass measurement or V2.)
3. Continue to treat latency at K=3 as indicative, not precise.
