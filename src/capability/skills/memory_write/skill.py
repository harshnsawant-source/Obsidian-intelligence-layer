def execute(

    ctx,
    input_data

):

    filename = (

        input_data.get(

            "filename",

            "memory.md"

        )

    )

    content = (

        input_data.get(

            "content",

            ""

        )

    )

    saved = ctx.memory.write(

        "working",

        filename,

        content

    )

    return {

        "status": "success",

        "saved": saved

    }