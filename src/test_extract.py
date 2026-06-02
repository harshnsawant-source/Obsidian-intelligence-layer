from capability.skills.knowledge_extract.skill import execute
from capability.core.runtime_context import RuntimeContext

ctx = RuntimeContext()

result = execute(
    ctx,
    {
        "task": "Design a multi-agent support platform",
        "outcome": """
A multi-agent platform should use
specialized agents,
an orchestrator,
and a vector database.
"""
    }
)

print(result)