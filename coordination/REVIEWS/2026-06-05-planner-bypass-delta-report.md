# Delta Report — Planner Bypass (Engineering sweep)

- **Author:** Claude (Executor)
- **Date:** 2026-06-05
- **Implementation:** commits `0ceb54e` (bypass) + `07fa86c` (benchmark wiring)
- **Compares:** CU6 run (`ec95a63`, all-planner pipeline) vs bypass run (`dispatch()` pipeline)
- **Conditions:** K=3, Engineering, isolated vault, per-trial breaker reset, trace-to-file.
- **Caveat up front:** the Ollama cloud endpoint was intermittently throwing `502 Bad
  Gateway` throughout this session. Two bypass runs were done; the first was heavily
  contaminated (cloud outage hit both arms). Numbers below are the cleaner second run,
  but infra is still partly masked by transient 502s — flagged explicitly.

## Numbers

| Metric (Engineering, per-case) | V1 | CU6 (all-planner) | Bypass | vs CU6 |
| :--- | :---: | :---: | :---: | :---: |
| Baseline score | 1.00 | 1.00 | 1.00 | — |
| Pipeline score | 1.00 | 1.00 | 1.00 | — |
| **Pipeline calls** | 16.8 | 14.5 | **2.0** | **−86%** |
| **Pipeline latency** (successful-call telemetry) | 950 s | 312 s | **12.5 s** | **−96%** |
| Extra calls over baseline | 15.8 | 13.5 | **1.0** | — |
| Pipeline infra failures | 7/12 | 8/12 | **5/12** | masked by 502s |
| Raw lift | 0.00 | 0.00 | 0.00 | — (no headroom) |
| Earns cost? | ❌ | ❌ | ❌ | — |

## What the bypass did (verified from trace, outage-independent)

- **Every pipeline trial routed directly to development-agent at 2 calls.** Zero
  decomposition. The old failure mode — coding tasks fanned out to research/retrieval
  agents — is **gone**. (Trace: 27 cloud-ok generations, no plan-step pattern; the route
  fix sends `function/implement/python/...` to development-agent.)
- **Orchestration tax collapsed:** 15.8 → **1.0** extra call over the single-call
  baseline. The pipeline is now nearly as cheap as one direct call.
- **Score held at 1.00** on every healthy trial.

## Honest read of the residual infra (5/12)

Not a structural OIL failure — two external/known causes:
1. **Transient cloud `502 Bad Gateway`** on the development-agent's own call (the session
   was flaky; a 5-call probe passed but 502s recurred during the run). These 5 cloud
   failures == the 5 infra trials.
2. **Sensitive retrieval delegate on local** (12 `["ollama-local"]` canned): development
   -agent delegates to retrieval-agent (sensitive → local-only, correctly) on every run;
   local times out. **CU6 absorbs these** (delegate returns ""), so they are a
   cost/latency tax, NOT trial-fatal. The privacy pin is intact and must stay.

So the dominant CU6-era failure driver (over-decomposition) is eliminated; what remains
is (a) an external cloud outage and (b) a known, non-fatal local-retrieval tax.

## Did the bypass deliver measurable value? — Honest assessment

**Yes, decisively, on its actual objective (cheapest sufficient path):**
- Call count **−86%** (14.5 → 2.0); extra-over-baseline **15.8 → 1.0**. Structural,
  outage-independent.
- Decomposition failure mode **eliminated** — the thing CU6 proved was the dominant
  remaining failure source.
- Latency **−96%** on healthy trials (caveat: telemetry latency counts only successful
  calls, so it understates wall-clock when failures occur; treat as indicative, not exact).
- Score unchanged at **1.00**.

**What it did NOT do (and was never meant to):**
- It adds **no lift** (still 0.00) — correct; the baseline already saturates these tasks.
  The bypass's value is *cost/latency/reliability*, not quality.
- It does **not** fully clean the infra number this session — transient cloud 502s mask it.
  A clean infra read needs a run during a healthy cloud window.

## Residual smell (flagged, NOT fixed — out of scope)

development-agent delegates to retrieval-agent (local-only) on **every** call, including
self-contained coding tasks that need no retrieval. CU6 makes it non-fatal, but it's pure
tax (12 local timeouts this run). Candidate next step: let development-agent skip the
retrieval delegate for self-contained tasks. **Not implemented** (no scope expansion).

## Recommendation

1. The bypass is a clear, measured win on cost and on eliminating the decomposition
   failure mode. Keep it.
2. Re-measure infra during a healthy-cloud window for a clean number (the benchmark is
   the authority; this session's cloud flakiness is the confound, now visible in the trace).
3. Do not expand further until Benchmark V2 (headroom cases) — the current set has no task
   where planning helps, so it cannot detect over-bypass regressions.
