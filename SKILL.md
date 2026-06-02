---
name: obsidian-intelligence-layer
description: Use when developing, extending, debugging, or operating the Obsidian Intelligence Layer — the local-first, free, resilient multi-agent orchestration system (hybrid free-cloud + local Ollama, semantic memory/RAG, agent-to-agent delegation, planner). Covers its architecture, conventions, models, testing discipline, and hard-won gotchas.
---

# Working on the Obsidian Intelligence Layer

A local-first multi-agent AI system. Agents reason via a hybrid LLM router
(free cloud + local Ollama), share a semantic knowledge vault, auto-distill
their outputs, delegate to one another, plan multi-step goals, and answer over
private documents — with **no paid APIs/subscriptions** and **no single point
of failure**. Project root: `projects/obsidian-intelligence-layer` (its own git
repo). Read `SUMMARY.md` + `ARCHITECTURE.md` first.

## Run & test
- Run the app: `cd src && python main.py` (menu-driven).
- Tests: `python run_tests.py` (5 suites). **Never claim done without running it.**
- Debug internals: `OIL_LOG_LEVEL=DEBUG`.

## Non-negotiable rules (learned the hard way)
1. **The router is heuristic, never an LLM.** Routing lives in
   `core/complexity.py` (cheap scoring). Calling a model to decide which model
   to call is a 40s-on-local mistake. Don't.
2. **All generation goes through `core/llm_engine.query_llm`** → the
   `ProviderRouter`. Never hardcode a model or hit Ollama directly from agents.
3. **Privacy boundary:** anything touching personal notes/memory/documents must
   use `sensitive=True` (pins to LOCAL models). Embeddings are always local.
4. **Free-only scope:** providers = Ollama local + Ollama free cloud only. Do
   NOT add paid/keyed providers (Anthropic API, Groq, OpenRouter, opencode)
   unless the user explicitly asks. Claude has **no API** here (Pro = consumer
   chat) → it is a *manual* escalation tier, surfaced via the escalation queue.
5. **Inverted economics:** the free cloud model is faster *and* stronger than
   local. Local is for **privacy, trivial-task quota preservation, and
   failover** — not "cheap." Don't blanket-route common work to slow local.

## Models
- Quality (default): `qwen3-coder:480b-cloud` (free, remote, fast).
- Local floor / private: `qwen3.5:4b`. Embeddings: `nomic-embed-text` (local).
- Configured in `src/configs/providers.py`; selected at runtime by the router.
- Hardware ceiling: **4GB VRAM → one ~3–4B local model at a time.** Don't pull
  big (7B+) or many local models (load/unload thrash). No Qdrant server.

## How to extend

### Add an agent
Subclass `BaseAgent` (in `src/agents/`):
```python
class FooAgent(BaseAgent):
    # sensitive = True        # if it reasons over private data (pins local)
    # distillable = False     # if its output should NOT go to the vault
    def __init__(self):
        super().__init__("foo-agent", "foo-specialty")
    def execute(self, task):
        return self.query_agent(task, role="Foo Expert",
            instructions="...")        # role/instructions only; pipeline is inherited
```
Then register it in `core/agent_manager.py` (`self.agents`) and add routing
keywords in `core/agent_engine.py` (`ROUTES`). `run()` auto-distills; the broker
is auto-injected. A bare agent (name+specialty, no `execute`) also works.

### Structured output
`query_llm(prompt, fmt="json", max_tokens=...)`. The cloud coder wraps JSON in
```` ```json ```` fences even in JSON mode — parse with the
extract-`{...}`-block approach (see `core/planner.py:_parse_steps`), not strict
`json.loads`.

### Memory / RAG
- Vault knowledge: `core/memory_index.py` (incremental, cosine, keyword
  fallback). Documents: `core/document_store.py` (chunk → embed local → search).
  Metadata: `core/db.py` (SQLite). Vectors live in the index, not SQLite.
- Vector-store progression: MemoryIndex → Chroma (embedded) → Qdrant (only at
  large scale). Keep the `DocumentStore`/`MemoryIndex` seam so swaps are local.

### Resilience
Providers raise on failure; the router fails over (circuit breaker, lazy
recovery) cloud → local → canned string. `query_llm` never raises.

## Testing discipline
- Tests are offline + deterministic: **stub `query_llm`, `build_context`, and
  `embeddings.embed_text`** (see existing `test_*.py`). Stubs must accept
  `*args, **kwargs` (signatures evolve — e.g. the `sensitive` kwarg).
- Add new suites to `run_tests.py`.
- For risky pieces, also run **one live check** (cloud is ~5s; local ~40s), then
  clean up artifacts. Generated stores are gitignored:
  `src/state/index/`, `src/state/db/`, `src/state/documents/`,
  `runtime/escalations.md`.

## Gotchas
- **Windows cp1252** console can't print model unicode → `main.py` forces UTF-8
  stdout. Keep that.
- **`qwen` chat models can't embed** (Ollama 501) — only `nomic-embed-text`
  embeds; failed models are cached per session.
- **Long notes** exceed the embed context → truncate to `EMBED_INPUT_CHAR_LIMIT`
  before embedding.
- **`configs/` lives under `src/`** (`src/configs/paths.py`); packages are
  namespace packages (no `__init__.py`). No `sys.path` hacks — don't reintroduce.
- `qwen3.5:397b-cloud` is **paywalled**; `qwen3-coder:480b-cloud` is **free**.

## Git
Project is its own repo. Branch off main for nontrivial work; commit only when
asked; end commit messages with the `Co-Authored-By: Claude ...` trailer; tests
green before committing.

## Pointers
`SUMMARY.md` (full overview + commit history), `ARCHITECTURE.md` (pipeline
diagrams), `README.md` (setup/run). Open roadmap: session memory, Chroma
migration, feedback/eval loop (#7), tool-execution framework + safety (#6).
