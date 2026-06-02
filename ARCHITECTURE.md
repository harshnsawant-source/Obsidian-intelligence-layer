# Architecture

## 1. Agent pipeline (BaseAgent)

```
AgentManager.execute_task(name, task)  ──▶  agent.run(task)
                                               │
   run():  result = execute(task)              │  execute() default = query_agent(...)
           if distillable: knowledge_distill ──┘  (subclasses override for role/instructions)

   query_agent(task, role, instructions, extra_context):
     build_context(task)  →  query_llm(prompt)  →  save_memory(out)  →  return result
```

Every agent returns a string and inherits distillation. `distillable = False`
opts an agent out of writing to the vault (e.g. RetrievalAgent).

## 2. Memory / distillation loop

```
agent output ──▶ memories/<agent>_output.md         (raw, per-agent)
             └─▶ knowledge_distill ──▶ src/knowledge/vault/knowledge_*.md   (curated)
                                              │
   recall_engine (Menu #5) ───────────────────┤  read the vault
   knowledge_search / Menu #6 (semantic) ──────┘
```

## 3. Semantic retrieval

```
build_context(task)
  └─ MemoryIndex.search(task, k, min_score)
       1. ensure_index()  — incremental: embed only new/changed vault files
                            (SHA-1 hash diff), persist to src/state/index/vault_index.json
       2. embed(query)     — Ollama nomic-embed-text (qwen fallback can't embed)
       3. cosine (numpy)   — rank, top-k, drop below min_score
       4. fallback         — keyword search if embeddings unavailable
```

Notes are truncated to a safe char budget before embedding (model context cap).
Failed embedding models are cached per session so one bad call never re-pays cost.

## 4. Agent-to-agent communication

```
AgentManager (broker)              dispatch(name, task)  — depth-guarded (max 3)
  └─ injects agent.broker = self

BaseAgent.delegate(name, task)     → broker.dispatch → sub-agent.run() → str
BaseAgent.consume(names, task)     → delegate many, aggregate
query_agent(..., extra_context)    ← delegated output injected into the prompt

Strategy    ──delegate──▶ Research            (live, 2 LLM calls)
Development ──delegate──▶ Retrieval            (live, 2 LLM calls)
Operations  ──vault─────▶ peers' distilled outputs via build_context (1 LLM call)
```

## 5. Planning / task decomposition (Planner)

```
Planner.run(goal):
  decompose(goal)   ── 1 LLM call (JSON mode) ──▶ {steps:[{id,task,agent,depends_on}]}
       • agent validated vs AgentManager else route_agent(task)
       • robust parse (strips ```json fences); bad output → single-step fallback
       • capped at MAX_STEPS (6)
  execute(steps):
       • topological order (Kahn); dependency cycle → safe ordered fallback
       • inject completed dependency outputs into each step's task
       • manager.dispatch(agent, task)  (runs agent.run → distills; depth-guarded)
  synthesize(goal, results)  ── 1 LLM call ──▶ consolidated final answer
  distill final plan into the vault
```

Built entirely on the router + broker + semantic memory + distillation. Menu #15.

## 6. LLM orchestration router (multi-provider, resilient)

`query_llm()` is a thin facade over `ProviderRouter` (core/router.py):

```
query_llm(prompt, fmt, max_tokens, sensitive)
  └─ score_complexity → bar (low/medium/high)        # cheap, no LLM
  └─ order providers:
       sensitive       → local only          (privacy: never leaves device)
       bar == low       → local first         (preserve free-cloud quota)
       else             → best cloud first, local floor   (quality)
  └─ try in order, circuit-breaker aware:
       success → return ; failure → trip breaker, fail over
       floor = local Ollama ; final = canned string (never raises)
  └─ bar == high → log a manual "escalate to Claude (Pro)" suggestion
```

Providers (configs/providers.py) are tiered and config-driven; `openai_compat`
ones (Groq/OpenRouter/Together) activate automatically when their API key env
is set. Recovery is lazy: a circuit breaker half-opens for one probe after a
cooldown. Note the inverted economics here — the free cloud model is *both*
faster and stronger than local, so local is used for privacy, trivial work
(quota preservation), and as the always-on failover floor, not for cost.

## Routing

`agent_engine.route_agent` uses whole-word keyword matching with best-score
selection (multi-intent tasks go to the strongest signal; substrings like
"research" no longer trip the "search" keyword).
