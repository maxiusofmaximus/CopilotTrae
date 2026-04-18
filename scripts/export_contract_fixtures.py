from pathlib import Path


FIXTURE_ROOT = Path("tests/contracts")


def ensure_fixture_layout() -> None:
    for relative_path in ("router", "terminal", "runtime"):
        (FIXTURE_ROOT / relative_path).mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    ensure_fixture_layout()
