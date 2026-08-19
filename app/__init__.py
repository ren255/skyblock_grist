"""SkyBlock flip data access package."""

from pathlib import Path


def find_project_root() -> Path:
    """
    Find repository root by searching upward for:
    - .git
    - requirements.txt
    - pyproject.toml
    """
    current = Path.cwd().resolve()

    for parent in [current] + list(current.parents):
        if (
            (parent / ".git").exists()
            or (parent / "requirements.txt").exists()
            or (parent / "pyproject.toml").exists()
        ):
            return parent

    raise FileNotFoundError("Could not locate project root.")


PROJECT_ROOT = find_project_root()
