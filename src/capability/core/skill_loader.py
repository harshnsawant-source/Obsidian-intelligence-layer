import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Ensure the project root is importable so skills loaded by file path
# (via spec_from_file_location) can still `import configs.paths`.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def load_skill(skill_name):

    skill_file = (
        PROJECT_ROOT /
        "src" /
        "capability" /
        "skills" /
        skill_name /
        "skill.py"
    )

    spec = importlib.util.spec_from_file_location(

        skill_name,

        skill_file

    )

    module = importlib.util.module_from_spec(spec)

    spec.loader.exec_module(module)

    return module