from core.llm_engine import query_llm


class Skill:

    name = "knowledge_extract"

    def execute(

        self,
        ctx,
        params

    ):

        task = params.get(

            "task",
            ""

        )

        outcome = params.get(

            "outcome",
            ""

        )

        prompt = f"""

Task:

{task}

Outcome:

{outcome}

Extract only reusable knowledge.

Format:

Pattern:
...

Lesson:
...

Recommendation:
...

Tags:
...
"""

        result = query_llm(

            prompt

        )

        return {

            "knowledge": result

        }


skill = Skill()


def execute(

    ctx,
    params

):

    return skill.execute(

        ctx,
        params

    )