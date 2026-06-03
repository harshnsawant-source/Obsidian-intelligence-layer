# CURRENT SYSTEM STATE  (canonical — single source of truth)

- **Pinned commit:** `714b017` (tree at this commit contains everything below)
- **Date:** 2026-06-04
- **Status:** Healthy — 10/10 test suites green, 295 checks

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
- **Phase A (this commit):** orchestration lift benchmark (`core/eval/lift_benchmark.py`, menu #22) — canonical `PlannerAgent` pipeline vs strong single-call baseline; significance-gated, cost-adjusted (calls/tokens/latency), infra-failure aware; cases tagged by grader reliability.

## Tests (10 suites, 295 checks)
semantic_memory · a2a · planner · shared_reasoning · provider_router · phase2 · verification · tools · feedback · **lift_benchmark (31)**.

## Do NOT rebuild (extend only)
Router · Sandbox · PlannerAgent · PlanExecutor · SharedExecutionContext · MemoryIndex · Verification · Tool framework · Eval/lift harness.

## Known limitations / tech debt
- Single-model monoculture (all agents = qwen-cloud); cross-model diversity not yet present (Phase D).
- Objective lift signal exists only for **Engineering/code** cases (sandbox). Research/Architecture graders are `shallow` (keyword presence ≠ quality) — treat those lift numbers as provisional until a cross-model judge exists.
- Live benchmark runs `PlannerAgent.run()`, which **distills to the real vault** → benchmark pollutes the vault; needs an isolated benchmark vault.
- Sequential execution (no parallel DAG); no budget/quota governance.
- Cross-run structured retrieval not wired (`to_dict` seam + `episodes` unused); context is per-run.
- No full run tracing yet (telemetry is per-run only; Phase B extends it).
- Free-only constraint vs paid cross-model ambition (decide at Phase D).
- Legacy strata: capability/skills v1 (2 live), operational engines (menu #1–13).

## Current priorities
1. Validate Phase A lift numbers (live run, Engineering first — the trustworthy signal).
2. Phase B observability (extend TelemetryAccumulator → full traces).
3. Phase C real workspace. 4. Phase D0/D cross-model. 5. Phase E retrieval.
