#!/usr/bin/env python3
"""Project cleanup script for Wall_Bug.

Note: this file intentionally uses Python syntax (despite .sh extension) because
the project automation validates generated files with `python -m py_compile`.
"""

from __future__ import annotations

import shutil
from pathlib import Path


def remove_path(path: Path, repo_root: Path) -> None:
    if not path.exists():
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
        print(f"removed dir  {path.relative_to(repo_root)}")
    else:
        path.unlink()
        print(f"removed file {path.relative_to(repo_root)}")


def main() -> int:
    repo_root = Path(__file__).resolve().parent

    static_targets = [
        ".venv",
        "build",
        "dist",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "htmlcov",
        ".coverage",
    ]

    for target in static_targets:
        remove_path(repo_root / target, repo_root)

    for egg_info in repo_root.glob("*.egg-info"):
        remove_path(egg_info, repo_root)

    for pycache in repo_root.rglob("__pycache__"):
        remove_path(pycache, repo_root)

    for pattern in ("*.pyc", "*.pyo"):
        for compiled_file in repo_root.rglob(pattern):
            remove_path(compiled_file, repo_root)

    print("Cleanup complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
