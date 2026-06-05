import sys

import core.agent_engine as ae
from core.agent_engine import route_agent, needs_planning

PASS = []
FAIL = []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("PASS" if cond else "FAIL"), "-", name)


# --- ROUTES extension: coding now routes to development-agent ---------------
check("route: 'Write a Python function to reverse a string' -> development",
      route_agent("Write a Python function to reverse a string") == "development-agent")
check("route: 'Implement quicksort' -> development",
      route_agent("Implement quicksort") == "development-agent")
check("route: 'Debug this Python code' -> development",
      route_agent("Debug this Python code") == "development-agent")
check("route: 'Research cloud pricing' -> research",
      route_agent("Research cloud pricing") == "research-agent")
check("route: 'Write a blog post' -> content",
      route_agent("Write a blog post") == "content-agent")
check("route: existing 'build a dashboard' still -> development",
      route_agent("build an analytics dashboard") == "development-agent")


# --- needs_planning: DIRECT by default (cheapest sufficient path) ------------
check("plan: single coding function -> direct",
      needs_planning("Write a Python function to reverse a string") is False)
check("plan: implement quicksort -> direct",
      needs_planning("Implement quicksort") is False)
check("plan: single research question -> direct",
      needs_planning("Research cloud pricing") is False)
check("plan: plain explanation -> direct",
      needs_planning("Explain how TCP congestion control works") is False)
check("plan: 'and' without two deliverables -> direct",
      needs_planning("Write a function to reverse a string and return it") is False)


# --- needs_planning: PLANNER only on strong, explicit signals ---------------
check("plan: explicit decomposition request -> planner",
      needs_planning("Decompose the goal of auditing a web app into at least 3 tasks") is True)
check("plan: multiple distinct deliverables -> planner",
      needs_planning("Design a database schema and build the API and write the docs") is True)
check("plan: numbered multi-step list -> planner",
      needs_planning("Do this:\n1. set up CI\n2. add tests\n3. deploy") is True)
check("plan: bulleted multi-step list -> planner",
      needs_planning("Tasks:\n- provision servers\n- configure DNS") is True)
check("plan: multi-file refactor -> planner",
      needs_planning("Refactor authentication across multiple files") is True)
check("plan: 'each of' work -> planner",
      needs_planning("Add logging to each of the service modules") is True)


# --- dispatch: SELECTOR wiring (no real LLM calls) --------------------------
calls = {}


def fake_manager_dispatch(name, task):
    calls["agent"] = name
    calls["task"] = task
    return f"DIRECT[{name}]"


ae.manager.dispatch = fake_manager_dispatch

out = ae.dispatch("Write a Python function to reverse a string")
check("dispatch: direct path = route_agent + manager.dispatch",
      out == "DIRECT[development-agent]" and calls.get("agent") == "development-agent")

# Planner path: stub PlannerAgent (dispatch lazy-imports it).
import agents.planner_agent as pa


class _FakePlanner:
    def run(self, task):
        return f"PLAN[{task}]"


_real_planner = pa.PlannerAgent
pa.PlannerAgent = _FakePlanner
try:
    out2 = ae.dispatch("Design a database schema and build the API and write the docs")
    check("dispatch: planner path invokes PlannerAgent.run",
          out2.startswith("PLAN["))
    # And a direct task does NOT touch the planner.
    calls.clear()
    out3 = ae.dispatch("Implement quicksort")
    check("dispatch: direct task bypasses the planner",
          out3 == "DIRECT[development-agent]")
finally:
    pa.PlannerAgent = _real_planner


print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
