"""Note processing and storage utilities for Wall_Bug."""

from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Optional

from wallbug.archive import ArchiveError, ArchiveManager
from wallbug.logging import get_logger


if TYPE_CHECKING:
    from wallbug.config import Config


def _load_config_symbols() -> tuple[type[Any], Any]:
    try:
        from wallbug.config import Config as runtime_config_class, load_config as runtime_load_config

        return runtime_config_class, runtime_load_config
    except Exception:
        legacy_module_name = "wallbug._note_processing_legacy_config"
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


class NoteProcessingError(RuntimeError):
    """Raised when note processing or storage cannot be completed."""


@dataclass(frozen=True)
class NoteStorageResult:
    """File paths produced by note processing and storage."""

    note_path: Path
    metadata_path: Path
    archive_note_path: Optional[Path] = None
    entry_id: Optional[str] = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _coerce_mapping(value: Optional[Mapping[str, Any]], field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise NoteProcessingError("{} must be a mapping or None.".format(field_name))
    return dict(value)


class NoteProcessing:
    """Processes and stores note text with optional additional information."""

    def __init__(
        self,
        config: Optional[Config] = None,
        archive_manager: Optional[ArchiveManager] = None,
    ) -> None:
        self.config = config or load_config()
        self.archive_manager = archive_manager or ArchiveManager(config=self.config)
        self.logger = get_logger(__name__)

    def normalize_note_text(self, note_text: str) -> str:
        if not isinstance(note_text, str):
            raise NoteProcessingError("note_text must be a string.")
        normalized = note_text.strip()
        if not normalized:
            raise NoteProcessingError("note_text cannot be empty.")
        return normalized

    def build_note_payload(
        self,
        note_text: str,
        *,
        additional_info: Optional[Mapping[str, Any]] = None,
        source: Optional[str] = None,
        transcript_path: Optional[str | Path] = None,
        entry_id: Optional[str] = None,
    ) -> dict[str, Any]:
        normalized_note = self.normalize_note_text(note_text)
        resolved_additional = _coerce_mapping(additional_info, "additional_info")

        metadata: dict[str, Any] = {
            "created_at": _utc_now_iso(),
            "char_count": len(normalized_note),
            "word_count": len(normalized_note.split()),
            "line_count": len(normalized_note.splitlines()),
            "entry_id": entry_id,
        }

        if source:
            metadata["source"] = str(source)
        if transcript_path is not None:
            metadata["transcript_path"] = str(Path(transcript_path).expanduser())

        return {
            "note": normalized_note,
            "metadata": metadata,
            "additional_info": resolved_additional,
        }

    def build_output_path(
        self,
        *,
        transcript_path: Optional[str | Path] = None,
        output_path: Optional[str | Path] = None,
        created_at: Optional[datetime] = None,
    ) -> Path:
        if output_path is not None:
            target = Path(output_path).expanduser()
            if target.suffix:
                return target
            if transcript_path is not None:
                stem = Path(transcript_path).expanduser().stem
                return target / "{}.md".format(stem)
            stamp = (created_at or datetime.now(timezone.utc)).strftime("%Y%m%d-%H%M%S")
            return target / "note-{}.md".format(stamp)

        notes_dir = Path(self.config.paths.notes_dir).expanduser()
        if transcript_path is not None:
            return notes_dir / "{}.md".format(Path(transcript_path).expanduser().stem)

        stamp = (created_at or datetime.now(timezone.utc)).strftime("%Y%m%d-%H%M%S")
        return notes_dir / "note-{}.md".format(stamp)

    def metadata_path_for_note(self, note_path: str | Path) -> Path:
        return Path(note_path).expanduser().with_suffix(".metadata.json")

    def process_and_store(
        self,
        note_text: str,
        *,
        transcript_path: Optional[str | Path] = None,
        output_path: Optional[str | Path] = None,
        additional_info: Optional[Mapping[str, Any]] = None,
        metadata_overrides: Optional[Mapping[str, Any]] = None,
        source: str = "note_processing",
        entry_id: Optional[str] = None,
        created_at: Optional[datetime] = None,
        archive: bool = True,
    ) -> NoteStorageResult:
        payload = self.build_note_payload(
            note_text,
            additional_info=additional_info,
            source=source,
            transcript_path=transcript_path,
            entry_id=entry_id,
        )
        payload["metadata"].update(_coerce_mapping(metadata_overrides, "metadata_overrides"))

        note_path = self.build_output_path(
            transcript_path=transcript_path,
            output_path=output_path,
            created_at=created_at,
        )
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text(payload["note"].rstrip() + "\n", encoding="utf-8")

        metadata_path = self.metadata_path_for_note(note_path)
        metadata_path.write_text(
            json.dumps(
                {
                    "note_path": str(note_path.resolve()),
                    "metadata": payload["metadata"],
                    "additional_info": payload["additional_info"],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        archive_note_path: Optional[Path] = None
        resolved_entry_id = entry_id

        if archive:
            if resolved_entry_id is None and transcript_path is not None:
                resolved_entry_id = self.archive_manager.entry_id_from_path(transcript_path)
            if resolved_entry_id is None:
                resolved_entry_id = self.archive_manager.entry_id_from_path(note_path)

            try:
                archive_note_path = self.archive_manager.archive_note(
                    text=payload["note"],
                    entry_id=resolved_entry_id,
                    filename=note_path.name,
                    created_at=created_at,
                )
            except (ArchiveError, OSError, UnicodeError) as exc:
                raise NoteProcessingError("Unable to archive note: {}".format(exc)) from exc

            archived_entry_id = self.archive_manager.entry_id_from_path(archive_note_path)
            if archived_entry_id is not None:
                resolved_entry_id = archived_entry_id
                self.archive_manager.update_metadata(
                    archived_entry_id,
                    {
                        "note_processing": {
                            "note_metadata": payload["metadata"],
                            "additional_info": payload["additional_info"],
                            "note_metadata_path": str(metadata_path.resolve()),
                        }
                    },
                    created_at=created_at,
                )

        self.logger.info(
            "Stored note artifact: note=%s metadata=%s archive=%s",
            note_path,
            metadata_path,
            archive_note_path,
        )

        return NoteStorageResult(
            note_path=note_path,
            metadata_path=metadata_path,
            archive_note_path=archive_note_path,
            entry_id=resolved_entry_id,
        )


def create_note_processing(
    config: Optional[Config] = None,
    archive_manager: Optional[ArchiveManager] = None,
) -> NoteProcessing:
    """Factory for NoteProcessing instances."""
    return NoteProcessing(config=config, archive_manager=archive_manager)


def process_note(
    note_text: str,
    *,
    config: Optional[Config] = None,
    transcript_path: Optional[str | Path] = None,
    output_path: Optional[str | Path] = None,
    additional_info: Optional[Mapping[str, Any]] = None,
    metadata_overrides: Optional[Mapping[str, Any]] = None,
    source: str = "note_processing",
    entry_id: Optional[str] = None,
    created_at: Optional[datetime] = None,
    archive: bool = True,
) -> NoteStorageResult:
    """Convenience helper to process and store a note."""
    return NoteProcessing(config=config).process_and_store(
        note_text,
        transcript_path=transcript_path,
        output_path=output_path,
        additional_info=additional_info,
        metadata_overrides=metadata_overrides,
        source=source,
        entry_id=entry_id,
        created_at=created_at,
        archive=archive,
    )


__all__ = [
    "NoteProcessingError",
    "NoteStorageResult",
    "NoteProcessing",
    "create_note_processing",
    "process_note",
]
