from agents.base_agent import BaseAgent


class OperationsAgent(BaseAgent):

    def __init__(self):

        super().__init__(
            "operations-agent",
            "system-operations"
        )

    def execute(
        self,
        task
    ):

        # Efficiency: rather than re-running peer agents live (which fans out
        # into several extra LLM calls), consume their already-distilled
        # outputs from the shared knowledge vault. query_agent's semantic
        # build_context retrieves the most relevant prior agent outputs in a
        # single vector lookup -- one LLM call instead of four.
        return self.query_agent(
            task,
            role="Operations Expert",
            instructions=(
                "Improve workflows, scalability, and reliability. "
                "Build on the relevant prior research and development "
                "knowledge surfaced from memory. Identify operational "
                "risks and propose mitigations."
            )
        )
