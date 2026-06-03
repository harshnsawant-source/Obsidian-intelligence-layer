# An agent that can take actions. It is just a BaseAgent whose execute() runs
# the tool loop instead of a single LLM call — so it inherits routing/failover
# (query_llm), semantic context (build_context), auto-distillation and the
# verification gate (run()) for free. See TOOL_FRAMEWORK.md section 6.

from agents.base_agent import BaseAgent

from core.llm_engine import query_llm
from core.memory_writer import save_memory
from core.context_builder import build_context
from core.tools.loop import ToolRegistry, run_tool_loop
from core.tools.policy import Policy


class ToolAgent(BaseAgent):

    # Subclasses set `tools` (Tool instances) and, if they need a DANGEROUS
    # tool, name it in `allow`. sensitive=True flows into the policy, which
    # then disables all network tools (privacy) AND keeps the LLM local.
    tools = []
    allow = []
    max_tool_steps = 6

    def execute(self, task):

        registry = ToolRegistry(self.tools)

        policy = Policy(allow=self.allow, sensitive=self.sensitive)

        memory_context = build_context(task)

        framed = task

        if memory_context and str(memory_context).strip():
            framed = f"{task}\n\nRelevant memory:\n{memory_context}"

        def generate(prompt):
            return query_llm(prompt, sensitive=self.sensitive)

        result = run_tool_loop(
            generate,
            framed,
            registry,
            policy,
            max_steps=self.max_tool_steps,
        )

        final = result.final or ""

        save_memory(f"{self.name}_output", final)

        print(f"\n=== {self.name.upper()} (tools) ===\n")
        print(final)
        if not result.completed:
            print(
                f"\n[{self.name}] note: stopped after {result.steps} steps "
                f"without a final answer."
            )

        return final
