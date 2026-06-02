from pathlib import Path

from capability.skills.meta.skill_lint import lint_skill


def activate_skill(skill_path):

    result = lint_skill(skill_path)

    if result["status"] != "passed":

        return {

            "status": "failed",

            "reason": result

        }

    active_file = (

        Path(skill_path) /
        ".active"

    )

    active_file.write_text(

        "ACTIVE",

        encoding="utf-8"

    )

    return {

        "status": "active"

    }