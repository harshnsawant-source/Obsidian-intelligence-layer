# Benchmark V2 — Calibration Results + Frozen Kept Set

- **Author:** Claude (Executor)
- **Date:** 2026-06-06
- **Config (pre-registered):** see `BENCHMARK_V2_PREREGISTRATION.md` — K_cal=5, Arm A only,
  ceiling≥0.90, floor≤0.10, variance(std)≥0.35. Cost axis (deciding) = wall-clock; K_sig=2.0.
- **Clean-cloud gate:** PASS (8/8 probes) immediately before the run.
- **Raw data:** `runtime/calibration_v2.json`. **Scope:** calibration only; no deciding run.

## Phase 1 — Catalog sanity (unchanged, for the record)
- Candidates: **18**. Probe mix: V=7, D=6, mixed=5.
- Hidden tests: mean 6.44, median 6, min 5, max 8. Public tests: 3 each.
- No duplicate ids, no public/hidden overlap, no malformed cases. All 18 references pass
  public AND hidden (validated by `test_benchmark_v2`, 12/12 suites).

## Phase 3 — Calibration metrics (Arm A baseline, K_cal=5)

| Case | Probe | Baseline mean | Std | Infra | Verdict |
| :--- | :--- | :---: | :---: | :---: | :--- |
| v2_format_file_size | V | 1.00 | 0.00 | 0 | drop:ceiling |
| v2_slugify | V | 1.00 | 0.00 | 0 | drop:ceiling |
| v2_expand_ranges | V | 1.00 | 0.00 | 0 | drop:ceiling |
| v2_validate_brackets | V | 1.00 | 0.00 | 0 | drop:ceiling |
| v2_custom_numeral | V | 1.00 | 0.00 | 0 | drop:ceiling |
| v2_running_total | V | 1.00 | 0.00 | 0 | drop:ceiling |
| v2_interval_overlap | V | 1.00 | 0.00 | 0 | drop:ceiling |
| v2_tokenize_template | D | 1.00 | 0.00 | 0 | drop:ceiling |
| v2_calc | D | 1.00 | 0.00 | 0 | drop:ceiling |
| v2_eval_postfix | D | 1.00 | 0.00 | 0 | drop:ceiling |
| v2_parse_kv | D | 1.00 | 0.00 | 0 | drop:ceiling |
| v2_merge_dicts | D | 1.00 | 0.00 | 0 | drop:ceiling |
| v2_csv_row_parse | D | 1.00 | 0.00 | 0 | drop:ceiling |
| v2_parse_duration | mixed | 1.00 | 0.00 | 0 | drop:ceiling |
| v2_normalize_whitespace | mixed | 1.00 | 0.00 | 0 | drop:ceiling |
| v2_chunk | mixed | 0.97 | 0.07 | 0 | drop:ceiling |
| v2_titlecase | mixed | 1.00 | 0.00 | 0 | drop:ceiling |
| **v2_format_phone** | **mixed** | **0.87** | **0.07** | 0 | **keep** |

## Phase 4 — Frozen kept set

| | Count | Cases |
| :--- | :---: | :--- |
| **Kept (in-band)** | **1** | v2_format_phone (mixed) |
| Dropped: ceiling | 17 | all others (16 at 1.00; chunk at 0.97) |
| Dropped: floor | 0 | — |
| Dropped: high-variance | 0 | — |
| Infra failures | 0 | clean-cloud run |

**Final kept-set count: 1.** Category breakdown of kept set: V=0, D=0, mixed=1.

The kept set is **frozen** (this is elimination-only; no mid-band selection, no manual
curation — the pre-registered thresholds were applied verbatim).

## Phase 5 — Summary + recommendation

### What the numbers say
The single strong cloud call, given the 3 public examples, **solves 17/18 bespoke
specification-following tasks at the ceiling** (16 with a perfect 1.00 across all 5 trials,
std 0). Only `format_phone` retained genuine headroom (0.87). There were **no** floor cases
and **no** high-variance cases — the model is not failing or flailing; it is simply solving
these tasks first-try.

### Honest interpretation
- The "non-canonical spec-following" hypothesis — that bespoke, rule-heavy single functions
  would trip a single shot — is **falsified for this model**. A 480B coder one-shots them
  when given examples. This is consistent with every prior finding: where a single call
  saturates the task, there is no headroom for verification or decomposition to add value.
- This is **not an instrument failure**. The calibration gate did exactly its job: it caught
  the absence of headroom **before** an expensive, meaningless 3-arm deciding run.

### Recommendation: **DO NOT proceed to the deciding run.**
A 1-case kept set (single category, no V/D representation) cannot answer "does verification
help?" or "does decomposition help beyond verification?" — it is statistically and
structurally inadequate (n=1 case; the Holm family would be trivial; any result would be
anecdote, not evidence). Running it would burn compute for an uninterpretable outcome.

### What would be required before a deciding run is justified (future, gated — NOT started)
A new case-authoring round explicitly designed to defeat single-shot solving by THIS model,
e.g.: multi-file / multi-function tasks graded by integration suites; long specs with many
interacting constraints where examples don't reveal the edges; iterative test-fix tasks
where first-pass code reliably fails hidden edges; or reducing the number of public examples
so the baseline cannot pattern-match. Each of those is a **separate, scope-gated phase**
(case design and/or benchmark-design change) and is **not** performed here.

### Status
- Clean-cloud calibration completed. ✅
- Ceiling/floor/high-variance identified objectively (pre-registered thresholds). ✅
- Kept set frozen (1 case). ✅
- **Ready for deciding-run approval: NO** — insufficient headroom; recommend a harder
  case round instead. Awaiting explicit direction. No further work performed.
