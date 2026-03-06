"""Directory management primitives for Wall_Bug."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional


if TYPE_CHECKING:
    from wallbug.config import Config


def _load_config_symbols() -> tuple[type[Any], Any]:
    try:
        from wallbug.config import Config as runtime_config_class, load_config as runtime_load_config

        return runtime_config_class, runtime_load_config
    except Exception:
        legacy_module_name = "wallbug._directory_manager_legacy_config"
        legacy_module_path = Path(__file__).resolve().with_name("config.py")

        module = sys.modules.get(legacy_module_name)
        if module is None:
            spec = importlib.util.spec_from_file_location(
                legacy_module_name,
                legacy_module_path,
            )
            if spec is None or spec.loader is None:
                raise ImportError(f"Unable to load config module from {legacy_module_path}")

            module = importlib.util.module_from_spec(spec)
            sys.modules[legacy_module_name] = module
            spec.loader.exec_module(module)

        return module.Config, module.load_config


Config, load_config = _load_config_symbols()


class DirectoryManagerError(RuntimeError):
    """Raised when a directory operation cannot be completed."""


class DirectoryManager:
    """Handles configured Wall_Bug directory paths and creation."""

    _NAME_ALIASES = {
        "home": "base_dir",
        "base": "base_dir",
        "base_dir": "base_dir",
        "data": "data_dir",
        "data_dir": "data_dir",
        "audio": "audio_dir",
        "recordings": "audio_dir",
        "audio_dir": "audio_dir",
        "transcript": "transcripts_dir",
        "transcripts": "transcripts_dir",
        "transcripts_dir": "transcripts_dir",
        "note": "notes_dir",
        "notes": "notes_dir",
        "notes_dir": "notes_dir",
        "summary": "summaries_dir",
        "summaries": "summaries_dir",
        "summaries_dir": "summaries_dir",
        "log": "logs_dir",
        "logs": "logs_dir",
        "logs_dir": "logs_dir",
        "archive": "archive_dir",
        "archive_dir": "archive_dir",
    }

    def __init__(self, config: Optional[Config] = None) -> None:
        self.config = config or load_config()

    def directory_map(self) -> dict[str, Path]:
        paths = self.config.paths
        return {
            "base_dir": Path(paths.base_dir).expanduser(),
            "data_dir": Path(paths.data_dir).expanduser(),
            "audio_dir": Path(paths.audio_dir).expanduser(),
            "transcripts_dir": Path(paths.transcripts_dir).expanduser(),
            "notes_dir": Path(paths.notes_dir).expanduser(),
            "summaries_dir": Path(paths.summaries_dir).expanduser(),
            "logs_dir": Path(paths.logs_dir).expanduser(),
            "archive_dir": Path(paths.archive_dir).expanduser(),
        }

    def get_directory(self, name: str) -> Path:
        if not isinstance(name, str) or not name.strip():
            raise DirectoryManagerError("name must be a non-empty string.")

        key = self._NAME_ALIASES.get(name.strip().lower())
        if key is None:
            supported = ", ".join(sorted(self._NAME_ALIASES))
            raise DirectoryManagerError(
                "Unknown directory name '{}'. Supported names: {}".format(name, supported)
            )

        return self.directory_map()[key]

    def ensure_directory(self, name: str) -> Path:
        path = self.get_directory(name)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def ensure_directories(self) -> list[Path]:
        created: list[Path] = []
        for path in self.directory_map().values():
            path.mkdir(parents=True, exist_ok=True)
            created.append(path)
        return created

    def missing_directories(self) -> list[Path]:
        return [path for path in self.directory_map().values() if not path.exists()]

    def validate_directories(self) -> bool:
        return not self.missing_directories()


def create_directory_manager(config: Optional[Config] = None) -> DirectoryManager:
    """Factory for DirectoryManager instances."""
    return DirectoryManager(config=config)


def ensure_configured_directories(config: Optional[Config] = None) -> list[Path]:
    """Ensure all configured directories exist."""
    return DirectoryManager(config=config).ensure_directories()


__all__ = [
    "DirectoryManagerError",
    "DirectoryManager",
    "create_directory_manager",
    "ensure_configured_directories",
]
