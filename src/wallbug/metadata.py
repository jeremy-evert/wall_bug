"""Metadata helpers for Wall_Bug transcripts."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


logger = logging.getLogger("wallbug.metadata")


class MetadataError(ValueError):
    """Raised when metadata cannot be generated from invalid input."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _coerce_metadata(metadata: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    if metadata is None:
        logger.debug("No user metadata provided.")
        return {}
    if not isinstance(metadata, Mapping):
        logger.error(
            "Metadata coercion failed: expected mapping or None, got %s.",
            type(metadata).__name__,
        )
        raise MetadataError("metadata must be a mapping or None.")

    try:
        coerced = dict(metadata)
    except Exception as exc:
        logger.error("Metadata coercion failed while converting mapping: %s", exc)
        raise MetadataError("metadata could not be converted to a dictionary.") from exc

    for key in coerced:
        if not isinstance(key, str):
            logger.error(
                "Metadata coercion failed: metadata keys must be strings, got key type %s.",
                type(key).__name__,
            )
            raise MetadataError("metadata keys must be strings.")

    logger.debug("Metadata coercion succeeded with %d override keys.", len(coerced))
    return coerced


def _transcript_stats(transcript: str) -> dict[str, int]:
    stripped = transcript.strip()
    words = stripped.split() if stripped else []
    lines = transcript.splitlines() if transcript else []
    stats = {
        "char_count": len(transcript),
        "word_count": len(words),
        "line_count": len(lines),
    }
    logger.debug(
        "Transcript stats computed (chars=%d, words=%d, lines=%d).",
        stats["char_count"],
        stats["word_count"],
        stats["line_count"],
    )
    return stats


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
    logger.debug("Starting metadata attachment.")
    if not isinstance(transcript, str):
        logger.error(
            "Metadata attachment failed: transcript must be a string, got %s.",
            type(transcript).__name__,
        )
        raise MetadataError("transcript must be a string.")

    computed = TranscriptMetadata(**_transcript_stats(transcript)).to_dict()
    provided = _coerce_metadata(metadata)

    merged_metadata = dict(computed)
    merged_metadata.update(provided)

    logger.info(
        "Metadata attachment complete (computed_keys=%d, override_keys=%d, merged_keys=%d).",
        len(computed),
        len(provided),
        len(merged_metadata),
    )

    return {
        "transcript": transcript,
        "metadata": merged_metadata,
    }


__all__ = [
    "MetadataError",
    "TranscriptMetadata",
    "attach_metadata",
]
