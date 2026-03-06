"""Daily note summarization for Wall_Bug."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
import re
from typing import Any, Optional

from wallbug.archive import ArchiveManager
from wallbug.config import Config, load_config


class SummarizerError(RuntimeError):
    """Raised when daily summary generation cannot be completed."""


@dataclass(frozen=True)
class NoteDocument:
    """One source document used in daily summary generation."""

    path: Path
    source_type: str
    text: str


_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "for",
    "from",
    "has",
    "have",
    "i",
    "if",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "our",
    "that",
    "the",
    "their",
    "there",
    "this",
    "to",
    "was",
    "we",
    "were",
    "with",
    "you",
    "your",
}


def _safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _iter_category_files(entry_dir: Path, category: str) -> list[Path]:
    target = entry_dir / category
    if not target.exists() or not target.is_dir():
        return []
    return [path for path in sorted(target.iterdir()) if path.is_file()]


def _is_target_day_entry(manager: ArchiveManager, entry_dir: Path, target_date: date) -> bool:
    expected = (
        target_date.strftime("%Y"),
        target_date.strftime("%m"),
        target_date.strftime("%d"),
    )

    try:
        rel = entry_dir.resolve().relative_to(manager.archive_root.resolve())
    except (ValueError, OSError):
        return False

    return len(rel.parts) >= 4 and tuple(rel.parts[:3]) == expected


def _line_candidate(text: str, max_len: int = 160) -> str:
    for line in text.splitlines():
        cleaned = " ".join(line.strip().split())
        if cleaned:
            if len(cleaned) > max_len:
                return cleaned[: max_len - 3].rstrip() + "..."
            return cleaned
    return ""


def _extract_keywords(chunks: list[str], limit: int = 8) -> list[str]:
    counts: Counter[str] = Counter()
    for chunk in chunks:
        for token in re.findall(r"[A-Za-z][A-Za-z'\-]{2,}", chunk.lower()):
            if token in _STOPWORDS:
                continue
            counts[token] += 1
    return [word for word, _ in counts.most_common(limit)]


def _build_narrative(keywords: list[str], words: int, files: int) -> str:
    if not keywords:
        return (
            "The day's notes contain limited repeated language, but they were aggregated "
            "into a single summary for review."
        )
    if len(keywords) == 1:
        topic_text = keywords[0]
    elif len(keywords) == 2:
        topic_text = "{} and {}".format(keywords[0], keywords[1])
    else:
        topic_text = ", ".join(keywords[:-1]) + ", and " + keywords[-1]

    return (
        "Reviewing {} words across {} files, the strongest recurring themes were {}."
    ).format(words, files, topic_text)


def collect_day_documents(
    target_date: date,
    archive_manager: Optional[ArchiveManager] = None,
    include_transcripts: bool = True,
) -> tuple[list[NoteDocument], int]:
    """Collect note-like documents for a single day.

    Returns:
    - list of documents with path/source_type/content
    - number of archive entries processed for the day
    """
    manager = archive_manager or ArchiveManager(config=load_config())
    entries = [
        entry_dir
        for entry_dir in manager.list_entries()
        if _is_target_day_entry(manager, entry_dir, target_date)
    ]

    documents: list[NoteDocument] = []
    for entry_dir in sorted(entries, reverse=True):
        for path in _iter_category_files(entry_dir, "notes"):
            text = _safe_read_text(path)
            if text:
                documents.append(NoteDocument(path=path, source_type="note", text=text))
        if include_transcripts:
            for path in _iter_category_files(entry_dir, "transcripts"):
                text = _safe_read_text(path)
                if text:
                    documents.append(NoteDocument(path=path, source_type="transcript", text=text))

    return documents, len(entries)


def build_daily_summary(
    target_date: date,
    archive_manager: Optional[ArchiveManager] = None,
    include_transcripts: bool = True,
) -> tuple[str, dict[str, int]]:
    """Analyze all day documents and generate a daily summary markdown string."""
    documents, entry_count = collect_day_documents(
        target_date=target_date,
        archive_manager=archive_manager,
        include_transcripts=include_transcripts,
    )

    chunks = [doc.text for doc in documents]
    note_files = sum(1 for doc in documents if doc.source_type == "note")
    transcript_files = sum(1 for doc in documents if doc.source_type == "transcript")
    file_count = len(documents)
    word_count = sum(len(chunk.split()) for chunk in chunks)
    char_count = sum(len(chunk) for chunk in chunks)

    highlight_lines: list[str] = []
    seen: set[str] = set()
    for chunk in chunks:
        if len(highlight_lines) >= 8:
            break
        candidate = _line_candidate(chunk)
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        highlight_lines.append(candidate)

    keywords = _extract_keywords(chunks, limit=8)
    narrative = _build_narrative(keywords=keywords[:5], words=word_count, files=file_count)

    lines: list[str] = [
        "# Daily Summary - {}".format(target_date.isoformat()),
        "",
        "## Snapshot",
        "- Entries processed: {}".format(entry_count),
        "- Files analyzed: {}".format(file_count),
        "- Notes analyzed: {}".format(note_files),
        "- Transcripts analyzed: {}".format(transcript_files),
        "- Total words: {}".format(word_count),
        "- Total characters: {}".format(char_count),
        "",
    ]

    if not documents:
        lines.extend(
            [
                "## Summary",
                "No notes or transcripts were found for this date.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "## Summary",
                narrative,
                "",
                "## Highlights",
            ]
        )
        if highlight_lines:
            for item in highlight_lines:
                lines.append("- {}".format(item))
        else:
            lines.append("- Content exists but no highlight line could be extracted.")
        lines.append("")
        if keywords:
            lines.append("## Keywords")
            lines.append("- " + ", ".join(keywords))
            lines.append("")

    summary_text = "\n".join(lines).rstrip() + "\n"
    stats = {
        "entries": entry_count,
        "files": file_count,
        "note_files": note_files,
        "transcript_files": transcript_files,
        "words": word_count,
        "characters": char_count,
    }
    return summary_text, stats


def write_daily_summary(
    target_date: date,
    summary_text: str,
    config: Optional[Config] = None,
    filename: Optional[str] = None,
) -> Path:
    """Write a generated daily summary into configured summaries directory."""
    cfg = config or load_config()
    summaries_dir = Path(cfg.paths.summaries_dir).expanduser()
    summaries_dir.mkdir(parents=True, exist_ok=True)

    output_name = filename or "{}.md".format(target_date.isoformat())
    output_path = summaries_dir / output_name
    output_path.write_text(summary_text, encoding="utf-8")
    return output_path


def summarize_day(
    target_date: Optional[date] = None,
    archive_manager: Optional[ArchiveManager] = None,
    config: Optional[Config] = None,
    include_transcripts: bool = True,
) -> tuple[Path, dict[str, int]]:
    """Generate and persist a daily summary for one day."""
    day = target_date or datetime.now().date()
    summary_text, stats = build_daily_summary(
        target_date=day,
        archive_manager=archive_manager,
        include_transcripts=include_transcripts,
    )
    path = write_daily_summary(day, summary_text, config=config)
    return path, stats


__all__ = [
    "SummarizerError",
    "NoteDocument",
    "collect_day_documents",
    "build_daily_summary",
    "write_daily_summary",
    "summarize_day",
]
