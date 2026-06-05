from datetime import datetime

from pathlib import Path


# Default sink for agent output dumps. Kept as a module-level global (rather than
# computed inline) so a benchmark/test harness can redirect ALL writes to an
# isolated directory by patching this one name — see core/eval/benchmark_vault.py.
MEMORIES_DIR = Path(__file__).parent.parent.parent / "memories"


def save_memory(

    title,

    content

):

    memory_dir = MEMORIES_DIR

    memory_dir.mkdir(

        parents=True,

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
