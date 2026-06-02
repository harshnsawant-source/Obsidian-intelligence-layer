import re

from core.agent_manager import (
    AgentManager
)


manager = AgentManager()


# Ordered by priority: on a score tie, the earlier agent wins.
ROUTES = [

    ("development-agent", [
        "build", "website", "ui",
        "dashboard", "frontend", "design"
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