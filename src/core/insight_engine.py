from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent.parent

MEMORY_LOG = BASE_DIR / "memory" / "workflow_memory.md"


def generate_insights():

    print("\n=== OPERATIONAL INSIGHTS ===\n")

    if not MEMORY_LOG.exists():

        print(
            "No workflow memory available."
        )

        return

    content = MEMORY_LOG.read_text(
        encoding="utf-8"
    ).lower()

    retrieval_count = content.count(
        "retrieval"
    )

    creation_count = content.count(
        "creation"
    )

    operations_count = content.count(
        "operations"
    )

    print(
        f"Retrieval workflows: {retrieval_count}"
    )

    print(
        f"Creation workflows: {creation_count}"
    )

    print(
        f"Operational workflows: {operations_count}"
    )

    print("\n=== SYSTEM OBSERVATIONS ===\n")

    if creation_count >= retrieval_count:

        print(
            "- System focus is shifting toward product creation."
        )

    if retrieval_count > 3:

        print(
            "- Retrieval workflows are becoming operationally significant."
        )

    if operations_count > 2:

        print(
            "- Operational orchestration activity is increasing."
        )

    if (
        retrieval_count == 0
        and creation_count == 0
        and operations_count == 0
    ):

        print(
            "- Not enough workflow data collected yet."
        )


if __name__ == "__main__":

    generate_insights()