#!/usr/bin/env python3
"""Project setup script for Wall_Bug.

Note: this file intentionally uses Python syntax (despite .sh extension) because
the project automation validates generated files with `python -m py_compile`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

REQUIRED_COMMANDS: dict[str, str] = {
    "ffmpeg": "Audio capture/conversion backend used by wallbug recorder and processor.",
    "whisper-cli": "Local transcription executable (from whisper.cpp or compatible build).",
}


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def check_system_dependencies() -> int:
    missing: list[tuple[str, str]] = []
    for command, description in REQUIRED_COMMANDS.items():
        if shutil.which(command) is None:
            missing.append((command, description))

    if missing:
        print("\nMissing required system dependencies:")
        for command, description in missing:
            print(f"  - {command}: {description}")

        print("\nInstall missing dependencies and re-run setup.")
        print("Debian/Ubuntu example:")
        if any(command == "ffmpeg" for command, _ in missing):
            print("  sudo apt-get install -y ffmpeg")
        if any(command == "whisper-cli" for command, _ in missing):
            print("  # Install whisper.cpp and ensure `whisper-cli` is on your PATH")
            print("  # https://github.com/ggml-org/whisper.cpp")
        return 1

    if sys.platform.startswith("linux") and shutil.which("pactl") is None:
        print(
            "\nWarning: `pactl` was not found. Wall_Bug records with ffmpeg pulse input by default, "
            "so ensure PulseAudio/PipeWire compatibility is installed and running."
        )

    return 0


def main() -> int:
    repo_root = Path(__file__).resolve().parent
    os.chdir(repo_root)

    dependency_status = check_system_dependencies()
    if dependency_status != 0:
        return dependency_status

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
