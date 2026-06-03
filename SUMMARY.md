# Project Summary — Obsidian Intelligence Layer

A local-first, free, resilient multi-agent AI system. Agents reason with a
hybrid LLM stack (free cloud + local Ollama), share a semantic knowledge vault,
learn from their own outputs, delegate to one another, plan multi-step goals,
and answer questions over private documents — with no paid APIs or
subscriptions, and no single point of failure.

This document summarizes the work completed across the build sessions.

---

## 1. What the system is now

```
USER / AGENT
     │
 HEURISTIC ROUTER (0ms, no LLM)  ── complexity score + privacy flag
     │
     ├── trivial / sensitive ──▶ LOCAL  qwen3.5:4b   (private, offline floor)
     ├── real work ───────────▶ FREE CLOUD  qwen3-coder:480b-cloud  (fast, top quality)
     │        └── circuit-breaker failover: cloud → local → canned (never down)
     └── HIGH complexity ─────▶ flagged for MANUAL Claude Pro escalation (you)

 Memory / RAG / embeddings ─────▶ ALWAYS LOCAL (nomic-embed-text)  — privacy boundary
```

- **Quality tier:** `qwen3-coder:480b-cloud` — free, remote, ~9× faster than
  local, used for coding / planning / reasoning / research.
- **Local floor:** `qwen3.5:4b` — privacy-sensitive work, trivial tasks (to
  preserve cloud quota), and failover. Always available, fully on-device.
- **Embeddings:** `nomic-embed-text` (local, 768-dim).
- **Manual brain:** Claude Pro (no API) — architecture reviews, debugging the
  orchestrator, prompt/eval, hard escalations. Surfaced via an escalation queue.

---

## 2. Capabilities built

