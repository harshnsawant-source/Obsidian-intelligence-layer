from pathlib import Path


def search_memory(keyword):

    memory_dir = Path(

        __file__

    ).parent.parent.parent / "memories"

    matches = []

    for file in memory_dir.glob("*.md"):

        content = file.read_text(

            encoding="utf-8"

        )

        if keyword.lower() in content.lower():

            matches.append(

                str(file)

            )

    return matches