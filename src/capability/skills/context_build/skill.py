def execute(

    ctx,
    input_data

):

    task = input_data.get(

        "task",

        ""

    )

    memories = input_data.get(

        "memories",

        []

    )

    knowledge = input_data.get(

        "knowledge",

        []

    )

    context = f"""

TASK

{task}

MEMORIES

{memories}

KNOWLEDGE

{knowledge}

"""

    return {

        "context": context

    }