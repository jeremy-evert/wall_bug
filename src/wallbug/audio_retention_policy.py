"""Audio file retention policy helpers for Wall_Bug."""

from __future__ import annotations

import configparser
import importlib.util
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Optional, Sequence


if TYPE_CHECKING:
    from wallbug.config import Config


def _load_config_symbols() -> tuple[type[Any] | None, Any | None]:
    try:
        from wallbug.config import Config as runtime_config_class, load_config as runtime_load_config

        return runtime_config_class, runtime_load_config
    except Exception:
        legacy_module_name = "wallbug._audio_retention_policy_legacy_config"
        legacy_module_path = Path(__file__).resolve().with_name("config.py")
        if not legacy_module_path.exists():
            return None, None

        module = sys.modules.get(legacy_module_name)
        if module is None:
            spec = importlib.util.spec_from_file_location(
                legacy_module_name,
                legacy_module_path,
            )
            if spec is None or spec.loader is None:
                return None, None

            module = importlib.util.module_from_spec(spec)
            sys.modules[legacy_module_name] = module
            spec.loader.exec_module(module)

        return getattr(module, "Config", None), getattr(module, "load_config", None)


Config, load_config = _load_config_symbols()

_DEFAULT_RETENTION_DAYS = 30
_DEFAULT_AUDIO_EXTENSIONS = (".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac", ".opus")
_DEFAULT_AUDIO_DIR = Path.home() / ".wallbug" / "data" / "audio"

_INI_SECTION = "audio_retention_policy"
_INI_RECORDINGS_DIR_KEY = "recordings_dir"
_INI_RETENTION_DAYS_KEY = "retention_days"

_INI_PATH_ENV_VARS = (
    "WALLBUG_AUDIO_RETENTION_CONFIG",
    "WALLBUG_CONFIG_INI",
)


class AudioRetentionPolicyError(RuntimeError):
    """Raised when audio retention policy operations cannot be completed."""


@dataclass(frozen=True)
class RetentionResult:
    """Summarizes one retention execution."""

    retention_days: int
    scanned_files: int
    expired_files: int
    deleted_files: int
    dry_run: bool

    def to_dict(self) -> dict[str, int | bool]:
        return {
            "retention_days": self.retention_days,
            "scanned_files": self.scanned_files,
            "expired_files": self.expired_files,
            "deleted_files": self.deleted_files,
            "dry_run": self.dry_run,
        }


