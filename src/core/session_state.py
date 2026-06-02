from pathlib import Path
from datetime import datetime


BASE_DIR = Path(__file__).resolve().parent.parent.parent

STATE_FILE = BASE_DIR / "runtime" / "session_state.md"


def update_session_state(task, workflow):

    content = f"""

# Active Session State

Updated:
{datetime.now()}

## Current Task

{task}

## Active Workflow

{workflow}

## Operational Mode

creation-focused

## System Direction

Building AI operational intelligence systems.

"""

    STATE_FILE.write_text(
        content,
        encoding="utf-8"
    )

    print(
        "\nSession state updated."
    )


if __name__ == "__main__":

    update_session_state(
        "test task",
        "creation"
    )