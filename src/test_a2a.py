import sys

import agents.base_agent as ba
from agents.base_agent import BaseAgent
from core.agent_manager import AgentManager

PASS = []
FAIL = []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("PASS" if cond else "FAIL"), "-", name)


# --- isolate delegation logic: no Ollama, no embeddings, no disk writes ---
llm_calls = {"n": 0}


def fake_llm(prompt, *args, **kwargs):
    llm_calls["n"] += 1
    return "ECHO::" + prompt


ba.query_llm = fake_llm
ba.build_context = lambda task, k=5: ""                  # skip semantic layer

distill_calls = []


class FakeDistill:
    def execute(self, ctx, data):
        distill_calls.append(data.get("task"))
        return {"saved": "fake"}


ba.load_skill = lambda name: FakeDistill()
ba.save_memory = lambda name, content: f"<mem:{name}>"   # no disk
ba.RuntimeContext = lambda: None                         # distill ctx unused

mgr = AgentManager()

# Req 1: StrategyAgent delegates to ResearchAgent (live, single hop)
llm_calls["n"] = 0
strat = mgr.execute_task("strategy-agent", "enter the EV charging market")
check("req1: strategy consumed research output",
      "Research Expert" in strat)
check("req1: strategy delegates live (research + self = 2 LLM calls)",
      llm_calls["n"] == 2)

# Req 2: DevelopmentAgent requests context from RetrievalAgent (live)
distill_calls.clear()
llm_calls["n"] = 0
dev = mgr.execute_task("development-agent", "build a payments API")
check("req2: development consumed retrieval context",
      "Context Retrieval Analyst" in dev)
check("req2: development delegates live (retrieval + self = 2 LLM calls)",
      llm_calls["n"] == 2)
# Req 5 detail: retrieval is distillable=False -> only development distills
check("req5: retrieval output NOT distilled (no vault pollution)",
      distill_calls == ["build a payments API"])

# Req 3: OperationsAgent consumes peer outputs from the vault (EFFICIENT) --
# semantic build_context surfaces prior agent outputs in one lookup, so no
# fan-out into extra agent runs.
ba.build_context = lambda task, k=5: "PEER_VAULT_OUTPUT_distilled_research_and_dev"
llm_calls["n"] = 0
ops = mgr.execute_task("operations-agent", "scale the platform")
ba.build_context = lambda task, k=5: ""   # restore isolation
check("req3: operations consumes peer outputs from the vault",
      "PEER_VAULT_OUTPUT" in ops)
check("req3: operations is efficient (1 LLM call, no fan-out)",
      llm_calls["n"] == 1)

# Req 4: no breaking changes — non-delegating agent still works
content = mgr.execute_task("content-agent", "write a launch post")
check("req4: plain agent still returns a string",
      isinstance(content, str) and "Content Strategist" in content)

# Req 4: standalone agent (no broker) — delegate is a graceful no-op
from agents.strategy_agent import StrategyAgent
solo = StrategyAgent()
solo_res = solo.run("standalone plan")
check("req4: standalone agent (no broker) still runs",
      isinstance(solo_res, str) and "Strategy Expert" in solo_res)

# Req 5: distillation pipeline still fires for distillable agents
check("req5: distillation still invoked", len(distill_calls) >= 1)

# Depth guard: two agents that delegate to each other must terminate
class Pinger(BaseAgent):
    distillable = False

    def __init__(self, name, target):
        super().__init__(name, "test")
        self.target = target

    def execute(self, task):
        return f"{self.name}->(" + self.delegate(self.target, task) + ")"


mgr.agents["ping"] = Pinger("ping", "pong")
mgr.agents["pong"] = Pinger("pong", "ping")
mgr.agents["ping"].broker = mgr
mgr.agents["pong"].broker = mgr
try:
    loop = mgr.dispatch("ping", "loop")
    check("depth guard: cyclic delegation terminates",
          "depth limit reached" in loop)
except RecursionError:
    check("depth guard: cyclic delegation terminates", False)

# CU6: a failed/canned/degenerate delegated output must NOT poison the caller —
# delegate() returns "" (consume() already skips empty), so the caller proceeds
# with no extra context instead of injecting garbage into its prompt.
from core.router import CANNED_FALLBACK


class _Canned(BaseAgent):
    distillable = False

    def execute(self, task):
        return CANNED_FALLBACK


class _Degen(BaseAgent):
    distillable = False

    def execute(self, task):
        return "[NO FINAL ANSWER GENERATED]\n\nThinking process..."


mgr.agents["canned-agent"] = _Canned("canned-agent", "test")
mgr.agents["degen-agent"] = _Degen("degen-agent", "test")
mgr.agents["canned-agent"].broker = mgr
mgr.agents["degen-agent"].broker = mgr

probe = StrategyAgent()
probe.broker = mgr
check("CU6: delegate returns '' on canned output",
      probe.delegate("canned-agent", "x") == "")
check("CU6: delegate returns '' on degenerate output",
      probe.delegate("degen-agent", "x") == "")
check("CU6: delegate still returns healthy output normally",
      probe.delegate("content-agent", "write something").strip() != "")


# Benchmark hygiene: distillation_suppressed() stops run() from distilling,
# without changing production behaviour outside the context.
from core.distillation_gate import distillation_suppressed

distill_calls.clear()
mgr.execute_task("content-agent", "write a launch post")
check("hygiene: distillation fires in production mode (gate enabled)",
      len(distill_calls) >= 1)

distill_calls.clear()
with distillation_suppressed():
    mgr.execute_task("content-agent", "write another launch post")
check("hygiene: distillation suppressed inside context (no vault writes)",
      distill_calls == [])

distill_calls.clear()
mgr.execute_task("content-agent", "write a third launch post")
check("hygiene: distillation restored after context exits",
      len(distill_calls) >= 1)


# CU7: a distillable agent distills at the TOP LEVEL (execute_task) but NOT when
# run as a SUBTASK via dispatch (so a plan writes one note, not one per subtask).
distill_calls.clear()
mgr.execute_task("content-agent", "top level note")
check("CU7: top-level run distills", len(distill_calls) == 1)

distill_calls.clear()
mgr.dispatch("content-agent", "subtask note")
check("CU7: dispatched subtask does NOT distill (no per-subtask pollution)",
      distill_calls == [])


print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
