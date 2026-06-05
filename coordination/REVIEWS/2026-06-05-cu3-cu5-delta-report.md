# Delta Report — Engineering Sweep after CU3–CU5 (reliability hardening)

- **Author:** Claude (Executor)
- **Date:** 2026-06-05
- **Compares:** V1 sweep (commit `86adbd6`, 2026-06-04) vs hardened sweep (commit `7fa22de`)
- **Conditions:** identical — K=3, Engineering only, isolated vault, cloud reachable. Trace-to-file enabled.

## Headline

CU1/CU2/CU3 worked exactly as designed: **pipeline latency fell 81% (950s → 184s/case).**
CU4/CU5 did **not** move the infra-failure rate (7/12, unchanged) — because the residual
failures are an *architectural* path that routing hardening deliberately cannot touch.
Lift is still **zero** (1.00 = 1.00) — expected, the tasks still have no headroom.

## The numbers

| Metric (Engineering, per-case) | V1 | Hardened | Δ |
| :--- | :---: | :---: | :--- |
| Baseline score | 1.00 | 1.00 | — |
| Pipeline score | 1.00 | 1.00 | — |
| Raw lift | 0.00 | 0.00 | — |
| **Pipeline latency** | **950.7 s** | **183.5 s** | **−81% (5.2× faster)** |
| Baseline latency | 4.4 s | 6.2 s | +1.8 s (noise) |
| Pipeline calls | 16.8 | 15.2 | −1.6 |
| Extra tokens | 57,452 | 39,796 | −31% |
| **Infra failures** | **7 / 12** | **7 / 12** | **unchanged** |
| Earns its cost? | ❌ NO | ❌ NO | — |

Per-case infra pattern is identical to V1: `parse_latency` 3/3 fail, `merge_intervals` 3/3
fail, `is_balanced` 1/3, `dedupe` 0/3.

## Routing behavior (now observable — this is new)

From `runtime/trace.jsonl` (132 records):

- **104 successful generations: 103 cloud, 1 local.** Cloud-pinning + complexity routing
  put essentially all real work on cloud.
- **11 provider failures — every one a `read timeout=120` and every one `sensitive=true`**
  (i.e. the local-only path).
- **17 canned outcomes — every one `sensitive=true`.** Agent attribution: 17/17 canned
  outputs are preceded by the `RETRIEVAL-AGENT` header.

## Root cause of the residual 7/12 failures

`retrieval-agent` is `sensitive = True` (it reads the knowledge vault) → **pinned local-only,
correctly, by the privacy boundary.** `development-agent` also delegates to it. On these
coding tasks the planner inserts retrieval steps; the local 4B model stalls on them; CU3
now sheds local after **one** 120 s timeout (down from 3× 600 s) — which is exactly why
latency collapsed — but once the local breaker is open, every subsequent *sensitive* call
returns the canned string immediately (no cloud fallback is allowed for sensitive work).
That canned output is then threaded forward and flags the trial as infra.

So:
- **CU4 cannot help** — cloud-pinning must never override `sensitive` (that would leak
  private vault data to cloud in real use).
- **CU5 cannot help** — the output is *canned* (an honest "all providers down" sentinel,
  already correctly flagged as infra), not a *degenerate* model loop.
- **CU3 helped a lot on latency** (fast shed) but a fast failure is still a failure.

**Routing hardening has hit its ceiling for this metric.** The remaining failures are not a
routing problem.

## What the evidence forces us to conclude (challenging assumptions)

1. **The dominant failure is over-decomposition, not routing.** The planner routes
   self-contained coding subtasks through a vault-retrieval agent that (a) has nothing to
   retrieve here (empty isolated vault — it produced "Memory: empty" analyses) and (b) is
   the single failure source. This is the same over-decomposition the post-Phase-A review
   flagged, now quantified as the #1 reliability driver.
2. **Do NOT "fix" this by un-marking retrieval-agent sensitive.** That pin is correct in
   production (the agent can surface private notes). The benchmark's empty vault makes the
   pin look pointless, but removing it would leak private data in real use. The fix is
   architectural, not a privacy downgrade.
3. **The highest-value next reliability item is CU6 (failure isolation).** If a canned/failed
   subtask were isolated — skipped, not threaded into the merge — then `dedupe`-style trials
   would survive a retrieval stall instead of being poisoned. CU6 (+ eventually the planner
   gate) is where the 7/12 → <2/12 win lives. That is **out of the approved CU3–CU5 scope**,
   so it is flagged, not done.

## Benchmark trustworthiness — improved, still gated

- **Better:** latency is no longer dominated by 10-minute stalls; routing is fully
  observable; every failure is now explained and attributable to a single agent's privacy
  pin (not random outages). The score signal (zero lift) is unchanged and now better
  understood.
- **Still gated:** the pipeline arm still loses 7/12 trials, so it is partly measuring an
  architectural failure rather than quality. The harness excludes infra trials from the
  score means, so the *score* is sound — but a clean V2 needs CU6 first, or it will keep
  measuring the retrieval-agent stall.

## Recommendation

Stop routing work — it is done for this metric. Before Benchmark V2:
1. **CU6 (failure isolation)** — the real lever for the infra rate.
2. **Planner gate** (don't decompose self-contained coding tasks into a retrieval pipeline)
   — the durable fix; addresses cost *and* failure together.

Both are beyond the approved CU3–CU5 scope. Awaiting direction.