### Learning loop (closed)
Every completed agent output auto-distills into the knowledge vault
(`src/knowledge/vault/`) via `BaseAgent.run()`. Recall (Menu #5) and contextual
search (Menu #6) read the vault. Fixed the original break where agent output
went to `memories/` and never reached the vault.

### Unified agent pipeline
All agents share one pipeline in `BaseAgent.query_agent`
(`build_context → LLM → save → return`). A new agent only needs a name +
specialty to inherit everything. Agents: Development, Operations, Content,
Retrieval, **Research**, **Strategy**. Routing uses whole-word keyword scoring
(fixes the "research" matched "search" bug; multi-intent → strongest signal).

### Semantic memory (RAG)
- `core/embeddings.py` — Ollama embedding client with LRU cache (repeated
  queries are instant) and failed-model caching.
- `core/memory_index.py` — incremental, hash-based vector index over the vault;
  cosine top-k with `min_score`; keyword fallback when embeddings are down;
  long notes truncated to a safe embedding budget.
- `core/context_builder.py` — agent context now comes from semantic retrieval.

### Agent-to-agent communication
`AgentManager` is a depth-guarded **broker**; `BaseAgent.delegate()` /
`consume()`. Strategy → Research (live), Development → Retrieval (live),
Operations consumes peers' distilled vault outputs (cheap, no fan-out).

### Planning / task decomposition (`core/planner.py`, Menu #15)
Decompose a goal into a subtask DAG (JSON mode) → route each to an agent →
execute in topological order feeding dependency outputs forward (via the broker)
→ synthesize a final answer → distill it. Robust: strips ```json fences,
single-step fallback on bad output, cycle-safe, capped at MAX_STEPS.

### LLM orchestration router (`core/router.py`)
- `core/complexity.py` — cheap deterministic complexity scoring (never an LLM).
- `core/providers/` — pluggable providers (Ollama local + cloud; OpenAI-compat
  class dormant). `core/circuit_breaker.py` — CLOSED/OPEN/HALF_OPEN with lazy
  recovery. Privacy/complexity-aware ordering, failover, local floor, canned
  final fallback (never raises). `llm_engine.query_llm` is a thin facade so all
  agents get routing + failover transparently.
- **Scope:** Ollama only (local + free cloud) — no external providers.

### Document RAG + privacy + escalation (Phase 2)
- `core/document_store.py` — ingest (chunk → embed local → search), Menu #16/#17.
- `core/db.py` — SQLite registry (documents, episodes).
- `sensitive` flag — personal memory/docs pinned to local models; embeddings
  never leave the device.
- `core/escalation.py` — HIGH-complexity tasks queued to `runtime/escalations.md`
  for manual Claude Pro review (Menu #18).

### Verification / self-correction + sandboxed execution (Phase 3)
A generic **generate → verify → correct** layer (`core/verification.py`,
`refine()`) with pluggable verifiers (`core/verifiers.py`): schema (JSON), code
(runs in `core/sandbox.py` — subprocess-isolated, timeout-bounded, opt-in), and
critic (a 2nd LLM review pass). Wired into `BaseAgent` (agents opt in via
`verifiers=[]`; no verifiers ⇒ unchanged single call) and `Planner(verify=True)`
(critic on synthesis). Crucially, `run()` now **gates distillation on the
verdict**: output that fails verification is *not* written to the vault, so
errors can no longer compound through retrieval. Design blueprint in
`VERIFICATION.md` (written to be reusable across orchestration systems).

### Foundations & hygiene
- Packaging: `configs/` moved under `src/`, removed all `sys.path` hacks,
  added `pyproject.toml`.
- Observability: `core/log.py` (quiet by default, `OIL_LOG_LEVEL=DEBUG`).
- Retired dead code (coordination_engine, test_ollama, memory_search); wired
  `model_adapter` into `llm_engine`.
- Docs: `README.md`, `ARCHITECTURE.md`; test runner `run_tests.py`.
- Windows: forced UTF-8 stdout (cloud model emits unicode cp1252 can't print).

---

## 3. Key design decisions (and why)

- **Inverted economics:** the free cloud model is both faster *and* stronger
  than local, so local is used for **privacy + quota preservation + failover**,
  not cost.
- **Router is heuristic, never an LLM** — routing must be ~0ms, not a 40s local
  call.
- **Claude has no API** (Pro is consumer chat) → it's a **manual** escalation
  tier, never called programmatically.
- **No Qdrant (yet):** `MemoryIndex` now → Chroma (embedded) when it grows →
  Qdrant only at large scale. No server competing for 16GB.
- **One model per role tier, not five tiny agents** — agents are roles sharing
  one router, not separate resident models (4GB VRAM holds ~one at a time).

---

## 4. Hardware profile

16GB RAM, 4GB VRAM, Ollama local. Local models capped at ~3–4B (q4) to fit
VRAM; the heavy lifting runs free on remote GPUs via Ollama cloud.

---

## 5. Testing

`python run_tests.py` → **6 suites, 89 checks, all passing**:
- `test_semantic_memory.py` — indexing, incremental, ranking, paraphrase, cache, fallback
- `test_a2a.py` — delegation, consumption, depth guard, distillation, no-broker safety
- `test_planner.py` — decompose, fallback, ordering, dependency injection, cycle safety, synth, distill
- `test_provider_router.py` — scoring, routing, privacy, failover, circuit-breaker
- `test_phase2.py` — chunking, ingest, SQLite registry, doc search, sensitivity flags, escalation queue
- `test_verification.py` — refine loop, aggregation, schema/code/critic verifiers, sandbox (real subprocess), distillation gate

---

## 6. Commit history

| Commit | Summary |
|---|---|
| `acafc61` | Initial commit: semantic memory + A2A |
| `449701c` | Scaffolding: README, ARCHITECTURE, requirements, test runner; remove cruft |
| `0057771` | Logging util + query-embedding cache |
| `94fa5f3` | Foundations: package layout + legacy-engine audit |
| `1acbfa1` | Planner (#5) + switch to free cloud coder model |
| `a1b104e` | Multi-provider LLM orchestration router |
| `dbbaeed` | Scope providers to Ollama only |
| `0b9243a` | Phase 2: document RAG + privacy flag + escalation + SQLite |
| `079ffd1` | SUMMARY.md (full project overview) |
| `2abf98c` | SKILL.md (operating + development guide) |
| `fe3aab8` | Phase 3: verification / self-correction loop + sandboxed execution |

---

## 7. Status & what's next

**Status:** the target architecture is essentially complete — free-only,
privacy-first, resilient, and tested. It cannot go down (local floor + canned
fallback), nothing sensitive leaves the device, and it costs nothing.

**Next steps:**
1. **Tool execution framework** (roadmap #6): generalize the sandbox's
   default-deny / explicit-enable permission posture into file/web/shell tools.
2. **Feedback / learning loop** (roadmap #7): use `Verdict.ok/score` as the
   pass/fail signal to activate the dormant `eval.jsonl` harness (prove
   verification + tools actually raise quality) + vault dedupe/prune.
3. One **live LLM-in-the-loop** run of the verification correction pass (the
   deterministic path is tested; the live correction pass is not yet).
4. Migrate `MemoryIndex` → **Chroma** (embedded) when note/chunk count grows.
5. Short-term **session memory** (deferred — no chat-loop consumer yet).

**Run it:** `cd src && python main.py` (Menu #14 execute agent, #15 plan a goal,
#16 ingest a doc, #17 ask over docs, #18 escalation queue).
`OIL_LOG_LEVEL=DEBUG` for internals.
