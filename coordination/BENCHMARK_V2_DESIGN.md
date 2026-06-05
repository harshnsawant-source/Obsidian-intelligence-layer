# Benchmark V2 — Design Document (design review only; nothing implemented)

- **Author:** Claude (Executor)
- **Date:** 2026-06-05
- **Status:** DESIGN ONLY. No code. Defines the evidence required before any future
  orchestration/architecture work is justified.
- **Builds on:** `src/core/eval/lift_benchmark.py` (run_trial, _lift_record significance
  gate, signal tags), `graders`, `sandbox`, `benchmark_vault.isolated_vault`, per-trial
  breaker reset.

---

## 0. Why V2 (evidence recap)

V1 and the Phase-A sweeps proved one thing decisively: **the single-call baseline already
scores 1.00 on every current task, so the benchmark has no headroom and cannot detect lift
either way.** Every "zero lift" result so far is a ceiling artifact, not evidence that
orchestration is worthless. V2's entire purpose is to **create headroom** and then let the
data decide — including the power to return a clean null result.

**Falsifiability is the design goal.** V2 must be able to conclude "orchestration earns
nothing" *and* "verification earns X, decomposition earns Y" with equal rigor.

---

## 1. Core design: three arms, two isolated mechanisms

Every kept case is run under three arms so the two distinct orchestration mechanisms are
separated:

| Arm | What it runs | Isolates |
| :--- | :--- | :--- |
| **A — Baseline** | one strong single cloud call (well-engineered prompt) | reference |
| **B — Verified single** | one call + `refine()` loop: run PUBLIC tests → feed failures back → retry (≤N) | **value of verification/iteration** |
| **C — Planner** | FORCED `PlannerAgent.run()` (decompose → execute → merge), not `dispatch()` | **value of decomposition/multi-agent BEYOND verification** |

Decisive lifts:
- **lift(B − A)** = value of verification.
- **lift(C − B)** = value of decomposition *on top of* verification.
- **lift(C − A)** = total orchestration value.

This directly tests the standing hypothesis (from the post-Phase-A review): *if any lift
exists it is mostly verification, not multi-agent decomposition.* V2 is built to falsify
that.

> Note: arm C must FORCE the planner (bypass disabled) — otherwise `dispatch()` would route
> these to a single agent and C would collapse into A/B. A `force_planner` switch on the
> pipeline runner is a required (small) harness change.

---

## 2. The critical anti-circularity rule: public vs hidden tests

If arm B's verification loop runs the *same* tests used for grading, B trivially maxes the
grader (it iterates until the grader passes) — meaningless.

**Rule:** every code case ships TWO disjoint test sets:
- **Public tests** — given in the prompt / used by arm B's verifier (the "examples").
- **Hidden tests** — used ONLY for grading (held out, adversarial edge cases).

This mirrors real TDD: iterate against examples, judged on held-out behavior. B's lift then
reflects genuine generalization from iterating, not teaching-to-the-test. **Without this
split the whole experiment is invalid.**

---

## 3. Proposed task categories (objective-first, with headroom)

Goal: tasks where a strong single call lands a partial — passes the happy path, misses edge
cases / a sub-component / a constraint — so scores spread across (0,1).

| Category | Signal | What creates headroom | Mechanism it probes |
| :--- | :--- | :--- | :--- |
| **Edge-case algorithms** | objective | adversarial hidden tests (empty, ties, overflow, unicode, negatives, large) | verification |
| **Multi-component build** | objective | several interdependent functions; integration test suite | decomposition |
| **Bug-fix / self-repair** | objective | buggy code + failing hidden tests; must diagnose+fix | verification |
| **Constraint-heavy spec** | objective | one function, 6–10 documented behaviors; grade = fraction satisfied | decomposition + verification |
| **Multi-step numeric reasoning** (small, lower trust) | numeric | genuinely hard multi-step; exact-match | reasoning |

