# Obsidian Intelligence Layer

A local-first, multi-agent intelligence layer. Agents reason with a local LLM
(via Ollama), share a **semantic knowledge vault**, learn from their own
outputs via an automatic distillation loop, and can **delegate to one another**.

## Key ideas

- **Agents** (`src/agents/`) all share one pipeline in `BaseAgent`:
  `build_context → query_llm → save_memory → return`. A new agent only needs a
  name + specialty (and optionally a role/instructions) to inherit everything.
- **Distillation loop**: every completed agent output is auto-distilled into the
  knowledge vault (`src/knowledge/vault/`) by `BaseAgent.run()`.
- **Semantic memory**: `MemoryIndex` embeds vault notes (Ollama
  `nomic-embed-text`) and serves cosine top-k retrieval, with a keyword
  fallback when embeddings are unavailable. `build_context` uses it.
- **Agent-to-agent (A2A)**: `AgentManager` is a depth-guarded broker; agents
  `delegate()` / `consume()` each other. Strategy→Research and
  Development→Retrieval delegate live; Operations consumes peers' distilled
  outputs from the vault (cheap, no fan-out).

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full pipelines.

## Setup

```bash
pip install -r requirements.txt
ollama pull nomic-embed-text    # embeddings (semantic memory), local
```

Generation is handled by a **multi-provider orchestration router**
(`core/router.py`, providers in `configs/providers.py`): it scores task
complexity, prefers the free cloud model `qwen3-coder:480b-cloud` for quality,
keeps `sensitive=True` calls and trivial work on the local `qwen3.5:4b`, and
fails over (circuit-breaker aware) to local if the cloud is down — so it never
becomes unavailable. Free cloud providers (Groq/OpenRouter) activate
automatically if you set their API key env var.

If `nomic-embed-text` is not present, semantic retrieval degrades gracefully to
keyword search (no crash).

## Run

```bash
cd src
python main.py
```

Menu highlights: **#5** recall vault knowledge, **#6** contextual (semantic)
search, **#14** execute an agent task (auto-routes), **#15** plan & execute a
goal (decompose → route → run → synthesize), **#16** ingest a document,
**#17** ask over documents (local RAG), **#18** view the Claude escalation queue.

Memory/RAG is local: documents are chunked, embedded with `nomic-embed-text`,
and retrieved by the same vector engine — answered on the local model
(`sensitive=True`) so private content never leaves the device. Document
metadata lives in SQLite (`src/core/db.py`).

## Tests

```bash
python run_tests.py        # runs the verified suites
```

- `src/test_semantic_memory.py` — indexing, incremental updates, ranking,
  paraphrase retrieval, fallback.
- `src/test_a2a.py` — delegation, consumption, depth guard, distillation,
  no-broker safety.

## Layout

```
src/configs/    paths + model config (single source of truth)
src/agents/     agent implementations (thin; logic lives in BaseAgent)
src/core/       engines: memory, embeddings, index, context, routing, broker
src/capability/ skills + skill loader/router
src/knowledge/  the semantic knowledge vault
src/state/      runtime state (traces, working memory, generated index)
```
