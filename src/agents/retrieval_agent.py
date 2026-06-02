from agents.base_agent import BaseAgent


class RetrievalAgent(BaseAgent):

    # Opt out of distillation: this agent synthesises an answer FROM the
    # vault, so writing it back would pollute the vault with echoes of
    # its own contents. It still returns a string and uses the shared
    # pipeline like every other agent.
    distillable = False

    def __init__(self):

        super().__init__(
            "retrieval-agent",
            "context-retrieval"
        )

    def execute(
        self,
        task
    ):

        return self.query_agent(
            task,
            role="Context Retrieval Analyst",
            instructions=(
                "Synthesise the most relevant prior knowledge for the "
                "task from the provided memory. Cite what is known and "
                "flag gaps. Do not invent facts that are not supported."
            )
        )
