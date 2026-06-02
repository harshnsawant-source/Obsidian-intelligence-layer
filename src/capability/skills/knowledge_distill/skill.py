from datetime import datetime


def execute(

    ctx,
    input_data

):

    task = input_data.get(

        "task",

        ""

    )

    outcome = input_data.get(

        "outcome",

        ""

    )

    lesson = f"""

# Knowledge Distillation

Date:
{datetime.now()}

Task:
{task}

Outcome:
{outcome}

Learning:
{outcome}

"""

    filename = (

        f"knowledge_{datetime.now().timestamp()}.md"

    )

    saved = ctx.knowledge.write(

        filename,

        lesson

    )

    return {

        "saved": saved

    }