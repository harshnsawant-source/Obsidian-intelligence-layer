from capability.core.runtime_context import RuntimeContext
from capability.skills.knowledge_search.skill import execute as knowledge_search
from capability.skills.trace_search.skill import execute as trace_search

ctx = RuntimeContext()

print("\nKNOWLEDGE SEARCH\n")

print(

    knowledge_search(

        ctx,

        {

            "query": "AI"

        }

    )

)

print("\nTRACE SEARCH\n")

print(

    trace_search(

        ctx,

        {

            "query": "platform"

        }

    )

)