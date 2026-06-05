import re

from core.agent_manager import (
    AgentManager
)


manager = AgentManager()


# Ordered by priority: on a score tie, the earlier agent wins.
ROUTES = [

    ("development-agent", [
        "build", "website", "ui",
        "dashboard", "frontend", "design",
        # Code intent — without these, "write a python FUNCTION" matched
        # "write" -> content-agent (see CU bypass review). Coding now routes
        # here. Agent selection stays centralized in route_agent (no second
        # code-detector system).
        "function", "implement", "code", "coding", "python",
        "script", "algorithm", "class", "debug", "fix", "refactor"
    ]),

    ("retrieval-agent", [
        "memory", "retrieve", "context", "search"
    ]),

    ("operations-agent", [
        "workflow", "system", "operations", "runtime"
    ]),

    ("content-agent", [
        "content", "post", "write", "marketing"
    ]),

    ("research-agent", [
        "research", "analyze", "analysis",
        "investigate", "study", "compare", "evaluate"
    ]),

    ("strategy-agent", [
        "strategy", "strategic", "roadmap",
        "business", "growth", "vision", "plan"
    ]),
]


def route_agent(task):

    # Whole-word matching (not substring, so "research" never trips the
    # "search" keyword), and best-score selection so multi-intent tasks
    # go to the agent with the strongest signal rather than first match.

    words = set(
        re.findall(r"[a-z]+", task.lower())
    )

    best_agent = "operations-agent"

    best_score = 0

    for agent, keywords in ROUTES:

        score = len(
            words.intersection(keywords)
        )

        if score > best_score:

            best_score = score

            best_agent = agent

    return best_agent


# Deliverable verbs used to detect "multiple distinct deliverables". Counting
# DISTINCT verbs (not occurrences) keeps "write a function" (one verb) on the
# direct path while "design X and build Y" (two verbs + 'and') escalates.
_DELIVERABLE_VERBS = {
    "build", "create", "write", "design", "implement", "develop",
    "document", "deploy", "test", "research", "analyze", "compare",
}


def needs_planning(task):

    # DETERMINISTIC planner gate (no LLM). Decides ONLY planner vs direct — it
    # never chooses an agent (that stays in route_agent). Default is DIRECT
    # (cheapest sufficient path); escalate to the planner ONLY on strong,
    # explicit multi-deliverable / multi-step / multi-file evidence.

    t = (task or "").lower()

    # 1. Explicit decomposition request, or a numbered/bulleted multi-step list.
    if re.search(r"\b(decompose|break\s+(it\s+)?down)\b", t):
        return True
    if re.search(r"\binto\s+(at\s+least\s+)?\d+\s+(steps|tasks|parts|subtasks)\b", t):
        return True
    if len(re.findall(r"(?m)^\s*\d+[\.\)]\s+", task or "")) >= 2:
        return True
    if len(re.findall(r"(?m)^\s*[-*]\s+", task or "")) >= 2:
        return True

    # 2. Multi-file / multi-module / multi-component work.
    if re.search(
        r"\b(multiple|several|many)\s+(files|modules|components|services|endpoints)\b", t
    ):
        return True
    if re.search(r"\bacross\s+(multiple\s+|the\s+)?(files|modules|codebase|services)\b", t):
        return True
    if "each of" in t:
        return True

    # 3. Multiple distinct deliverables joined ("design X AND build Y").
    if " and " in t:
        words = set(re.findall(r"[a-z]+", t))
        if len(words.intersection(_DELIVERABLE_VERBS)) >= 2:
            return True

    return False


def dispatch(task):

    # Single entry point that applies the cheapest sufficient path: a direct
    # single-agent run by default, the PlannerAgent only when needs_planning()
    # finds strong evidence planning is required. This is a SELECTOR over the
    # two mechanisms that already exist — it adds no agent-selection logic
    # (route_agent) and no new orchestration. Returns the result string.

    if needs_planning(task):
        # Lazy import: PlannerAgent imports route_agent from this module, so a
        # top-level import would be circular.
        from agents.planner_agent import PlannerAgent
        return PlannerAgent().run(task)

    return manager.dispatch(route_agent(task), task)


def execute_agent_task(task):

    assigned_agent = route_agent(task)

    print(
        f"\nAssigned Agent: {assigned_agent}"
    )

    manager.execute_task(

        assigned_agent,
        task
    )


def show_agent_status():

    manager.show_agents()


if __name__ == "__main__":

    execute_agent_task(

        "build futuristic AI dashboard"
    )