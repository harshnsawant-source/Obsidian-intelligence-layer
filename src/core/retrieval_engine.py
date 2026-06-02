from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent.parent

SEARCH_PATHS = [

    BASE_DIR / "docs",

    BASE_DIR / "memory",

    BASE_DIR / "logs"
]


def run_retrieval_scan():

    print("\n=== RETRIEVAL ENGINE ===\n")

    for path in SEARCH_PATHS:

        if path.exists():

            markdown_files = list(
                path.glob("*.md")
            )

            print(
                f"[OK] {path.name} :: {len(markdown_files)} markdown files"
            )

        else:

            print(
                f"[MISSING] {path.name}"
            )


if __name__ == "__main__":

    run_retrieval_scan()