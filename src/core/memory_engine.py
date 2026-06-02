from pathlib import Path
from datetime import datetime


BASE_DIR = Path(__file__).resolve().parent.parent.parent

MEMORY_LOG = BASE_DIR / "memory" / "workflow_memory.md"


def store_memory(task, workflow):

    entry = f"""

## Workflow Event

Timestamp:
{datetime.now()}

Task:
{task}

Detected Workflow:
{workflow}

"""

    if not MEMORY_LOG.exists():

        MEMORY_LOG.write_text(
            "# Workflow Memory\n",
            encoding="utf-8"
        )

    with MEMORY_LOG.open(
        "a",
        encoding="utf-8"
    ) as file:

        file.write(entry)

    print(
        "\nWorkflow memory stored."
    )


if __name__ == "__main__":

    store_memory(
        "test task",
        "creation"
    )