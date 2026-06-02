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

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
