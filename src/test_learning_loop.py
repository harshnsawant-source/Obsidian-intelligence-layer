from capability.core.runtime_context import RuntimeContext

from capability.core.skill_loader import load_skill


ctx = RuntimeContext()


distill = load_skill(

    "knowledge_distill"

)

result = distill.execute(

    ctx,

    {

        "task": "Build Skill Registry",

        "outcome": "Skill Registry working successfully"

    }

)

print(result)


recall = load_skill(

    "memory_recall"

)

print(

    recall.execute(

        ctx,

        {

            "query": "registry"

        }

    )

)