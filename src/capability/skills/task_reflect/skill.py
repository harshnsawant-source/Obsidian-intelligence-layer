from core.llm_engine import query_llm


class Skill:

    name = "task_reflect"

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

Analyze:

1. What worked?
2. What failed?
3. Reusable patterns
4. Future recommendations
"""

        reflection = query_llm(

            prompt

        )

        return {

            "reflection": reflection

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