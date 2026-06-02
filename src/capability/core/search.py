from pathlib import Path


def search_directory(root, query):

    matches = []

    root = Path(root)

    if not root.exists():
        return matches

    query_words = [
        word.lower()
        for word in query.split()
        if word.strip()
    ]

    for file in root.rglob("*"):

        if not file.is_file():
            continue

        try:

            text = file.read_text(
                encoding="utf-8",
                errors="ignore"
            )

            text_lower = text.lower()

            score = 0

            for word in query_words:

                if word in text_lower:
                    score += 1

            if score > 0:

                snippet = text[:500]

                matches.append({

                    "file": str(file),

                    "score": score,

                    "snippet": snippet

                })

        except Exception:
            pass

    matches.sort(

        key=lambda x: x["score"],

        reverse=True

    )

    return matches