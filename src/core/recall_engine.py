from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

KNOWLEDGE_VAULT = BASE_DIR / "knowledge" / "vault"


def recall_recent_memory(limit=5):

    print("\n=== MEMORY RECALL ===\n")

    if not KNOWLEDGE_VAULT.exists():

        print("Knowledge vault not found.")
        return

    files = sorted(

        KNOWLEDGE_VAULT.glob("*.md"),

        key=lambda x: x.stat().st_mtime,

        reverse=True

    )

    if not files:

        print("No knowledge found.")
        return

    for file in files[:limit]:

        print("\n" + "=" * 50)
        print(file.name)
        print("=" * 50)

        try:

            content = file.read_text(
                encoding="utf-8",
                errors="ignore"
            )

            print(content[:3000])

        except Exception as error:

            print(f"Error reading {file.name}: {error}")

        print("\n")


if __name__ == "__main__":

    recall_recent_memory()