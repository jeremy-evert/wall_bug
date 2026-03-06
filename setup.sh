#!/usr/bin/env python3
"""Project setup script for Wall_Bug.

Note: this file intentionally uses Python syntax (despite .sh extension) because
the project automation validates generated files with `python -m py_compile`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def _config_payload_from_defaults() -> dict[str, object]:
    try:
        from wallbug.config import Config
    except Exception:
        return {
            "debug": False,
            "paths": {
                "base_dir": "~/.wallbug",
                "data_dir": "~/.wallbug/data",
                "audio_dir": "~/.wallbug/data/audio",
                "transcripts_dir": "~/.wallbug/data/transcripts",
                "notes_dir": "~/.wallbug/data/notes",
                "summaries_dir": "~/.wallbug/data/summaries",
                "logs_dir": "~/.wallbug/data/logs",
                "archive_dir": "~/.wallbug/data/archive",
            },
            "recorder": {
                "sample_rate": 16000,
                "channels": 1,
                "chunk_size": 1024,
                "silence_timeout_seconds": 1.25,
                "max_record_seconds": 300,
                "output_format": "wav",
            },
            "transcription": {
                "model": "base",
                "language": "en",
                "device": "cpu",
                "beam_size": 5,
            },
            "llm": {
                "backend": "none",
                "model": "",
                "temperature": 0.2,
                "max_tokens": 512,
            },
            "logging": {
                "level": "INFO",
                "fmt": "%(asctime)s %(levelname)s %(name)s: %(message)s",
            },
            "tools": {
                "ffmpeg_path": "ffmpeg",
                "whisper_cpp_path": "whisper-cli",
            },
        }

    cfg = Config()
    return {
        "debug": cfg.debug,
        "paths": {
            "base_dir": str(cfg.paths.base_dir),
            "data_dir": str(cfg.paths.data_dir),
            "audio_dir": str(cfg.paths.audio_dir),
            "transcripts_dir": str(cfg.paths.transcripts_dir),
            "notes_dir": str(cfg.paths.notes_dir),
            "summaries_dir": str(cfg.paths.summaries_dir),
            "logs_dir": str(cfg.paths.logs_dir),
            "archive_dir": str(cfg.paths.archive_dir),
        },
        "recorder": {
            "sample_rate": cfg.recorder.sample_rate,
            "channels": cfg.recorder.channels,
            "chunk_size": cfg.recorder.chunk_size,
            "silence_timeout_seconds": cfg.recorder.silence_timeout_seconds,
            "max_record_seconds": cfg.recorder.max_record_seconds,
            "output_format": cfg.recorder.output_format,
        },
        "transcription": {
            "model": cfg.transcription.model,
            "language": cfg.transcription.language,
            "device": cfg.transcription.device,
            "beam_size": cfg.transcription.beam_size,
        },
        "llm": {
            "backend": cfg.llm.backend,
            "model": cfg.llm.model,
            "temperature": cfg.llm.temperature,
            "max_tokens": cfg.llm.max_tokens,
        },
        "logging": {
            "level": cfg.logging.level,
            "fmt": cfg.logging.fmt,
        },
        "tools": {
            "ffmpeg_path": cfg.tools.ffmpeg_path,
            "whisper_cpp_path": cfg.tools.whisper_cpp_path,
        },
    }


def _write_if_missing(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        print(f"= keeping existing {path}")
        return
    path.write_text(content, encoding="utf-8")
    print(f"+ created {path}")


def _create_service_config_files() -> None:
    base_dir = Path(os.getenv("WALLBUG_BASE_DIR", str(Path.home() / ".wallbug"))).expanduser()
    config_file = Path(os.getenv("WALLBUG_CONFIG_FILE", str(base_dir / "config.json"))).expanduser()
    env_file = Path(os.getenv("WALLBUG_ENV_FILE", str(base_dir / "wallbug.env"))).expanduser()

    config_payload = _config_payload_from_defaults()
    config_text = json.dumps(config_payload, indent=2) + "\n"
    _write_if_missing(config_file, config_text)

    env_lines = [
        "# Wall_Bug service environment file",
        f"WALLBUG_CONFIG_FILE={config_file}",
        "# Optional overrides:",
        "# WALLBUG_DEBUG=false",
        "# WALLBUG_LOG_LEVEL=INFO",
        "# WALLBUG_TRANSCRIPTION_MODEL=base",
        "# WALLBUG_TRANSCRIPTION_DEVICE=cpu",
        "# WALLBUG_FFMPEG_PATH=ffmpeg",
    ]
    env_text = "\n".join(env_lines) + "\n"
    _write_if_missing(env_file, env_text)

    print("Service config files:")
    print(f"  config: {config_file}")
    print(f"  env:    {env_file}")


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

    _create_service_config_files()

    print("\nSetup complete.")
    if os.name == "nt":
        print(r"Activate with: .venv\Scripts\activate")
    else:
        print("Activate with: source .venv/bin/activate")
    print("Run CLI with: wallbug help")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
