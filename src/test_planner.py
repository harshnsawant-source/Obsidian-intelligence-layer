import sys

import core.planner as pl
from core.planner import Planner

PASS = []
FAIL = []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("PASS" if cond else "FAIL"), "-", name)


class FakeManager:
    def __init__(self):
        self.agents = {n: 1 for n in [
            "research-agent", "development-agent", "operations-agent",
            "content-agent", "retrieval-agent", "strategy-agent"]}
        self.calls = []

    def dispatch(self, name, task):
        self.calls.append((name, task))
        return f"OUTPUT[{name}]"


distill_calls = []


class FakeDistill:
    def execute(self, ctx, data):
        distill_calls.append(data.get("task"))
        return {"saved": "fake"}


# --- isolate: no Ollama, no real broker, no vault writes ---
pl.load_skill = lambda name: FakeDistill()
pl.RuntimeContext = lambda: None
pl.route_agent = lambda task: "operations-agent"

DECOMP = ('[{"id":1,"task":"research the market","agent":"research-agent",'
          '"depends_on":[]},'
          '{"id":2,"task":"build the prototype","agent":"development-agent",'
          '"depends_on":[1]}]')


def llm_with(decomp):
    def fake(prompt, *args, **kwargs):
        if "Final consolidated answer" in prompt:
            return "FINAL_SYNTHESIS"
        return decomp
    return fake


# Test 1: valid decomposition parses + normalizes
pl.query_llm = llm_with(DECOMP)
p = Planner(manager=FakeManager())
steps = p.decompose("launch a product")
check("decompose: parses 2 steps", len(steps) == 2)
check("decompose: agents valid", {s["agent"] for s in steps} ==
      {"research-agent", "development-agent"})
check("decompose: dependency captured", steps[1]["depends_on"] == [1])

# Test 2: unparseable output -> single-step fallback via route_agent
pl.query_llm = llm_with("sorry, no json here")
steps_fb = Planner(manager=FakeManager()).decompose("do a thing")
check("decompose: fallback to single step",
      len(steps_fb) == 1 and steps_fb[0]["agent"] == "operations-agent")

# Test 3: invalid agent name -> replaced by route_agent
pl.query_llm = llm_with('[{"id":1,"task":"x","agent":"wizard-agent","depends_on":[]}]')
steps_inv = Planner(manager=FakeManager()).decompose("x")
check("decompose: invalid agent replaced", steps_inv[0]["agent"] == "operations-agent")

# Test 4: MAX_STEPS cap
big = "[" + ",".join(
    f'{{"id":{i},"task":"t{i}","agent":"content-agent","depends_on":[]}}'
    for i in range(1, 11)) + "]"
pl.query_llm = llm_with(big)
steps_cap = Planner(manager=FakeManager()).decompose("many")
check("decompose: capped at MAX_STEPS", len(steps_cap) == Planner.MAX_STEPS)

# Test 5: execution respects dependency order + injects prior results
pl.query_llm = llm_with(DECOMP)
fm = FakeManager()
p2 = Planner(manager=fm)
results = p2.execute(p2.decompose("launch"))
order = [name for name, _ in fm.calls]
check("execute: dependency order (research before development)",
      order.index("research-agent") < order.index("development-agent"))
dev_task = [t for n, t in fm.calls if n == "development-agent"][0]
check("execute: prior result injected into dependent task",
      "Use these prior results" in dev_task and "OUTPUT[research-agent]" in dev_task)
check("execute: collects one result per step", len(results) == 2)

# Test 6: dependency cycle does not hang or crash
cycle = [
    {"id": 1, "task": "a", "agent": "content-agent", "depends_on": [2]},
    {"id": 2, "task": "b", "agent": "content-agent", "depends_on": [1]},
]
fm2 = FakeManager()
res_cycle = Planner(manager=fm2).execute(cycle)
check("execute: cycle handled, all steps still run", len(res_cycle) == 2)

# Test 7: full run() — synthesize + distill
pl.query_llm = llm_with(DECOMP)
distill_calls.clear()
outcome = Planner(manager=FakeManager()).run("launch a product")
check("run: returns final synthesis", outcome["final"] == "FINAL_SYNTHESIS")
check("run: plan distilled into vault", len(distill_calls) == 1 and
      distill_calls[0].startswith("[plan]"))

# ===================== Phase 4: sequential planner =====================

from core.execution_context import SharedExecutionContext
from core.planner import PlanExecutor
import agents.planner_agent as pa
from agents.planner_agent import PlannerAgent

# PlanExecutor (in pl) uses pl.route_agent (already stubbed above). PlannerAgent
# resolves route_agent + query_llm from its own module namespace.
pa.route_agent = lambda task: "operations-agent"


# Test 8: SharedExecutionContext shape — Phase-5 slots reserved + empty
sec = SharedExecutionContext("ship feature")
check("context: goal set", sec.goal == "ship feature")
check("context: outputs starts empty", sec.outputs == [])
check("context: phase-5 slots present and empty",
      sec.completed_steps == [] and sec.findings == []
      and sec.decisions == [] and sec.artifacts == {})
sec.record_output("research-agent", "do research", "R")
check("context: record_output populates outputs",
      len(sec.outputs) == 1 and sec.outputs[0]["output"] == "R")
check("context: record_output tracks completed_steps",
      sec.completed_steps[0]["agent"] == "research-agent")
check("context: render includes prior output + goal",
      "R" in sec.render() and "ship feature" in sec.render())
check("context: empty render before any output",
      SharedExecutionContext("g").render() == "")


