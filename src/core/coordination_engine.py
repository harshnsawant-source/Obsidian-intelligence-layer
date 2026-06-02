from pathlib import Path
from datetime import datetime


BASE_DIR = Path(__file__).resolve().parent.parent.parent

COORDINATION_LOG = (
    BASE_DIR
    / "runtime"
    / "coordination_log.md"
)


def coordinate_agents(

    source_agent,
    target_agent,
    task

):

    entry = f"""

## Coordination Event

Timestamp:
{datetime.now()}

Source Agent:
{source_agent}

Target Agent:
{target_agent}

Task:
{task}

"""

    if not COORDINATION_LOG.exists():

        COORDINATION_LOG.write_text(
            "# Agent Coordination Log\n",
            encoding="utf-8"
        )

    with COORDINATION_LOG.open(
        "a",
        encoding="utf-8"
    ) as file:

        file.write(entry)

    print(
        "\nAgent coordination recorded."
    )


def show_coordination_history():

    print(
        "\n=== AGENT COORDINATION ===\n"
    )

    if not COORDINATION_LOG.exists():

        print(
            "No coordination history available."
        )

        return

    content = COORDINATION_LOG.read_text(
        encoding="utf-8"
    )

    print(content)


if __name__ == "__main__":

    coordinate_agents(

        "development-agent",

        "retrieval-agent",

        "retrieve UI inspiration memory"
    )

    show_coordination_history()