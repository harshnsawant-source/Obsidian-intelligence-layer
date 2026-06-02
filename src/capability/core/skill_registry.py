from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]

SKILLS_PATH = (

    PROJECT_ROOT /
    "src" /
    "capability" /
    "skills"

)


def discover_skills():

    skills = []

    for item in SKILLS_PATH.iterdir():

        if (

            item.is_dir()

            and

            not item.name.startswith("_")

            and

            item.name != "meta"

        ):

            skills.append(

                item.name

            )

    return sorted(skills)


if __name__ == "__main__":

    print(

        discover_skills()

    )