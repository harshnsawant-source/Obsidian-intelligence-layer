from pathlib import Path
from datetime import datetime


BASE_DIR = Path(__file__).resolve().parent.parent.parent

OBJECTIVE_FILE = BASE_DIR / "runtime" / "active_objectives.md"


def add_objective(objective):

    timestamp = datetime.now()

    entry = f"""

## Objective

Created:
{timestamp}

Status:
active

Goal:
{objective}

"""

    if not OBJECTIVE_FILE.exists():

        OBJECTIVE_FILE.write_text(
            "# Active Objectives\n",
            encoding="utf-8"
        )

    with OBJECTIVE_FILE.open(
        "a",
        encoding="utf-8"
    ) as file:

        file.write(entry)

    print(
        "\nObjective added successfully."
    )


def show_objectives():

    print("\n=== ACTIVE OBJECTIVES ===\n")

    if not OBJECTIVE_FILE.exists():

        print(
            "No objectives available."
        )

        return

    content = OBJECTIVE_FILE.read_text(
        encoding="utf-8"
    )

    print(content)


if __name__ == "__main__":

    add_objective(
        "Build operational AI system"
    )

    show_objectives()