from pathlib import Path

from core.memory_index import MemoryIndex


_index = MemoryIndex()


def build_context(task, k=5):

    # Semantic top-k retrieval over the knowledge vault. Each memory is
    # labelled with its similarity score (or marked as a keyword fallback
    # when embeddings are unavailable).

    results = _index.search(task, k=k)

    if not results:

        return ""

    parts = []

    for result in results:

        score = result.get("score")

        if score is None:
            label = "(keyword match)"
        else:
            label = f"(similarity: {score})"

        try:

            text = Path(result["file"]).read_text(
                encoding="utf-8",
                errors="ignore"
            )

        except Exception:

            text = result.get("snippet", "")

        parts.append(
            f"# Memory {label}\n\n{text}"
        )

    return "\n\n".join(parts)