**Excluded from the verdict:** research / architecture / "shallow" keyword categories — they
cannot be objectively graded for *quality*, so they cannot decide whether orchestration has
value. They may be carried as *observational only* until a cross-model judge exists (future,
out of scope). The verdict rests on `objective` + `numeric` cases only.

Concrete examples (illustrative): robust CSV/expression parser, interval merge with tie
edges, LRU cache with eviction order, date arithmetic across leap/DST, a mini calculator
(tokenizer+parser+evaluator), "fix this failing concurrency/parsing function."

---

## 4. Grading methodology

- **Partial-credit, objective:** `score = (# hidden tests passed) / (total hidden tests)`
  ∈ [0,1]. Continuous scoring is essential — binary pass/fail re-creates the ceiling/floor
  problem and hides incremental gains. (Requires upgrading the current binary `code` grader
  to a fractional one — a defined V2 harness change.)
- **Sandbox execution** (existing `sandbox.py`): bounded, no network, timeout, per hidden test.
- **Numeric:** exact match (rounded). No `contains`/keyword graders for any *deciding* case.
- **Calibration gate (keep-band):** pre-measure baseline (arm A) on each candidate; **keep
  only cases with baseline mean ∈ [0.2, 0.8].** Discard ~1.0 (no headroom) and ~0.0
  (unsolvable / floor). This is what guarantees headroom and is done BEFORE the real run.
- Each case keeps its `signal` tag; only `objective`/`numeric` cases contribute to the verdict.

---

## 5. Statistical methodology

- **Pre-registration (mandatory):** fix K, the significance multiplier, the keep-band, and
  the decision rule BEFORE running. No post-hoc tuning. This is what makes a null result
  trustworthy.
- **Trials:** K ≥ 5 per (case, arm); prefer 8–10 on deciding cases (LLM output is
  non-deterministic; SE shrinks ~1/√K). State the cost trade-off explicitly.
- **Aggregation:** mean score per (case, arm), infra trials excluded (existing `_aggregate`).
  Decide at the **category level** (pool trials) to limit multiple-comparison false positives;
  do not cherry-pick single cases.
- **Effect + significance:** reuse `_lift_record` — SE of the difference of means; significant
  iff `raw_lift > K_sig · SE`. Recommend a STRICT `K_sig = 2.0` for a positive claim (V1 used
  1.0). Also report a standardized effect size (lift / pooled_std).
- **Cost adjustment (existing):** lift per extra call, per 1k tokens, latency delta. An arm
  **earns its cost iff** `significant AND cost_adjusted_lift > 0`. Pre-registered.
- **Multiple comparisons:** with several categories × 3 arms, apply category-level aggregation
  + a conservative correction (e.g., Bonferroni on the number of arm-vs-arm tests).
- **Reliability separated from quality:** report infra rate per arm; exclude infra trials from
  quality means; **clean-cloud gating** (probe ≥8/8 before running; abort/retry on cloud
  flakiness — the 502s already corrupted two runs). Breaker reset per trial (done).
- **Four axes reported separately and never collapsed:** Quality (partial-credit score),
  Cost (calls + tokens), Latency (wall-clock, not just successful-call telemetry — see
  confounds), Reliability (infra rate).

**Pre-registered decision rule (draft):** "Orchestration earns its place iff, at the category
level on objective cases, lift(B−A) or lift(C−B) is significant at K_sig=2.0 AND
cost-adjusted > 0. Otherwise the cheaper arm wins and the heavier path is not built."

---

## 6. Exact execution plan

1. **Author** candidate objective cases with public+hidden test splits (no LLM; human/spec).
2. **Calibrate:** run arm A only, K, keep cases with baseline ∈ [0.2, 0.8]; discard the rest.
3. **Pre-register** K, K_sig, keep-band, decision rule (write them into the report header
   before the deciding run).
