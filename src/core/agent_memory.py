from pathlib import Path
from datetime import datetime


BASE_DIR = Path(__file__).resolve().parent.parent.parent

AGENT_MEMORY_DIR = BASE_DIR / "memory" / "agents"

AGENT_MEMORY_DIR.mkdir(
    parents=True,
    exist_ok=True
)


def store_agent_memory(agent, task):

    file_path = AGENT_MEMORY_DIR / f"{agent}.md"

    entry = f"""

## Agent Activity

Timestamp:
{datetime.now()}

Task:
{task}

"""

    if not file_path.exists():

        file_path.write_text(
            f"# {agent}\n",
            encoding="utf-8"
        )

    with file_path.open(
        "a",
        encoding="utf-8"
    ) as file:

        file.write(entry)

    print(
        f"\nMemory updated for {agent}"
    )


def show_agent_memory(agent):

    file_path = AGENT_MEMORY_DIR / f"{agent}.md"

    print(f"\n=== {agent.upper()} MEMORY ===\n")

    if not file_path.exists():

        print(
            "No memory available."
        )

        return

    content = file_path.read_text(
        encoding="utf-8"
    )

    print(content)


if __name__ == "__main__":

    store_agent_memory(
        "development-agent",
        "build AI dashboard"
    )

    show_agent_memory(
        "development-agent"
    )