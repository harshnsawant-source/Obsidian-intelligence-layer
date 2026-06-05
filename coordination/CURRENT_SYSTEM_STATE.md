# CURRENT SYSTEM STATE  (canonical — single source of truth)

- **Pinned commit:** `8367f17` (tree at this commit contains everything below)
- **Date:** 2026-06-06
- **Status:** Healthy — 12/12 test suites green

> Rule: nothing is "baseline" until committed. This file always cites a commit
> whose tree actually contains the claimed capabilities. Do not duplicate this
> file elsewhere; `docs/ROADMAP.md` is the canonical roadmap.

---

## Providers & hardware
- Tier 1 cloud: `ollama-cloud-coder` = `qwen3-coder:480b-cloud` (free, primary — plan/code/strategy).
- Tier 4 local floor: `ollama-local` = `qwen3.5:4b` (failover + sensitive/private).
- Embeddings: local `nomic-embed-text` (768-dim).
- Dormant: `OpenAICompatProvider` (key-gated; enables paid cross-model at Phase D).
- Hardware: 16GB RAM, 4GB VRAM, Ollama on `localhost:11434`.

## Implemented (committed)
- **Foundations:** provider router (`core/router.py`, heuristic complexity, circuit breakers, failover, **+ TelemetryAccumulator**), memory index, verification, sandbox.
- **Phase 2:** document RAG + privacy flag + escalation + SQLite (`episodes` table defined, unused).
- **Phase 3:** verification/self-correction + sandbox.
- **Phase 6:** tool framework (ReAct, risk-tiered, default-deny, path-jail).
- **Phase 7:** eval harness + curator.
- **Phase 4:** PlannerAgent + PlanExecutor + SharedExecutionContext (sequential).
- **Phase 5 / 5.1:** structured reasoning (findings/decisions/artifacts/risks/assumptions), provenance, dedup, `reported_by` consensus, contribution strip.
- **Phase A:** orchestration lift benchmark (`core/eval/lift_benchmark.py`, menu #22) — canonical `PlannerAgent` pipeline vs strong single-call baseline; significance-gated, cost-adjusted (calls/tokens/latency), infra-failure aware; cases tagged by grader reliability. **+ isolated benchmark vault** (`core/eval/benchmark_vault.py`) so runs cannot pollute/read the real vault.
- **Week 1 reliability (CU8/CU1/CU2 — this commit):**
  - **CU8** minimal tracing (`core/trace.py`): bounded per-call records at the router chokepoint (served_by / providers_tried / fallback_used / bar / latency / ok / output_kind); opt-in `runtime/trace.jsonl`. Additive; never alters returned values.
  - **CU1** per-provider timeout config (replaces hardcoded 600s): cloud 300s, local floor 120s.
  - **CU2** per-provider output-token cap: local floor capped at 1500 tokens (bounds runaway/looping generation); cloud uncapped.
  - **CU3** breaker tuning (severe/timeout fast-open). **CU4** cloud-pin non-sensitive code (`produces_code`). **CU5** degenerate-output detection (`output_health`). **CU6** failure isolation (`PlanExecutor` skips failed steps; `delegate` returns "" on failure; `degraded_steps`).
  - **Planner bypass:** `core/agent_engine.dispatch()` + `needs_planning()` — cheapest sufficient path (direct single agent by default; PlannerAgent only on strong explicit multi-step/multi-deliverable signal). ROUTES extended so coding → development-agent. Benchmark pipeline now measures `dispatch()`; per-trial breaker reset. Measured: pipeline calls 14.5→2.0, latency 312→12.5s, score held 1.00, decomposition failure mode eliminated (see REVIEWS/2026-06-05-planner-bypass-delta-report.md).
  - **Benchmark V2:** instrument built (3 arms, fractional grading, calibration, MDE+Holm) + 18 validated cases. **Calibration result (settled):** 17/18 ceiling, kept set = 1 → orchestration-lift for coding is answered (negative); no deciding run. See `coordination/BENCHMARK_V2_*`.
- **Knowledge-work pivot (product roadmap in `coordination/PRODUCT_AUDIT_AND_ROADMAP.md`):**
  - **Phase K-A DONE:** CU7 — distil only top-level results (subtask/delegated runs suppressed via `AgentManager.dispatch`); auto-curation on startup (`curator.auto_curate`, prunes error/empty + dedups the distillation vault). "Only if novel" = exact-dedup at write + auto-curate near-dedup (no hot-path embedding gate).
  - **Next (not started):** K-B real Obsidian-vault ingestion + unified retrieval; K-C private-work capability (local reliability + cloud-consent tier); K-D synthesis/connections; K-E cross-run memory.

## Tests (10 suites, 322 checks)
semantic_memory · a2a · planner · shared_reasoning · **provider_router (33 — +CU8 trace, CU1 timeout, CU2 token cap)** · phase2 · verification · tools · feedback · **lift_benchmark (40 — +isolation)**.

## Do NOT rebuild (extend only)
Router · Sandbox · PlannerAgent · PlanExecutor · SharedExecutionContext · MemoryIndex · Verification · Tool framework · Eval/lift harness.

## Known limitations / tech debt
- Single-model monoculture (all agents = qwen-cloud); cross-model diversity not yet present (Phase D).
- Objective lift signal exists only for **Engineering/code** cases (sandbox). Research/Architecture graders are `shallow` (keyword presence ≠ quality) — treat those lift numbers as provisional until a cross-model judge exists.
- Live benchmark runs `PlannerAgent.run()`, which **distills to the real vault** → benchmark pollutes the vault; needs an isolated benchmark vault.
- Sequential execution (no parallel DAG); no budget/quota governance.
- **Reliability (partial — Week 1 in progress):** provider stalls are now bounded by timeout (CU1) + token cap (CU2) and visible via trace (CU8). Still open: breaker still needs 3 failures to shed local (CU3); code subtasks not yet cloud-pinned (CU4); repetition-loop / `[NO FINAL ANSWER GENERATED]` output is not yet detected as failure (CU5); a degraded subtask still threads forward into the merge (CU6); distillation still fires per subtask (CU7).
- Cross-run structured retrieval not wired (`to_dict` seam + `episodes` unused); context is per-run.
- No full run tracing yet (telemetry is per-run only; Phase B extends it).
- Free-only constraint vs paid cross-model ambition (decide at Phase D).
- Legacy strata: capability/skills v1 (2 live), operational engines (menu #1–13).

## Current priorities
1. Validate Phase A lift numbers (live run, Engineering first — the trustworthy signal).
2. Phase B observability (extend TelemetryAccumulator → full traces).
3. Phase C real workspace. 4. Phase D0/D cross-model. 5. Phase E retrieval.