4. **Clean-cloud gate:** probe cloud (≥8/8 OK); only proceed when healthy.
5. **Run** arms A, B, C × kept cases × K, in `isolated_vault`, breaker reset per trial,
   trace-to-file, distillation suppressed during the run (see §7).
6. **Analyze:** per-arm Quality/Cost/Latency/Reliability; lift(B−A), lift(C−B), lift(C−A)
   with SE, significance, effect size, cost-adjustment; category-level verdict.
7. **Verdict** against the pre-registered rule; write the report; decide whether ANY further
   orchestration work is justified.

**Required (small) harness changes, gated by approval — NOT built now:** force-planner arm C;
arm B verified-single runner (reuse `refine()`); fractional code grader; public/hidden test
fields in the case schema; calibration mode; wall-clock latency capture; benchmark-time
distillation suppression.

---

## 7. Risks and confounds

| # | Confound | Impact | Mitigation |
| :--- | :--- | :--- | :--- |
| 1 | **Verifier == grader** (arm B) | invalidates the experiment | public/hidden test split (§2) |
| 2 | **No headroom** (ceiling) | repeats V1 | calibration keep-band [0.2,0.8] (§4) |
| 3 | **Cross-trial distillation contamination** | trial N reads trial N−1's distilled note from the isolated vault → arms not independent | **suppress distillation during benchmark** (hygiene; ties to CU7) OR reset vault per trial |
| 4 | **Cloud flakiness (502s)** | corrupts infra + quality | clean-cloud gate; infra exclusion; re-run |
| 5 | **Weak/strawman baseline** | inflates apparent lift | arm A must be a STRONG, well-engineered single prompt; pre-write + peer-check prompts |
| 6 | **Small K → underpowered** | can't detect real small lifts; false nulls | K≥5–8; report SE; state minimum detectable effect |
| 7 | **Multiple comparisons** | false positives across cases | category-level aggregation + correction (§5) |
| 8 | **Case-authoring selection bias** | cases chosen to favor a hypothesis | calibrate purely on baseline difficulty, blind to which arm benefits |
| 9 | **Latency telemetry counts only successful calls** | understates true cost of slow/failed paths | capture **wall-clock** per trial (the delegate A/B already showed telemetry hides ~28s) |
| 10 | **Local model in code arms** | timeouts/loops corrupt arms | cloud-pin code (CU4 done); report infra separately |
| 11 | **Overfitting to a fixed case set** over time | benchmark stops being honest | keep a held-out rotation; don't tune architecture against the same cases repeatedly |

---

## 8. Recommendation: delegate-skip / CU7 before V2?

- **CU7 / distillation suppression — YES, do the minimal version first (it is V2 hygiene).**
  Per-trial distillation into the isolated vault creates **cross-trial contamination**
  (confound #3): a later trial can retrieve an earlier trial's distilled note within the same
  run, breaking arm independence — exactly when V2 finally has headroom to be corrupted by it.
  Recommendation: implement only **"distillation off during benchmark runs"** (a flag), not
  the full CU7 policy redesign. Smallest change that makes V2 measurements independent.

- **Retrieval-delegate skip — NO, defer.** It is a latency/cost optimization, already
  justified by its own A/B (~3× on self-contained coding), and it does **not** affect V2's
  *quality* validity. Doing it first would also change arm C's behavior mid-design.
  Recommendation: defer; it can land independently any time after V2, and arm C should
  measure the planner as it actually is.

**Net:** before the V2 deciding run, complete only the minimal benchmark-time distillation
suppression (hygiene). Defer delegate-skip and the full CU7 redesign.

---

## 9. What V2 must be able to conclude

V2 succeeds as an *instrument* (regardless of outcome) if it can cleanly produce any of:
- "Verification earns lift (B>A, significant, cost-positive); decomposition does not (C≈B)."
- "Both earn lift." / "Neither earns lift — single call wins; stop building orchestration."

Only after V2 returns one of these, with pre-registered rigor on objective cases, is any
further architecture work justified. Until then: **measure before expansion** holds.
