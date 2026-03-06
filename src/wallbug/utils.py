"""Shared utility helpers for Wall_Bug."""

from __future__ import annotations

import configparser
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable, Optional


PathLike = str | Path


class UtilsError(RuntimeError):
    """Raised when a utility operation cannot be completed."""


def to_path(value: PathLike) -> Path:
    """Normalize string/path input into an expanded Path."""
    return Path(value).expanduser()


def ensure_directory(path: PathLike) -> Path:
    """Create a directory (and parents) if it does not already exist."""
    directory = to_path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _coerce_target_date(value: Optional[str | date | datetime]) -> date:
    if value is None:
        return datetime.now().date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise UtilsError(
            "Invalid date value {!r}. Expected YYYY-MM-DD.".format(value)
        ) from exc


def ensure_daily_markdown_file(
    output_dir: PathLike,
    target_date: Optional[str | date | datetime] = None,
    title: Optional[str] = None,
) -> Path:
    """Create YYYY-MM-DD.md in output_dir if missing and return its path."""
    resolved_date = _coerce_target_date(target_date)
    directory = ensure_directory(output_dir)
    output_path = directory / "{}.md".format(resolved_date.isoformat())

    if not output_path.exists():
        heading = title or "Daily Summary - {}".format(resolved_date.isoformat())
        output_path.write_text("# {}\n\n".format(heading), encoding="utf-8")

    return output_path


def list_files(
    directory: PathLike,
    extensions: Optional[Iterable[str]] = None,
    recursive: bool = False,
) -> list[Path]:
    """List files in a directory, optionally filtered by extension."""
    root = to_path(directory)
    if not root.exists() or not root.is_dir():
        return []

    normalized_exts: Optional[set[str]] = None
    if extensions is not None:
        normalized_exts = set()
        for ext in extensions:
            value = ext.strip().lower()
            if not value:
                continue
            if not value.startswith("."):
                value = "." + value
            normalized_exts.add(value)

    iterator = root.rglob("*") if recursive else root.iterdir()
    files: list[Path] = []
    for item in iterator:
        if not item.is_file():
            continue
        if normalized_exts is not None and item.suffix.lower() not in normalized_exts:
            continue
        files.append(item)

    files.sort()
    return files


def file_age_days(path: PathLike, now: Optional[datetime] = None) -> float:
    """Return file age in fractional days, based on mtime."""
    target = to_path(path)
    if not target.exists() or not target.is_file():
        raise UtilsError("File not found: {}".format(target))

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)

    modified = datetime.fromtimestamp(target.stat().st_mtime, tz=timezone.utc)
    delta = current - modified
    return max(0.0, delta.total_seconds() / 86400.0)


def filter_files_older_than(
    files: Iterable[PathLike],
    max_age_days: float,
    now: Optional[datetime] = None,
) -> list[Path]:
    """Return only files whose age is >= max_age_days."""
    if max_age_days < 0:
        raise UtilsError("max_age_days must be non-negative.")

    older: list[Path] = []
    for item in files:
        path = to_path(item)
        if not path.exists() or not path.is_file():
            continue
        if file_age_days(path, now=now) >= max_age_days:
            older.append(path)

    older.sort()
    return older


def delete_file(path: PathLike, missing_ok: bool = True) -> bool:
    """Delete a single file and return True if deletion happened."""
    target = to_path(path)
    if not target.exists():
        if missing_ok:
            return False
        raise UtilsError("File not found: {}".format(target))

    if not target.is_file():
        raise UtilsError("Not a file: {}".format(target))

    target.unlink()
    return True


def delete_files(paths: Iterable[PathLike], missing_ok: bool = True) -> list[Path]:
    """Delete multiple files and return the deleted paths."""
    deleted: list[Path] = []
    for item in paths:
        path = to_path(item)
        if delete_file(path, missing_ok=missing_ok):
            deleted.append(path)

    deleted.sort()
    return deleted


def load_ini(path: PathLike) -> configparser.ConfigParser:
    """Load and return an INI config file."""
    config_path = to_path(path)
    if not config_path.exists() or not config_path.is_file():
        raise UtilsError("Config file not found: {}".format(config_path))

    parser = configparser.ConfigParser()
    parser.read(config_path, encoding="utf-8")
    return parser


def read_ini_int(
    parser: configparser.ConfigParser,
    section: str,
    option: str,
    default: Optional[int] = None,
) -> int:
    """Read an integer from an INI parser with optional fallback."""
    if parser.has_option(section, option):
        value = parser.get(section, option)
    elif default is not None:
        return default
    else:
        raise UtilsError(
            "Missing required INI value [{}] {}.".format(section, option)
        )

    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise UtilsError(
            "Invalid integer for [{}] {}: {!r}".format(section, option, value)
        ) from exc


__all__ = [
    "UtilsError",
    "to_path",
    "ensure_directory",
    "ensure_daily_markdown_file",
    "list_files",
    "file_age_days",
    "filter_files_older_than",
    "delete_file",
    "delete_files",
    "load_ini",
    "read_ini_int",
]
