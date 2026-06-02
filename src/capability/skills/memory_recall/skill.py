from pathlib import Path


def execute(

    ctx,
    input_data

):

    query = (

        input_data.get(
            "query",
            ""
        ).lower()

    )

    results = []

    memory_root = (

        ctx.memory.root
    )

    for file in memory_root.rglob("*.md"):

        try:

            content = file.read_text(

                encoding="utf-8"

            )

            if query in content.lower():

                results.append({

                    "file": str(file),

                    "content": content[:1000]

                })

        except:

            pass

    return {

        "query": query,

        "matches": results

    }