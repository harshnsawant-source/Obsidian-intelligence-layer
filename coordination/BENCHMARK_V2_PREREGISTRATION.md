# Benchmark V2 — Calibration Pre-registration (frozen BEFORE any run)

- **Author:** Claude (Executor)
- **Date:** 2026-06-06
- **Purpose:** Freeze every parameter and decision rule before calibration/deciding
  runs, so results cannot be tuned post-hoc and a null result is trustworthy.
- **Note:** all values below equal the instrument's existing committed defaults
  (`arms.VERIFY_TRIES`, `run_calibration`, `run_v2`, `analyze_v2`). No code is
  changed in this phase.

## Trial counts
| Param | Value | Meaning |
| :--- | :---: | :--- |
| **K_cal** | 5 | calibration trials per case (Arm A only) |
| **K** | 8 | deciding-run trials per case, per arm (registered now for the later gated run) |
| **VERIFY_TRIES** | 2 | verification depth in arms B and C: 1 initial generate + up to 2 attempts; identical in B and C |

## Significance / correction (deciding run)
| Param | Value | Meaning |
| :--- | :---: | :--- |
| **K_sig** | 2.0 | a lift is "significant" iff raw_lift > K_sig · SE (one-sided alpha ≈ 0.0228) |
| **Holm–Bonferroni family** | all pairwise arm tests {B−A, C−B, C−A} across every category present in the kept set, corrected together (step-down Holm). Family size = 3 × (#categories in kept set). |
| **MDE** | reported per pair = K_sig · SE; a non-significant result with lift < MDE is read as "underpowered," not "zero lift." |

## Cost axis for `earns_cost`
- **Primary (decision):** **wall-clock** seconds. A pair earns its cost iff it is
  Holm-significant AND its cost-adjusted lift (quality lift per extra wall-second) > 0.
- Calls and tokens are reported as informational secondary cost axes.

## Calibration elimination thresholds (Arm A baseline only)
Eliminate a candidate case iff ANY of:
| Rule | Threshold | Rationale |
| :--- | :---: | :--- |
| **ceiling** | baseline mean **≥ 0.90** | single call already solves it → no headroom |
| **floor** | baseline mean **≤ 0.10** | effectively unsolvable → no learnable signal |
| **high-variance** | baseline std **≥ 0.35** | score is near-coin-flip → noise, not signal |
| **keep** | otherwise | NO mid-band selection — elimination only |

## Hard rules
- Calibration uses **Arm A only**; **no** Arm B, **no** Arm C, **no** planner comparison.
- Calibration trials are **independent** and are **never reused** in the deciding run
  (the deciding run draws fresh trials).
- Elimination is purely threshold-based; **no** manual curation, **no** selecting cases
  because they would help orchestration.
- Runs only proceed when the clean-cloud gate passes (probe ≥ 8/8).
- Calibration runs inside `isolated_vault` with distillation suppressed (no vault pollution).

## Frozen
This configuration is frozen as of commit recorded in the calibration report. Any change
after a run invalidates that run.
