from pathlib import Path
import json


PROJECT_ROOT = Path(__file__).resolve().parents[4]


def create_skill(skill_name):

    skill_path = (
        PROJECT_ROOT /
        "src" /
        "capability" /
        "skills" /
        skill_name
    )

    skill_path.mkdir(
        parents=True,
        exist_ok=True
    )

    skill_md = f"""# {skill_name}

version: 0.1.0

type: atomic

description:
Replace this description.

when_to_use:
- Add usage condition

when_not_to_use:
- Add exclusion condition

reads:
- none

writes:
- none

models:
- local

cost_class:
- low

idempotent:
- true

failure_modes:
- invalid_input
"""

    skill_py = f"""def execute(ctx, input_data):

    return {{
        "status": "success",
        "skill": "{skill_name}",
        "input": input_data
    }}
"""

    eval_jsonl = json.dumps(
        {
            "input": "test",
            "expected": "success"
        }
    )

    with open(
        skill_path / "SKILL.md",
        "w",
        encoding="utf-8"
    ) as file:

        file.write(skill_md)

    with open(
        skill_path / "skill.py",
        "w",
        encoding="utf-8"
    ) as file:

        file.write(skill_py)

    with open(
        skill_path / "eval.jsonl",
        "w",
        encoding="utf-8"
    ) as file:

        file.write(eval_jsonl)

    return skill_path


if __name__ == "__main__":

    created = create_skill(

        "memory_write"

    )

    print(created)