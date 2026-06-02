from capability.skills.knowledge_search.skill import execute
from capability.core.runtime_context import RuntimeContext

ctx = RuntimeContext()

result = execute(

    ctx,

    {

        "query": "agents"

    }

)

print(result)