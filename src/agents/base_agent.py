from datetime import datetime

from capability.core.runtime_context import RuntimeContext
from capability.core.skill_loader import load_skill

from core.llm_engine import query_llm
from core.memory_writer import save_memory
from core.context_builder import build_context


class BaseAgent:

    # Subclasses set distillable = False to opt OUT of writing their
    # output back into the knowledge vault. Retrieval-style agents do
    # this: their output is a re-synthesis of existing vault knowledge,
    # so distilling it back in would create a self-referential feedback
    # loop that degrades search/recall quality over time.
    distillable = True

    def __init__(
        self,
        name,
        specialty
    ):

        self.name = name

        self.specialty = specialty

        self.created = datetime.now()

        # Set by AgentManager so an agent can reach its siblings. None when
        # an agent runs standalone, in which case delegation is a no-op.
        self.broker = None

    def delegate(self, agent_name, task):

        # Hand a sub-task to another agent and return its result string.
        # Safe no-op if there is no broker, or if asked to call itself.
        if not self.broker or agent_name == self.name:
            return ""

        return self.broker.dispatch(agent_name, task)

    def consume(self, agent_names, task):

        # Run several upstream agents and aggregate their outputs as a
        # single context block this agent can reason over.
        parts = []

        for agent_name in agent_names:

            output = self.delegate(agent_name, task)

            if output and str(output).strip():

                parts.append(
                    f"### From {agent_name}\n\n{output}"
                )

        return "\n\n".join(parts)

    def query_agent(
        self,
        task,
        role=None,
        instructions="",
        output_name=None,
        extra_context=""
    ):

        # Shared execution pipeline used by EVERY agent:
        #   build memory context -> call LLM -> persist output -> return.
        # Subclasses customise only role / instructions / task framing.

        role = role or self.specialty

        memory_context = build_context(task)

        delegated = ""

        if extra_context and str(extra_context).strip():

            delegated = (
                f"Input from other agents:\n\n{extra_context}\n\n"
            )

        prompt = f"""
You are a {role}.

{instructions}

{delegated}Relevant Memory:

{memory_context}

Task:

{task}

Provide a complete, actionable response.
"""

        result = query_llm(prompt)

        output_name = output_name or f"{self.name}_output"

        memory_file = save_memory(
            output_name,
            result
        )

        print(
            f"\n=== {self.name.upper()} ===\n"
        )

        print(result)

        print(
            f"\nSaved to: {memory_file}"
        )

        return result

    def execute(
        self,
        task
    ):

        # Generic default so ANY future agent works with zero extra code:
        # define name + specialty and you inherit the full pipeline.
        # Subclasses override this only to customise role / instructions.

        return self.query_agent(
            task,
            role=self.specialty,
            instructions=(
                "Provide expert analysis and a concrete, "
                "actionable plan."
            )
        )

    def run(
        self,
        task
    ):

        # Public entrypoint. Runs the agent's logic, then automatically
        # distills the returned output into the knowledge vault so recall
        # + contextual search can see it (unless the agent opts out).

        result = self.execute(task)

        if (
            self.distillable
            and isinstance(result, str)
            and result.strip()
        ):

            ctx = RuntimeContext()

            knowledge_distill = load_skill(
                "knowledge_distill"
            )

            knowledge_distill.execute(
                ctx,
                {
                    "task": task,
                    "outcome": result
                }
            )

        return result

    def status(self):

        print(
            f"\nAgent: {self.name}"
        )

        print(
            f"Specialty: {self.specialty}"
        )

        print(
            f"Created: {self.created}"
        )
