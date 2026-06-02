from capability.skills.meta.skill_activate import activate_skill

skills = [

    "capability/skills/memory_write",
    "capability/skills/memory_recall",
    "capability/skills/knowledge_distill",
    "capability/skills/context_build",
    "capability/skills/workflow_execute"

]

for skill in skills:

    print(

        activate_skill(skill)

    )