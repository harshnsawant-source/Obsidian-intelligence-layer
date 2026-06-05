# Benchmark V2 — Candidate Catalog Report (pre-calibration)

- **Author:** Claude (Executor)
- **Date:** 2026-06-06
- **Status:** Catalog expanded + validated. **Calibration NOT run** (awaiting approval).
- **Source:** `src/core/eval/benchmark_cases_v2.py`; validated by `test_benchmark_v2.py`.

## Final candidate count
**18 candidate cases.**

## Category / probe distribution
- **Probe (intended):** V (verification-heavy) = **7** · D (decomposition-heavy) = **6** · mixed = **5**
- **Structural category:** spec-following = 12 · compositional = 6
- All cases are `signal=objective`, graded by `fractional_code` (partial credit over hidden tests).
- Public tests per case: **3** (used by arms B/C verify loop). Hidden tests: 5–8 (grading only).

## Validation report (every reference passes public AND hidden)

| Case | Probe | Category | Public | Hidden | Ref→public | Ref→hidden |
|---|---|---|---:|---:|:---:|:---:|
| v2_format_file_size | V | spec-following | 3 | 8 | ✅ | ✅ |
| v2_slugify | V | spec-following | 3 | 6 | ✅ | ✅ |
| v2_expand_ranges | V | spec-following | 3 | 8 | ✅ | ✅ |
| v2_validate_brackets | V | spec-following | 3 | 7 | ✅ | ✅ |
| v2_custom_numeral | V | spec-following | 3 | 7 | ✅ | ✅ |
| v2_running_total | V | spec-following | 3 | 6 | ✅ | ✅ |
| v2_interval_overlap | V | spec-following | 3 | 6 | ✅ | ✅ |
| v2_tokenize_template | D | compositional | 3 | 7 | ✅ | ✅ |
| v2_calc | D | compositional | 3 | 7 | ✅ | ✅ |
| v2_eval_postfix | D | compositional | 3 | 7 | ✅ | ✅ |
| v2_parse_kv | D | compositional | 3 | 6 | ✅ | ✅ |
| v2_merge_dicts | D | compositional | 3 | 6 | ✅ | ✅ |
| v2_csv_row_parse | D | compositional | 3 | 6 | ✅ | ✅ |
| v2_parse_duration | mixed | spec-following | 3 | 7 | ✅ | ✅ |
| v2_normalize_whitespace | mixed | spec-following | 3 | 5 | ✅ | ✅ |
| v2_format_phone | mixed | spec-following | 3 | 6 | ✅ | ✅ |
| v2_chunk | mixed | spec-following | 3 | 6 | ✅ | ✅ |
| v2_titlecase | mixed | spec-following | 3 | 5 | ✅ | ✅ |

**Reference pass status: 18/18 references pass ALL public AND ALL hidden tests** (56 validation
checks in `test_benchmark_v2.py`). Full suite **12/12** green.

## Design properties held
- **Non-canonical:** all tasks are bespoke specification-following (idiosyncratic rules / parameterized inputs) — no `merge_intervals` / `roman_to_int` / `binary_search`. Memorization resistance comes from quiet rules + parameterized signatures (e.g. `to_int(s, table)` with a non-standard symbol table; `validate_brackets(s, pairs)`).
- **Public/hidden disjoint:** hidden tests add adversarial edges (empty input, boundaries, error-raising, dup/overlap, unicode separators) absent from the 3 public examples → iterating on public cannot teach to the grader.
- **Probe balance:** V cases are single edge-rich functions; D cases are compositional (tokenize→parse→evaluate, recursive merge, stateful CSV) where decomposition could plausibly help; mixed cases combine validation + transformation with several components.

## Honest caveats (for the calibration step)
- Probe tags are the **author's intent**, not proof a case favors that mechanism — the deciding run measures actual lift.
- Some cases may still prove to be ceiling (single-call solves them) — that is exactly what calibration removes. Expect the kept set to be < 18.
- A few cases (`calc`, `eval_postfix`, `expand_ranges`) are toward the "common" end and may hit the baseline ceiling; calibration will cull them if so.

## Next (gated) steps — NOT started
1. Freeze this candidate pool (this report = the frozen list, pending review).
2. Pre-register K_cal, K, K_sig, cost axis, keep-band thresholds.
3. Clean-cloud **independent calibration** (arm A only) → eliminate ceiling/floor/high-variance → kept set (target ≥ 8–10).
4. Pre-register kept set → deciding run → analyze → verdict.

No calibration or measurement run has been performed.
