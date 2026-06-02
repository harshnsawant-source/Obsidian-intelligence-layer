from agents.base_agent import BaseAgent


class ContentAgent(BaseAgent):

    def __init__(self):

        super().__init__(
            "content-agent",
            "content-generation"
        )

    def execute(
        self,
        task
    ):

        return self.query_agent(
            task,
            role="Content Strategist",
            instructions=(
                "Produce clear, structured, audience-appropriate "
                "content with a strong narrative and concrete examples."
            )
        )
