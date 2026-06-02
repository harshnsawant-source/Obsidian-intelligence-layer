from pathlib import Path
from datetime import datetime


BASE_DIR = Path(__file__).resolve().parent.parent.parent

TASK_FILE = BASE_DIR / "runtime" / "task_queue.md"


def create_task(task):

    timestamp = datetime.now()

    entry = f"""

## Task

Created:
{timestamp}

Status:
pending

Task:
{task}

"""

    if not TASK_FILE.exists():

        TASK_FILE.write_text(
            "# Operational Task Queue\n",
            encoding="utf-8"
        )

    with TASK_FILE.open(
        "a",
        encoding="utf-8"
    ) as file:

        file.write(entry)

    print(
        "\nTask added successfully."
    )


def view_tasks():

    print("\n=== TASK QUEUE ===\n")

    if not TASK_FILE.exists():

        print(
            "No tasks available."
        )

        return

    content = TASK_FILE.read_text(
        encoding="utf-8"
    )

    print(content)


if __name__ == "__main__":

    create_task(
        "Build operational dashboard"
    )

    view_tasks()