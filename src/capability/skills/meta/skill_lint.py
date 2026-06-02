from pathlib import Path


REQUIRED_FILES = [

    "SKILL.md",
    "skill.py",
    "eval.jsonl"

]


def lint_skill(skill_path):

    skill_path = Path(skill_path)

    errors = []

    for file_name in REQUIRED_FILES:

        file_path = skill_path / file_name

        if not file_path.exists():

            errors.append(

                f"Missing file: {file_name}"

            )

    eval_file = (

        skill_path /
        "eval.jsonl"

    )

    if eval_file.exists():

        content = (

            eval_file
            .read_text(
                encoding="utf-8"
            )
            .strip()
        )

        if not content:

            errors.append(

                "eval.jsonl is empty"

            )

    if errors:

        return {

            "status": "failed",
            "errors": errors

        }

    return {

        "status": "passed",
        "skill": skill_path.name

    }


if __name__ == "__main__":

    result = lint_skill(

        "../memory_write"

    )

    print(result)