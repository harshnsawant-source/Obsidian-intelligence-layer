"""Run the verified test suites from the src/ working directory."""
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"

SUITES = [
    "test_semantic_memory.py",
    "test_a2a.py",
    "test_planner.py",
    "test_provider_router.py",
    "test_phase2.py",
    "test_verification.py",
    "test_tools.py",
]


def main():
    failures = 0
    for suite in SUITES:
        print(f"\n{'=' * 60}\n  {suite}\n{'=' * 60}")
        result = subprocess.run([sys.executable, suite], cwd=str(SRC))
        if result.returncode != 0:
            failures += 1
    print(f"\n{'=' * 60}")
    print(f"  SUITES: {len(SUITES) - failures}/{len(SUITES)} passed")
    print(f"{'=' * 60}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