# Test 9: PlanExecutor runs sequentially, threads context, feeds prior forward
fm3 = FakeManager()
plan = [
    {"task": "research the market", "agent": "research-agent"},
    {"task": "design the build", "agent": "development-agent"},
]
seen = []
ctx = PlanExecutor(manager=fm3).run(
    "launch", plan,
    progress_callback=lambda i, n, a, t: seen.append((i, a)))
order = [name for name, _ in fm3.calls]
check("executor: sequential order preserved",
      order == ["research-agent", "development-agent"])
check("executor: returns context with one output per step", len(ctx.outputs) == 2)
check("executor: completed_steps tracked", len(ctx.completed_steps) == 2)
dev_task = [t for n, t in fm3.calls if n == "development-agent"][0]
check("executor: prior result fed forward into later subtask",
      "OUTPUT[research-agent]" in dev_task
      and "shared execution context" in dev_task)
research_task = [t for n, t in fm3.calls if n == "research-agent"][0]
check("executor: first subtask carries no prior context",
      "shared execution context" not in research_task)
check("executor: progress callback fired per step",
      seen == [(1, "research-agent"), (2, "development-agent")])


# Test 10: PlanExecutor validates agent names -> route_agent fallback
fm4 = FakeManager()
PlanExecutor(manager=fm4).run("g", [{"task": "x", "agent": "wizard-agent"}])
check("executor: invalid agent replaced via route_agent",
      fm4.calls[0][0] == "operations-agent")


# Test 11: PlannerAgent.decompose parses flat [{task, agent}] + validates
pa.query_llm = lambda prompt, *a, **k: (
    '[{"task":"research","agent":"research-agent"},'
    '{"task":"build","agent":"development-agent"}]')
dsteps = PlannerAgent(manager=FakeManager()).decompose("launch")
check("planner-agent: decompose parses flat 2-step list", len(dsteps) == 2)
check("planner-agent: decompose is flat (no depends_on)",
      all(set(s.keys()) == {"task", "agent"} for s in dsteps))
check("planner-agent: decompose agents valid + ordered",
      [s["agent"] for s in dsteps] == ["research-agent", "development-agent"])


# Test 12: decompose invalid agent replaced; unparseable -> single-step fallback
pa.query_llm = lambda prompt, *a, **k: '[{"task":"x","agent":"nope-agent"}]'
check("planner-agent: invalid agent replaced",
      PlannerAgent(manager=FakeManager()).decompose("x")[0]["agent"]
      == "operations-agent")
pa.query_llm = lambda prompt, *a, **k: "definitely not json"
fbk = PlannerAgent(manager=FakeManager()).decompose("do a thing")
check("planner-agent: unparseable -> single-step fallback",
      len(fbk) == 1 and fbk[0]["agent"] == "operations-agent")


# Test 13: PlannerAgent.execute decomposes, runs sequentially, merges report
prog = []


def planner_query(prompt, *a, **k):
    if "Final combined report" in prompt:
        return "COMBINED_REPORT"
    return ('[{"task":"research","agent":"research-agent"},'
            '{"task":"build","agent":"development-agent"}]')


pa.query_llm = planner_query
fm5 = FakeManager()
pe_agent = PlannerAgent(manager=fm5)
pe_agent.progress_callback = lambda i, n, ag, t: prog.append(i)
report = pe_agent.execute("launch product")
check("planner-agent: execute returns merged combined report",
      report == "COMBINED_REPORT")
check("planner-agent: execute dispatched every subtask", len(fm5.calls) == 2)
check("planner-agent: progress shown for each step", prog == [1, 2])


# ===================== CU6: failure isolation =====================

from core.router import CANNED_FALLBACK


# record_degraded: failed step is recorded, NOT counted as an output, and is
# surfaced in render WITHOUT its garbage content.
secd = SharedExecutionContext("g")
secd.record_degraded("retrieval-agent", "lookup context", "canned_fallback")
check("CU6: record_degraded populates degraded_steps",
      len(secd.degraded_steps) == 1
      and secd.degraded_steps[0]["agent"] == "retrieval-agent")
check("CU6: degraded step is not an output", secd.outputs == [])
rd = secd.render()
check("CU6: degraded-only context renders the failure",
      "Degraded steps" in rd and "retrieval-agent" in rd)


class FailingManager:
    def __init__(self, fail_agent):
        self.agents = {n: 1 for n in [
            "research-agent", "development-agent", "operations-agent",
            "content-agent", "retrieval-agent", "strategy-agent"]}
        self.fail_agent = fail_agent
        self.calls = []

    def dispatch(self, name, task):
        self.calls.append((name, task))
        if name == self.fail_agent:
            return CANNED_FALLBACK
        return f"OUTPUT[{name}]"


fmgr = FailingManager(fail_agent="retrieval-agent")
plan_cu6 = [
    {"task": "retrieve context", "agent": "retrieval-agent"},
    {"task": "build it", "agent": "development-agent"},
]
ctx6 = PlanExecutor(manager=fmgr).run("goal", plan_cu6)
check("CU6: failed subtask kept out of outputs",
      [o["agent"] for o in ctx6.outputs] == ["development-agent"])
check("CU6: failed subtask recorded as degraded",
      len(ctx6.degraded_steps) == 1
      and ctx6.degraded_steps[0]["reason"] == "canned_fallback")
check("CU6: run continued past the failure",
      any(n == "development-agent" for n, _ in fmgr.calls))
dev_prompt = [t for n, t in fmgr.calls if n == "development-agent"][0]
check("CU6: canned text NOT threaded into downstream subtask",
      CANNED_FALLBACK not in dev_prompt)
check("CU6: downstream is told a prior step failed",
      "Degraded steps" in dev_prompt and "retrieval-agent" in dev_prompt)


print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
