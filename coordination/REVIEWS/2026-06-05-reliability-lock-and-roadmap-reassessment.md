# Reliability Lock + Delegate Investigation + Roadmap Reassessment

- **Author:** Claude (Executor)
- **Date:** 2026-06-05
- **HEAD at measurement:** `07fa86c` (bypass) — no code changed for these measurements.
- **Scope:** measure only. No architecture built. Stop after, reassess.

---

## 1. Reliability number — LOCKED (clean-cloud run)

Probed cloud health (8/8 OK), then ran Engineering K=3 with per-trial breaker reset:

| Case | Pipeline score | Calls | Latency | Infra |
| :--- | :---: | :---: | :---: | :---: |
| engineering_latency | 1.00 | 2.0 | 11.0 s | 0/3 |
| engineering_dedupe | 1.00 | 2.0 | 8.5 s | 0/3 |
| engineering_balanced | 1.00 | 2.0 | 10.1 s | 0/3 |
| engineering_merge_intervals | 1.00 | 2.0 | 9.9 s | 0/3 |
| **Category** | **1.00** | **2.0** | **9.9 s** | **0/12** |

**The reliability number is 0/12 infra failures with healthy cloud.** The earlier
5/12 and 8/12 were entirely transient Ollama-cloud `502 Bad Gateway` outages, now
confirmed external (this run: 36 cloud generations, zero cloud failures).

### Full arc (V1 → now), Engineering, score held at 1.00 throughout

| | Calls/case | Latency/case | Infra |
| :--- | :---: | :---: | :---: |
| V1 (all-planner) | 16.8 | 950 s | 7/12 |
| CU6 (all-planner) | 14.5 | 312 s | 8/12 (502-contaminated) |
| **Bypass (clean)** | **2.0** | **9.9 s** | **0/12** |

Net: **−88% calls, −99% latency, infra → 0, quality unchanged.** Week-1 + bypass
delivered a system that takes the cheapest sufficient path and is reliable on it.

---

## 2. Delegate investigation — retrieval delegate is pure tax on self-contained coding

Throwaway A/B (uncommitted, deleted): development-agent WITH vs WITHOUT the
retrieval delegate, Engineering K=3, isolated vault, local timeout bounded to 25 s.

| Arm | Score | Successful calls | Wall-clock | Infra | Local-delegate failures |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **A — WITH delegate (current)** | 1.00 | 2.0 | **41.2 s** | 0/12 | **12/12** |
| **B — WITHOUT delegate** | 1.00 | 2.0 | **13.3 s** | 0/12 | 0 |

**Findings:**
- **Quality identical (1.00 = 1.00).** Retrieval added nothing to correctness.
- **Successful call count identical (2.0 = 2.0).** The 2 calls are development-agent's
  own *generation + distillation* — the retrieval delegate produced **zero** successful
  calls (it failed on local 12/12). So retrieval is not even one of the counted calls.
- **Latency: 41.2 s → 13.3 s — the delegate adds ~28 s/task (~3.1×), pure waste.** And
  that is with the local timeout bounded to 25 s for the experiment; in production the
  local timeout is **120 s**, so the real tax on a self-contained coding task is up to
  ~120 s of a guaranteed-useless, failing retrieval call.
- **CU6 keeps it non-fatal** (infra 0 in both arms) — but non-fatal is not free.

**Conclusion:** for *self-contained* coding tasks (full spec in the prompt, empty/irrelevant
vault), the retrieval delegate is latency tax with zero quality or reliability benefit.

**Honest caveats:**
- Measured on self-contained coding against an empty isolated vault. On a **real vault with
  relevant prior knowledge**, retrieval could add value (e.g. "build X consistent with our
  existing patterns"). So any change must be **conditional** (skip for self-contained tasks),
  not a blanket removal — and must preserve the privacy pin (retrieval stays sensitive→local).
- The delegate failed because local was unhealthy this session; with healthy local it would
  *succeed* and still add a call + latency for no coding benefit. Either way: cost, no gain.

---

## 3. Roadmap reassessment

### Where we actually are (evidence, not intuition)
- The single-call baseline solves every Engineering task at 1.00. **Orchestration adds no
  lift on this set** — its value is cost/latency/reliability, which the bypass now delivers.
- The system's defensible thesis is confirmed: **"spend the least sufficient amount, take
  the cheapest path, escalate only on evidence."** Not "more agents = smarter."
- Reliability is solved for the common path (infra 0 clean). Remaining costs are: (a) the
  retrieval-delegate tax (above), (b) per-task distillation = a 2nd cloud call on every
  direct run (the CU7 item), (c) external cloud flakiness (not ours).

### What is proven / done
- Routing hardening (CU1–CU5), failure isolation (CU6), planner bypass — all measured.
- Reliability number locked at 0/12 (clean).

### What remains justified, by evidence
1. **Conditional retrieval-delegate skip for self-contained tasks** — directly measured
   ~3× latency win, zero quality cost. **Smallest, highest-certainty next change.** (Not
   built — investigation only, per instruction.)
2. **CU7 distillation policy** — every direct coding run still does a 2nd cloud call to
   distill throwaway output. On the bypass path this is now half the call cost. Revisit.
3. **Benchmark V2 (headroom cases)** — still the gate for ANY claim that orchestration
   helps. The current set cannot show lift OR detect over-bypass regressions. Until V2,
   we cannot justify re-investing in the planner/multi-agent path.

### What is NOT justified yet (hold)
- Any new orchestration, agents, verification systems, or planner rework — the benchmark
  shows no task where they'd help. Build the V2 cases first; let evidence decide.

### Recommendation
**Pause architecture work here.** Two concrete, low-risk, evidence-backed candidates remain
(conditional delegate skip; CU7 distillation), but the higher-leverage move is **Benchmark
V2** — without headroom cases every further orchestration decision is unmeasurable. Decide
V2 vs the two cleanups next; do not expand the architecture until then.
