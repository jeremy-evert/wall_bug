"""Directory location constants for Wall_Bug."""

from __future__ import annotations

from pathlib import Path

WALLBUG_HOME_DIR = Path.home() / ".wallbug"
WALLBUG_DATA_DIR = WALLBUG_HOME_DIR / "data"
WALLBUG_AUDIO_DIR = WALLBUG_DATA_DIR / "audio"
WALLBUG_TRANSCRIPTS_DIR = WALLBUG_DATA_DIR / "transcripts"
WALLBUG_NOTES_DIR = WALLBUG_DATA_DIR / "notes"
WALLBUG_SUMMARIES_DIR = WALLBUG_DATA_DIR / "summaries"
WALLBUG_LOGS_DIR = WALLBUG_DATA_DIR / "logs"
WALLBUG_ARCHIVE_DIR = WALLBUG_DATA_DIR / "archive"

__all__ = [
    "WALLBUG_HOME_DIR",
    "WALLBUG_DATA_DIR",
    "WALLBUG_AUDIO_DIR",
    "WALLBUG_TRANSCRIPTS_DIR",
    "WALLBUG_NOTES_DIR",
    "WALLBUG_SUMMARIES_DIR",
    "WALLBUG_LOGS_DIR",
    "WALLBUG_ARCHIVE_DIR",
]