def _coerce_retention_days(value: Any) -> int:
    try:
        days = int(value)
    except (TypeError, ValueError) as exc:
        raise AudioRetentionPolicyError("retention_days must be an integer.") from exc

    if days < 0:
        raise AudioRetentionPolicyError("retention_days cannot be negative.")
    return days


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class AudioRetentionPolicy:
    """Applies a time-based retention policy to audio files."""

    def __init__(
        self,
        config: Optional[Config] = None,
        *,
        retention_days: Optional[int] = None,
        audio_dir: Optional[str | Path] = None,
        dry_run: bool = False,
    ) -> None:
        if config is None and callable(load_config):
            try:
                config = load_config()
            except Exception:
                config = None

        self.config = config
        self._ini_path = self._resolve_ini_path()
        self._ini_config = self._load_ini_config(self._ini_path)

        self.audio_dir = self._resolve_audio_dir(audio_dir)
        self.retention_days = self._resolve_retention_days(retention_days)
        self.dry_run = bool(dry_run)

    def _resolve_ini_path(self) -> Optional[Path]:
        candidates: list[Path] = []

        for env_name in _INI_PATH_ENV_VARS:
            value = os.getenv(env_name)
            if value:
                candidates.append(Path(value).expanduser())

        candidates.append(Path.cwd() / "config.ini")

        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return candidate
        return None

    def _load_ini_config(self, ini_path: Optional[Path]) -> Optional[configparser.ConfigParser]:
        if ini_path is None:
            return None

        parser = configparser.ConfigParser()
        try:
            loaded_files = parser.read(ini_path, encoding="utf-8")
        except (configparser.Error, OSError):
            return None

        if not loaded_files:
            return None
        return parser

    def _resolve_audio_dir(self, audio_dir: Optional[str | Path]) -> Path:
        if audio_dir is not None:
            return Path(audio_dir).expanduser()

        if self.config is not None:
            paths_cfg = getattr(self.config, "paths", None)
            cfg_audio_dir = getattr(paths_cfg, "audio_dir", None)
            if cfg_audio_dir is not None:
                return Path(cfg_audio_dir).expanduser()

        env_audio_dir = os.getenv("WALLBUG_AUDIO_DIR") or os.getenv("AUDIO_DIR")
        if env_audio_dir:
            return Path(env_audio_dir).expanduser()

        if self._ini_config is not None and self._ini_config.has_option(
            _INI_SECTION, _INI_RECORDINGS_DIR_KEY
        ):
            raw_value = self._ini_config.get(_INI_SECTION, _INI_RECORDINGS_DIR_KEY).strip()
            if raw_value:
                parsed = Path(raw_value).expanduser()
                if not parsed.is_absolute() and self._ini_path is not None:
                    parsed = (self._ini_path.parent / parsed).expanduser()
                return parsed

        return _DEFAULT_AUDIO_DIR

    def _resolve_retention_days(self, retention_days: Optional[int]) -> int:
        if retention_days is not None:
            return _coerce_retention_days(retention_days)

        env_value = os.getenv("WALLBUG_AUDIO_RETENTION_DAYS") or os.getenv("AUDIO_RETENTION_DAYS")
        if env_value:
            return _coerce_retention_days(env_value)

        if self.config is not None:
            candidate = getattr(self.config, "audio_retention_days", None)
            if candidate is not None:
                return _coerce_retention_days(candidate)

            policy_cfg = getattr(self.config, "audio_retention_policy", None)
            nested_candidate = getattr(policy_cfg, "retention_days", None)
            if nested_candidate is not None:
                return _coerce_retention_days(nested_candidate)

        if self._ini_config is not None and self._ini_config.has_option(
            _INI_SECTION, _INI_RETENTION_DAYS_KEY
        ):
            ini_value = self._ini_config.get(_INI_SECTION, _INI_RETENTION_DAYS_KEY)
            return _coerce_retention_days(ini_value)

        return _DEFAULT_RETENTION_DAYS

    def get_audio_files(
        self,
        *,
        recursive: bool = False,
        extensions: Sequence[str] = _DEFAULT_AUDIO_EXTENSIONS,
    ) -> list[Path]:
        directory = self.audio_dir.expanduser()
        if not directory.exists() or not directory.is_dir():
            return []

        normalized_extensions = {ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in extensions}
        iterator = directory.rglob("*") if recursive else directory.glob("*")

        files: list[Path] = []
        for path in iterator:
            if path.is_file() and path.suffix.lower() in normalized_extensions:
                files.append(path)

        files.sort(key=lambda item: str(item).lower())
        return files

    def calculate_file_age_days(
        self,
        path: str | Path,
        *,
        now: Optional[datetime] = None,
    ) -> float:
        target = Path(path).expanduser()
        if not target.exists() or not target.is_file():
            raise AudioRetentionPolicyError(f"Audio file not found: {target}")

        ts = datetime.fromtimestamp(target.stat().st_mtime, tz=timezone.utc)
        reference = _as_utc(now) if now is not None else datetime.now(timezone.utc)
        delta = reference - ts
        return delta.total_seconds() / 86400.0

    def is_expired(
        self,
        path: str | Path,
        *,
        now: Optional[datetime] = None,
    ) -> bool:
        return self.calculate_file_age_days(path, now=now) >= float(self.retention_days)

    def get_expired_files(
        self,
        *,
        now: Optional[datetime] = None,
        recursive: bool = False,
        extensions: Sequence[str] = _DEFAULT_AUDIO_EXTENSIONS,
    ) -> list[Path]:
        reference = _as_utc(now) if now is not None else None
        files = self.get_audio_files(recursive=recursive, extensions=extensions)
        return [path for path in files if self.is_expired(path, now=reference)]

    def delete_files(self, files: Iterable[str | Path]) -> list[Path]:
        deleted: list[Path] = []
        for file_path in files:
            target = Path(file_path).expanduser()
            if not target.exists() or not target.is_file():
                continue
            try:
                target.unlink()
            except OSError as exc:
                raise AudioRetentionPolicyError(f"Unable to delete file: {target}") from exc
            deleted.append(target)
        return deleted

    def enforce(
        self,
        *,
        now: Optional[datetime] = None,
        recursive: bool = False,
        extensions: Sequence[str] = _DEFAULT_AUDIO_EXTENSIONS,
        dry_run: Optional[bool] = None,
    ) -> RetentionResult:
        should_dry_run = self.dry_run if dry_run is None else bool(dry_run)
        files = self.get_audio_files(recursive=recursive, extensions=extensions)
        expired = self.get_expired_files(now=now, recursive=recursive, extensions=extensions)

        deleted_count = 0
        if not should_dry_run:
            deleted_count = len(self.delete_files(expired))

        return RetentionResult(
            retention_days=self.retention_days,
            scanned_files=len(files),
            expired_files=len(expired),
            deleted_files=deleted_count,
            dry_run=should_dry_run,
        )


def create_audio_retention_policy(
    config: Optional[Config] = None,
    *,
    retention_days: Optional[int] = None,
    audio_dir: Optional[str | Path] = None,
    dry_run: bool = False,
) -> AudioRetentionPolicy:
    """Factory for AudioRetentionPolicy instances."""
    return AudioRetentionPolicy(
        config=config,
        retention_days=retention_days,
        audio_dir=audio_dir,
        dry_run=dry_run,
    )


def enforce_audio_retention_policy(
    config: Optional[Config] = None,
    *,
    retention_days: Optional[int] = None,
    audio_dir: Optional[str | Path] = None,
    recursive: bool = False,
    dry_run: bool = False,
) -> RetentionResult:
    """Apply the audio retention policy once and return the execution summary."""
    policy = create_audio_retention_policy(
        config=config,
        retention_days=retention_days,
        audio_dir=audio_dir,
        dry_run=dry_run,
    )
    return policy.enforce(recursive=recursive)


__all__ = [
    "AudioRetentionPolicyError",
    "RetentionResult",
    "AudioRetentionPolicy",
    "create_audio_retention_policy",
    "enforce_audio_retention_policy",
]
