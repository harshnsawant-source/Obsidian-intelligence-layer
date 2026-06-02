from agents.base_agent import BaseAgent


class ResearchAgent(BaseAgent):

    def __init__(self):

        super().__init__(
            "research-agent",
            "deep-research"
        )

    def execute(
        self,
        task
    ):

        return self.query_agent(
            task,
            role="Research Expert",
            instructions=(
                "Perform deep analysis. Compare options, weigh "
                "trade-offs with evidence, and surface risks, "
                "unknowns, and open questions."
            )
        )
