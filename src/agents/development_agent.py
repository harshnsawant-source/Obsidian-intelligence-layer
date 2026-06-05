from agents.base_agent import BaseAgent


class DevelopmentAgent(
    BaseAgent
):

    # Phase 5: development produces artifacts (and may flag risks/assumptions).
    contributes = ["artifacts", "risks", "assumptions"]

    # CU4: development's primary output is code -> cloud-pin (local is unreliable
    # for code generation). Privacy still wins if this agent were ever sensitive.
    produces_code = True

    def __init__(self):

        super().__init__(
            "development-agent",
            "software-development"
        )

    def execute(
        self,
        task
    ):

        # Request relevant context from the retrieval agent before designing.
        retrieved = self.delegate(
            "retrieval-agent",
            task
        )

        return self.query_agent(
            task,
            role="Senior Software Architect",
            instructions=(
                "Recommend an approach, design the architecture, "
                "and provide concrete implementation steps."
            ),
            output_name="development_output",
            extra_context=retrieved
        )
