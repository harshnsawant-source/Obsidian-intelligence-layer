from capability.core.search import search_directory

from configs.paths import KNOWLEDGE_VAULT

from core.memory_index import MemoryIndex


class Skill:

    name = "knowledge_search"

    def __init__(self):

        self.index = MemoryIndex()

    def execute(
        self,
        ctx,
        params
    ):

        query = params.get(
            "query",
            ""
        )

        k = params.get("k", 5)

        min_score = params.get("min_score", 0.25)

        try:

            # Semantic search; MemoryIndex itself falls back to keyword
            # matching when embeddings are unavailable.
            matches = self.index.search(
                query,
                k=k,
                min_score=min_score
            )

        except Exception:

            # Last-resort safety net: never crash the menu.
            matches = search_directory(
                KNOWLEDGE_VAULT,
                query
            )

        return {
            "query": query,
            "matches": matches
        }


skill = Skill()


def execute(
    ctx,
    params
):

    return skill.execute(
        ctx,
        params
    )
