from agents.base_agent import BaseAgent


class ResearchAgent(BaseAgent):

    # Phase 5: research surfaces findings (and may flag risks/assumptions).
    contributes = ["findings", "risks", "assumptions"]

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
