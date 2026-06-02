from datetime import datetime

from pathlib import Path


def save_memory(

    title,

    content

):

    memory_dir = Path(

        __file__

    ).parent.parent.parent / "memories"

    memory_dir.mkdir(

        exist_ok=True

    )

    filename = (

        memory_dir /

        f"{title}.md"

    )

    with open(

        filename,

        "w",

        encoding="utf-8"

    ) as file:

        file.write(

            f"# {title}\n\n"

        )

        file.write(

            f"Created: {datetime.now()}\n\n"

        )

        file.write(

            content

        )

    return str(

        filename

    )