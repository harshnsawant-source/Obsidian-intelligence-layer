from capability.core.runtime_context import RuntimeContext

from capability.core.skill_registry import discover_skills

from capability.core.skill_loader import load_skill

from capability.skills.meta.skill_activate import activate_skill


ctx = RuntimeContext()


print("\nDISCOVERED SKILLS")

print(

    discover_skills()

)


activation = activate_skill(

    "capability/skills/memory_write"

)

print("\nACTIVATION")

print(

    activation

)


skill = load_skill(

    "memory_write"

)


result = skill.execute(

    ctx,

    {

        "filename": "integration_test.md",

        "content": "Skill execution successful."

    }

)

print("\nEXECUTION")

print(

    result

)