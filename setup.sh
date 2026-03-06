#!/usr/bin/env python3
"""Project setup script for Wall_Bug.

Note: this file intentionally uses Python syntax (despite .sh extension) because
the project automation validates generated files with `python -m py_compile`.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> int:
    repo_root = Path(__file__).resolve().parent
    os.chdir(repo_root)

    venv_dir = repo_root / ".venv"
    if not venv_dir.exists():
        run([sys.executable, "-m", "venv", str(venv_dir)])

    python_bin = venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    python = str(python_bin)

    run([python, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"])
    run([python, "-m", "pip", "install", "-e", "."])

    contract_script = repo_root / "scripts" / "enforce_filesystem_contract.py"
    if contract_script.exists():
        run([python, str(contract_script)])

    print("\nSetup complete.")
    if os.name == "nt":
        print(r"Activate with: .venv\Scripts\activate")
    else:
        print("Activate with: source .venv/bin/activate")
    print("Run CLI with: wallbug help")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
