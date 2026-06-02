from pathlib import Path

from capability.core.search import search_directory


class Skill:

    name = "trace_search"

    def execute(

        self,
        ctx,
        params

    ):

        query = params.get(

            "query",
            ""

        )

        root = (

            Path(__file__)
            .resolve()
            .parents[4]
            /
            "state"
            /
            "traces"
        )

        matches = search_directory(

            root,
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