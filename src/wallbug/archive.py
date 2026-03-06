"""Archive management for Wall_Bug."""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Optional


if TYPE_CHECKING:
    from wallbug.config import Config


def _load_config_symbols() -> tuple[type[Any], Any]:
    try:
        from wallbug.config import Config as runtime_config_class, load_config as runtime_load_config

        return runtime_config_class, runtime_load_config
    except Exception:
        legacy_module_name = "wallbug._archive_legacy_config"
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

_ENTRY_ID_RE = re.compile(r"^(?P<y>\d{4})(?P<m>\d{2})(?P<d>\d{2})T\d{12}Z$")


class ArchiveError(RuntimeError):
    """Raised when archive operations cannot be completed."""


class ArchiveManager:
    """Manages archive directory layout and archived assets."""

    def __init__(self, config: Optional[Config] = None) -> None:
        self.config = config or load_config()

    @property
    def archive_root(self) -> Path:
        return self.config.paths.archive_dir.expanduser()

    def ensure_directories(self) -> None:
        paths = self.config.paths
        required = (
            paths.base_dir,
            paths.data_dir,
            paths.audio_dir,
            paths.transcripts_dir,
            paths.notes_dir,
            paths.summaries_dir,
            paths.logs_dir,
            paths.archive_dir,
        )
        for directory in required:
            Path(directory).expanduser().mkdir(parents=True, exist_ok=True)

    def _as_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _entry_datetime_from_id(self, entry_id: str) -> Optional[datetime]:
        if _ENTRY_ID_RE.match(entry_id) is None:
            return None
        try:
            return datetime.strptime(entry_id, "%Y%m%dT%H%M%S%fZ").replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    def build_entry_id(self, created_at: Optional[datetime] = None) -> str:
        ts = self._as_utc(created_at) if created_at is not None else datetime.now(timezone.utc)
        return ts.strftime("%Y%m%dT%H%M%S%fZ")

    def _find_existing_entry_dir(self, entry_id: str) -> Optional[Path]:
        root = self.archive_root
        if not root.exists():
            return None

        candidates = [p for p in root.glob(f"*/*/*/{entry_id}") if p.is_dir()]
        if not candidates:
            return None

        candidates.sort(reverse=True)
        return candidates[0]

    def _entry_date_parts(
        self, entry_id: str, created_at: Optional[datetime] = None
    ) -> tuple[str, str, str]:
        if created_at is not None:
            ts = self._as_utc(created_at)
            return ts.strftime("%Y"), ts.strftime("%m"), ts.strftime("%d")

        match = _ENTRY_ID_RE.match(entry_id)
        if match:
            return match.group("y"), match.group("m"), match.group("d")

        existing = self._find_existing_entry_dir(entry_id)
        if existing is not None:
            day_dir = existing.parent
            month_dir = day_dir.parent
            year_dir = month_dir.parent
            return year_dir.name, month_dir.name, day_dir.name

        ts = datetime.now(timezone.utc)
        return ts.strftime("%Y"), ts.strftime("%m"), ts.strftime("%d")

    def _entry_created_at(self, entry_id: str, created_at: Optional[datetime]) -> datetime:
        if created_at is not None:
            return self._as_utc(created_at)

        from_id = self._entry_datetime_from_id(entry_id)
        if from_id is not None:
            return from_id

        return datetime.now(timezone.utc)

    def get_entry_dir(
        self, entry_id: str, created_at: Optional[datetime] = None
    ) -> Path:
        if created_at is None and _ENTRY_ID_RE.match(entry_id) is None:
            existing = self._find_existing_entry_dir(entry_id)
            if existing is not None:
                return existing

        year, month, day = self._entry_date_parts(entry_id, created_at=created_at)
        return self.archive_root / year / month / day / entry_id

    def create_entry(
        self, entry_id: Optional[str] = None, created_at: Optional[datetime] = None
    ) -> str:
        self.ensure_directories()

        eid = entry_id or self.build_entry_id(created_at)
        entry_dir = self.get_entry_dir(eid, created_at=created_at)

        (entry_dir / "audio").mkdir(parents=True, exist_ok=True)
        (entry_dir / "transcripts").mkdir(parents=True, exist_ok=True)
        (entry_dir / "notes").mkdir(parents=True, exist_ok=True)
        (entry_dir / "summaries").mkdir(parents=True, exist_ok=True)

        metadata_path = entry_dir / "metadata.json"
        if not metadata_path.exists():
            metadata_ts = self._entry_created_at(eid, created_at)
            metadata = {
                "id": eid,
                "created_at": metadata_ts.isoformat(),
                "files": {},
            }
            self._write_json(metadata_path, metadata)

        return eid

    def archive_recording(
        self,
        source: str | Path,
        entry_id: Optional[str] = None,
        created_at: Optional[datetime] = None,
        move: bool = False,
    ) -> Path:
        src = Path(source).expanduser()
        if not src.exists() or not src.is_file():
            raise ArchiveError(f"Recording source not found: {src}")

        eid = self.create_entry(entry_id=entry_id, created_at=created_at)
        entry_dir = self.get_entry_dir(eid, created_at=created_at)
        target = (entry_dir / "audio" / src.name).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)

        if move:
            shutil.move(str(src), str(target))
        else:
            shutil.copy2(src, target)

        self.update_metadata(eid, {"files": {"recording": str(target)}})
        return target

    def archive_transcript(
        self,
        text: str,
        entry_id: Optional[str] = None,
        filename: str = "transcript.txt",
        created_at: Optional[datetime] = None,
    ) -> Path:
        eid = self.create_entry(entry_id=entry_id, created_at=created_at)
        entry_dir = self.get_entry_dir(eid, created_at=created_at)
        target = (entry_dir / "transcripts" / filename).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        self.update_metadata(eid, {"files": {"transcript": str(target)}})
        return target

    def archive_note(
        self,
        text: str,
        entry_id: Optional[str] = None,
        filename: str = "note.txt",
        created_at: Optional[datetime] = None,
    ) -> Path:
        eid = self.create_entry(entry_id=entry_id, created_at=created_at)
        entry_dir = self.get_entry_dir(eid, created_at=created_at)
        target = (entry_dir / "notes" / filename).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        self.update_metadata(eid, {"files": {"note": str(target)}})
        return target

    def archive_summary(
        self,
        text: str,
        entry_id: Optional[str] = None,
        filename: str = "summary.txt",
        created_at: Optional[datetime] = None,
    ) -> Path:
        eid = self.create_entry(entry_id=entry_id, created_at=created_at)
        entry_dir = self.get_entry_dir(eid, created_at=created_at)
        target = (entry_dir / "summaries" / filename).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        self.update_metadata(eid, {"files": {"summary": str(target)}})
        return target

    def metadata_path(
        self, entry_id: str, created_at: Optional[datetime] = None
    ) -> Path:
        return self.get_entry_dir(entry_id, created_at=created_at) / "metadata.json"

    def read_metadata(
        self, entry_id: str, created_at: Optional[datetime] = None
    ) -> dict[str, Any]:
        metadata_file = self.metadata_path(entry_id, created_at=created_at)
        if not metadata_file.exists():
            return {"id": entry_id, "files": {}}

        with metadata_file.open("r", encoding="utf-8") as handle:
            data = json.load(handle)

        if not isinstance(data, dict):
            raise ArchiveError(f"Invalid metadata file: {metadata_file}")
        return dict(data)

    def update_metadata(
        self,
        entry_id: str,
        updates: Mapping[str, Any],
        created_at: Optional[datetime] = None,
    ) -> dict[str, Any]:
        metadata = self.read_metadata(entry_id, created_at=created_at)
        merged = self._merge_dicts(metadata, dict(updates))
        self._write_json(self.metadata_path(entry_id, created_at=created_at), merged)
        return merged

    def list_entries(self) -> list[Path]:
        root = self.archive_root
        if not root.exists():
            return []

        entries: list[Path] = []
        for year_dir in sorted(root.iterdir(), reverse=True):
            if not year_dir.is_dir():
                continue
            for month_dir in sorted(year_dir.iterdir(), reverse=True):
                if not month_dir.is_dir():
                    continue
                for day_dir in sorted(month_dir.iterdir(), reverse=True):
                    if not day_dir.is_dir():
                        continue
                    for entry_dir in sorted(day_dir.iterdir(), reverse=True):
                        if entry_dir.is_dir():
                            entries.append(entry_dir)
        return entries

    def _write_json(self, target: Path, payload: Mapping[str, Any]) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")

    def _merge_dicts(self, base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
        merged = dict(base)
        for key, value in update.items():
            if (
                key in merged
                and isinstance(merged[key], dict)
                and isinstance(value, Mapping)
            ):
                merged[key] = self._merge_dicts(dict(merged[key]), dict(value))
            else:
                merged[key] = value
        return merged


def ensure_archive_structure(config: Optional[Config] = None) -> None:
    ArchiveManager(config=config).ensure_directories()


def create_entry(
    config: Optional[Config] = None,
    entry_id: Optional[str] = None,
    created_at: Optional[datetime] = None,
) -> str:
    manager = ArchiveManager(config=config)
    return manager.create_entry(entry_id=entry_id, created_at=created_at)


def archive_recording(
    source: str | Path,
    config: Optional[Config] = None,
    entry_id: Optional[str] = None,
    created_at: Optional[datetime] = None,
    move: bool = False,
) -> Path:
    manager = ArchiveManager(config=config)
    return manager.archive_recording(
        source=source,
        entry_id=entry_id,
        created_at=created_at,
        move=move,
    )


def archive_transcript(
    text: str,
    config: Optional[Config] = None,
    entry_id: Optional[str] = None,
    filename: str = "transcript.txt",
    created_at: Optional[datetime] = None,
) -> Path:
    manager = ArchiveManager(config=config)
    return manager.archive_transcript(
        text=text,
        entry_id=entry_id,
        filename=filename,
        created_at=created_at,
    )


def archive_note(
    text: str,
    config: Optional[Config] = None,
    entry_id: Optional[str] = None,
    filename: str = "note.txt",
    created_at: Optional[datetime] = None,
) -> Path:
    manager = ArchiveManager(config=config)
    return manager.archive_note(
        text=text,
        entry_id=entry_id,
        filename=filename,
        created_at=created_at,
    )


def archive_summary(
    text: str,
    config: Optional[Config] = None,
    entry_id: Optional[str] = None,
    filename: str = "summary.txt",
    created_at: Optional[datetime] = None,
) -> Path:
    manager = ArchiveManager(config=config)
    return manager.archive_summary(
        text=text,
        entry_id=entry_id,
        filename=filename,
        created_at=created_at,
    )


def read_metadata(
    entry_id: str,
    config: Optional[Config] = None,
    created_at: Optional[datetime] = None,
) -> dict[str, Any]:
    manager = ArchiveManager(config=config)
    return manager.read_metadata(entry_id=entry_id, created_at=created_at)


def update_metadata(
    entry_id: str,
    updates: Mapping[str, Any],
    config: Optional[Config] = None,
    created_at: Optional[datetime] = None,
) -> dict[str, Any]:
    manager = ArchiveManager(config=config)
    return manager.update_metadata(entry_id=entry_id, updates=updates, created_at=created_at)


def list_entries(config: Optional[Config] = None) -> list[Path]:
    manager = ArchiveManager(config=config)
    return manager.list_entries()


__all__ = [
    "ArchiveError",
    "ArchiveManager",
    "ensure_archive_structure",
    "create_entry",
    "archive_recording",
    "archive_transcript",
    "archive_note",
    "archive_summary",
    "read_metadata",
    "update_metadata",
    "list_entries",
]
