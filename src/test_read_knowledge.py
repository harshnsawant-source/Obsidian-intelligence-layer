from pathlib import Path

root = Path("knowledge/vault")

for file in root.glob("*.md"):

    print("\n" + "=" * 50)
    print(file.name)
    print("=" * 50)

    with open(

        file,

        "r",

        encoding="utf-8"

    ) as f:

        print(

            f.read()[:1000]

        )