from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent.parent

OUTPUT = BASE_DIR / "runtime" / "runtime_prompt.md"


def generate_runtime_prompt():

    print("\n=== RUNTIME ENGINE ===\n")

    prompt = f"""

# Runtime Prompt

Generated:
{datetime.now()}

## Active Objective

Support operational execution
inside Obsidian Intelligence Layer.

## Current Focus

- retrieval
- workflows
- runtime orchestration
- operational continuity

"""

    OUTPUT.write_text(
        prompt,
        encoding="utf-8"
    )

    print(
        "\nRuntime prompt generated."
    )

    print(
        f"\nSaved to: {OUTPUT}"
    )


if __name__ == "__main__":

    generate_runtime_prompt()