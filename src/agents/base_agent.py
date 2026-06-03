from datetime import datetime

from capability.core.runtime_context import RuntimeContext
from capability.core.skill_loader import load_skill

from core.llm_engine import query_llm
from core.memory_writer import save_memory
from core.context_builder import build_context
from core.verification import refine


class BaseAgent:

    # Subclasses set distillable = False to opt OUT of writing their
    # output back into the knowledge vault. Retrieval-style agents do
    # this: their output is a re-synthesis of existing vault knowledge,
    # so distilling it back in would create a self-referential feedback
    # loop that degrades search/recall quality over time.
    distillable = True

    # Subclasses set sensitive = True to pin their LLM calls to LOCAL models
    # only (privacy) — used by agents that reason over personal memory/notes.
    sensitive = False

    # Subclasses set verifiers = [Verifier(), ...] to opt INTO the
    # generate -> verify -> correct loop. Empty (the default) means a single
    # LLM call and no behavior change — verification is strictly additive.
    verifiers = []

    # Max generate attempts when verifiers are present (1 generate + retries).
    max_verify_tries = 2

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

        # Verdict from the most recent query_agent run; None when no verifier
        # ran. run() reads this to gate distillation.
        self.last_verdict = None

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

        base_prompt = f"""
You are a {role}.

{instructions}

{delegated}Relevant Memory:

{memory_context}

Task:

{task}

Provide a complete, actionable response.
"""

        # Generation closure: re-issues the prompt with the verifier's feedback
        # appended on a correction pass. With no verifiers this is called once.
        def generate(feedback, previous):
            prompt = base_prompt
            if feedback:
                prompt += f"""

Your previous attempt did not pass verification:

--- previous attempt ---
{previous}
--- end ---

Fix these specific problems and return a corrected response:
{feedback}
"""
            return query_llm(prompt, sensitive=self.sensitive)

        outcome = refine(
            generate,
            task,
            verifiers=self.verifiers,
            max_tries=self.max_verify_tries,
        )

        self.last_verdict = outcome.verdict

        result = outcome.output

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

        # Gate the learning loop on verification: only distill output that did
        # not FAIL a verifier. last_verdict is None when no verifier ran (the
        # default), which preserves the original always-distill behavior. A
        # failed verdict keeps bad output out of the vault, stopping errors
        # from compounding through retrieval. See VERIFICATION.md section 5.2.
        verified = self.last_verdict is None or self.last_verdict.ok

        if (
            self.distillable
            and verified
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

        elif self.distillable and not verified:

            print(
                f"\n[{self.name}] skipped distillation - output failed "
                f"verification (not added to the knowledge vault)."
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
