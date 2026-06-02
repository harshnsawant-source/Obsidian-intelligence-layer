from capability.core.runtime_context import RuntimeContext
from capability.core.skill_loader import load_skill

from core.llm_engine import query_llm


class AgentExecutor:

    def __init__(self):

        self.ctx = RuntimeContext()

    def run(

        self,
        task

    ):

        print(
            "\n=== AGENT EXECUTOR ===\n"
        )

        memory_recall = load_skill(

            "memory_recall"

        )

        context_build = load_skill(

            "context_build"

        )

        knowledge_distill = load_skill(

            "knowledge_distill"

        )

        recall_results = (

            memory_recall.execute(

                self.ctx,

                {

                    "query": task

                }

            )

        )

        context = (

            context_build.execute(

                self.ctx,

                {

                    "task": task,

                    "memories": recall_results,

                    "knowledge": []

                }

            )

        )

        print(
            "\n=== CONTEXT ===\n"
        )

        print(
            context["context"]
        )

        prompt = f"""
Answer directly.

Task:

{task}

Context:

{context['context']}

Requirements:

1. Recommended approach
2. Architecture
3. Implementation plan

IMPORTANT RULES:

- Do NOT output thinking process.
- Do NOT explain reasoning.
- Do NOT show analysis.
- Output only the final answer.
- Start immediately with section 1.

FINAL ANSWER:
"""

        print(
            "\n=== PROMPT ===\n"
        )

        print(
            prompt
        )

        result = query_llm(

            prompt

        )

        self.ctx.trace.log(

            "agent_executor",

            task,

            result

        )

        knowledge_distill.execute(

            self.ctx,

            {

                "task": task,

                "outcome": result

            }

        )

        print(
            "\n=== FINAL OUTPUT ===\n"
        )

        print(
            result
        )

        return result