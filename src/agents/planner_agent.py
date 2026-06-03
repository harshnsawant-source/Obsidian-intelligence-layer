# PlannerAgent — a planning LAYER above the agent pool.
#
#   1. decompose the goal into an ordered, flat [{task, agent}] plan
#   2. run it sequentially via PlanExecutor (each subtask auto-distills through
#      the normal agent run() pipeline — "every subtask result is distilled")
#   3. merge the collected outputs into one final combined report
#
# It is a BaseAgent, so its FINAL report inherits the distillation gate via
# run() (the report itself lands in the vault too). It is deliberately NOT
# registered in AgentManager / the route table: it sits ABOVE the agents, so a
# subtask can never be routed back into the planner and recurse.
#
# decompose/merge call query_llm directly (not query_agent): decomposition needs
# fmt="json" and must not be polluted by semantic-memory context injection.

from agents.base_agent import BaseAgent

from core.llm_engine import query_llm
from core.agent_manager import AgentManager
from core.agent_engine import route_agent
from core.planner import PlanExecutor
from core.verifiers import extract_json
from core.log import get_logger


log = get_logger("planner-agent")


class PlannerAgent(BaseAgent):

    MAX_STEPS = 6

    def __init__(self, manager=None):

        super().__init__("planner-agent", "task-planning")

        self.manager = manager or AgentManager()

        self.executor = PlanExecutor(self.manager)

        # Set by callers (e.g. the menu) to display progress; None = silent.
        self.progress_callback = None

    # ---- decomposition (flat, sequential) -----------------------------

    def decompose(self, goal):

        agents = ", ".join(sorted(self.manager.agents))

        prompt = (
            f"Decompose the goal into 2 to {self.MAX_STEPS} concrete subtasks, "
            f"ordered so each step can build on the previous ones.\n"
            f"Return ONLY a JSON array; each element is "
            f'{{"task": "<what to do>", "agent": "<one of: {agents}>"}}.\n'
            f"Execution order = array order. No prose, no markdown fences.\n\n"
            f"Goal:\n{goal}"
        )

        raw = query_llm(prompt, fmt="json", max_tokens=1200)

        return self._normalize(extract_json(raw), goal)

    def _normalize(self, data, goal):

        steps = data if isinstance(data, list) else []

        normalized = []

        for raw in steps[: self.MAX_STEPS]:

            if not isinstance(raw, dict):
                continue

            task = str(raw.get("task", "")).strip()

            if not task:
                continue

            agent = raw.get("agent")

            if agent not in self.manager.agents:
                agent = route_agent(task)

            normalized.append({"task": task, "agent": agent})

        if not normalized:

            log.warning("decomposition unparseable; single-step fallback")

            normalized = [{"task": goal, "agent": route_agent(goal)}]

        return normalized

    # ---- merge --------------------------------------------------------

    def merge(self, goal, ctx):

        # Reason over the BOUNDED structured context (findings/decisions/
        # artifacts/risks/assumptions + recent outputs), not raw text only, so
        # the planner consolidates accumulated reasoning — within a budget.
        context_view = ctx.render_summary()

        prompt = (
            "Combine the accumulated reasoning into a single, coherent report "
            "that fully addresses the goal. Integrate the findings, decisions, "
            "artifacts, and risks into one narrative — do not merely list them.\n\n"
            f"Goal:\n{goal}\n\n"
            f"Accumulated context:\n{context_view}\n\n"
            f"Final combined report:"
        )

        return query_llm(prompt, max_tokens=8000)

    # ---- BaseAgent hook ----------------------------------------------

    def execute(self, task):

        # decompose -> execute sequentially (collecting outputs into the shared
        # context) -> merge. Returned report is distilled by BaseAgent.run().

        plan = self.decompose(task)

        ctx = self.executor.run(
            task,
            plan,
            progress_callback=self.progress_callback,
        )

        return self.merge(task, ctx)
