from agents.development_agent import (
    DevelopmentAgent
)

from agents.retrieval_agent import (
    RetrievalAgent
)

from agents.operations_agent import (
    OperationsAgent
)

from agents.content_agent import (
    ContentAgent
)

from agents.research_agent import (
    ResearchAgent
)

from agents.strategy_agent import (
    StrategyAgent
)


class AgentManager:

    # Cap how deep agent-to-agent delegation may recurse, so a chain (or an
    # accidental cycle) can never loop forever.
    MAX_DELEGATION_DEPTH = 3

    def __init__(self):

        self.agents = {

            "development-agent":
            DevelopmentAgent(),

            "retrieval-agent":
            RetrievalAgent(),

            "operations-agent":
            OperationsAgent(),

            "content-agent":
            ContentAgent(),

            "research-agent":
            ResearchAgent(),

            "strategy-agent":
            StrategyAgent()
        }

        # Act as the broker: let every agent reach its siblings.
        self._depth = 0

        for agent in self.agents.values():

            agent.broker = self

    def dispatch(
        self,
        agent_name,
        task
    ):

        # Agent-to-agent entrypoint. Runs the target agent through its full
        # run() pipeline (so distillation is preserved) under a depth guard.

        if self._depth >= self.MAX_DELEGATION_DEPTH:

            return (
                f"[delegation depth limit reached at {agent_name}]"
            )

        agent = self.agents.get(agent_name)

        if not agent:

            return f"[unknown agent: {agent_name}]"

        self._depth += 1

        try:

            return agent.run(task)

        finally:

            self._depth -= 1

    def execute_task(

        self,
        agent_name,
        task

    ):

        agent = self.agents.get(
            agent_name
        )

        if not agent:

            print(
                "\nAgent not found."
            )

            return

        return agent.run(task)

    def show_agents(self):

        print(
            "\n=== ACTIVE AGENTS ===\n"
        )

        for name in self.agents:

            print(f"[ACTIVE] {name}")


if __name__ == "__main__":

    manager = AgentManager()

    manager.show_agents()

    manager.execute_task(

        "development-agent",

        "build AI dashboard"
    )