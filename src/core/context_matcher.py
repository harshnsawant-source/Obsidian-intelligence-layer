from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent.parent

MEMORY_LOG = BASE_DIR / "memory" / "workflow_memory.md"


def match_context(query):

    print("\n=== CONTEXT MATCHER ===\n")

    if not MEMORY_LOG.exists():

        print(
            "No workflow memory available."
        )

        return

    content = MEMORY_LOG.read_text(
        encoding="utf-8"
    )

    sections = content.split(
        "## Workflow Event"
    )

    query = query.lower()

    matches = []

    for section in sections:

        if query in section.lower():

            matches.append(section.strip())

    if not matches:

        print(
            "No matching operational memory found."
        )

        return

    print(
        f"\nFound {len(matches)} contextual matches.\n"
    )

    for match in matches[-3:]:

        print(
            "\n## MATCHED MEMORY\n"
        )

        print(match)

        print("\n" + "=" * 40)