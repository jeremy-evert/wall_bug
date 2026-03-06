"""Metadata helpers for Wall_Bug transcripts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Optional


class MetadataError(ValueError):
    """Raised when metadata cannot be generated from invalid input."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _coerce_metadata(metadata: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    if metadata is None:
        return {}
    if not isinstance(metadata, Mapping):
        raise MetadataError("metadata must be a mapping or None.")
    return dict(metadata)


def _transcript_stats(transcript: str) -> dict[str, int]:
    stripped = transcript.strip()
    words = stripped.split() if stripped else []
    lines = transcript.splitlines() if transcript else []
    return {
        "char_count": len(transcript),
        "word_count": len(words),
        "line_count": len(lines),
    }


@dataclass(frozen=True)
class TranscriptMetadata:
    created_at: str = field(default_factory=_utc_now_iso)
    char_count: int = 0
    word_count: int = 0
    line_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "created_at": self.created_at,
            "char_count": self.char_count,
            "word_count": self.word_count,
            "line_count": self.line_count,
        }


def attach_metadata(
    transcript: str,
    metadata: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """
    Attach computed metadata to transcript content.

    Returns a dictionary with:
    - transcript: original transcript text
    - metadata: merged metadata dictionary
    """
    if not isinstance(transcript, str):
        raise MetadataError("transcript must be a string.")

    computed = TranscriptMetadata(**_transcript_stats(transcript)).to_dict()
    provided = _coerce_metadata(metadata)

    merged_metadata = dict(computed)
    merged_metadata.update(provided)

    return {
        "transcript": transcript,
        "metadata": merged_metadata,
    }


__all__ = [
    "MetadataError",
    "TranscriptMetadata",
    "attach_metadata",
]
