from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent.parent

CHECK_PATHS = {

    "docs":
    BASE_DIR / "docs",

    "memory":
    BASE_DIR / "memory",

    "logs":
    BASE_DIR / "logs",

    "runtime":
    BASE_DIR / "runtime"
}


def run_diagnostics():

    print("\n=== DIAGNOSTICS ENGINE ===\n")

    for name, path in CHECK_PATHS.items():

        if path.exists():

            print(
                f"[OK] {name}"
            )

        else:

            print(
                f"[MISSING] {name}"
            )


if __name__ == "__main__":

    run_diagnostics()