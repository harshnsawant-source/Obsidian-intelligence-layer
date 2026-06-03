from agents.base_agent import BaseAgent


class StrategyAgent(BaseAgent):

    # Phase 5: strategy records decisions (and may flag risks/assumptions).
    contributes = ["decisions", "risks", "assumptions"]

    def __init__(self):

        super().__init__(
            "strategy-agent",
            "business-strategy"
        )

    def execute(
        self,
        task
    ):

        # Delegate the analysis groundwork to the research agent, then build
        # the strategy on top of its findings.
        research = self.delegate(
            "research-agent",
            f"Provide research and analysis to support: {task}"
        )

        return self.query_agent(
            task,
            role="Strategy Expert",
            instructions=(
                "Create business and technical roadmaps. Define "
                "goals, milestones, sequencing, and success metrics."
            ),
            extra_context=research
        )
