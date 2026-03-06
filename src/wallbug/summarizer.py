"""Daily note summarization for Wall_Bug."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Sequence

from wallbug.config import Config, load_config
from wallbug.logging import get_logger

logger = get_logger("wallbug.summarizer")

_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "with",
    "i",
    "we",
    "you",
    "they",
    "he",
    "she",
    "them",
    "our",
    "your",
    "their",
}


class SummarizerError(RuntimeError):
    """Raised when daily summary generation fails."""


@dataclass(frozen=True)
class SummaryStats:
    note_files: int
    non_empty_notes: int
    extracted_lines: int
    total_words: int

    def to_dict(self) -> dict[str, int]:
        return {
            "note_files": self.note_files,
            "non_empty_notes": self.non_empty_notes,
            "extracted_lines": self.extracted_lines,
            "total_words": self.total_words,
        }


def parse_target_date(raw_value: str | None) -> date:
    if raw_value is None:
        return datetime.now().date()
    try:
        return date.fromisoformat(raw_value)
    except ValueError as exc:
        raise SummarizerError(
            "Invalid date {!r}. Expected format: YYYY-MM-DD.".format(raw_value)
        ) from exc


def _resolve_config(config: Config | None) -> Config:
    return config or load_config()


def _safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        logger.warning("Unable to read note file: %s", path)
        return ""


def _date_file_globs(target_date: date) -> tuple[str, str]:
    return (
        "{}*.md".format(target_date.isoformat()),
        "{}*.md".format(target_date.strftime("%Y%m%d")),
    )


def _iter_note_files_for_day(notes_dir: Path, target_date: date) -> list[Path]:
    if not notes_dir.exists() or not notes_dir.is_dir():
        return []

    candidates: dict[str, Path] = {}

    for pattern in _date_file_globs(target_date):
        for path in sorted(notes_dir.glob(pattern)):
            if path.is_file():
                candidates[str(path.resolve())] = path

    for path in sorted(notes_dir.glob("*.md")):
        if not path.is_file():
            continue
        try:
            modified_date = datetime.fromtimestamp(path.stat().st_mtime).date()
        except OSError:
            continue
        if modified_date == target_date:
            candidates[str(path.resolve())] = path

    return sorted(candidates.values())


def read_daily_notes(
    target_date: date,
    *,
    notes_dir: Path | None = None,
    config: Config | None = None,
) -> list[Path]:
    resolved_config = _resolve_config(config)
    resolved_notes_dir = (notes_dir or resolved_config.paths.notes_dir).expanduser()
    note_files = _iter_note_files_for_day(resolved_notes_dir, target_date)
    logger.info(
        "Found %d note file(s) for %s in %s",
        len(note_files),
        target_date.isoformat(),
        resolved_notes_dir,
    )
    return note_files


def _clean_line(value: str) -> str:
    line = value.strip()
    if not line:
        return ""
    line = re.sub(r"^\s*[-*+]\s+", "", line)
    line = re.sub(r"^\s*#+\s*", "", line)
    line = re.sub(r"\s+", " ", line).strip()
    return line


def extract_relevant_information(note_files: Sequence[Path]) -> list[str]:
    extracted: list[str] = []
    for path in note_files:
        raw = _safe_read_text(path)
        if not raw.strip():
            continue
        for line in raw.splitlines():
            candidate = _clean_line(line)
            if candidate:
                extracted.append(candidate)
    return extracted


def _top_terms(lines: Iterable[str], *, limit: int = 8) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for line in lines:
        for token in re.findall(r"[A-Za-z0-9']+", line.lower()):
            if len(token) < 3:
                continue
            if token in _STOP_WORDS:
                continue
            counter[token] += 1
    return counter.most_common(limit)


def aggregate_note_data(note_files: Sequence[Path], lines: Sequence[str]) -> SummaryStats:
    non_empty_notes = 0
    total_words = 0
    for path in note_files:
        text = _safe_read_text(path).strip()
        if text:
            non_empty_notes += 1
            total_words += len(text.split())

    return SummaryStats(
        note_files=len(note_files),
        non_empty_notes=non_empty_notes,
        extracted_lines=len(lines),
        total_words=total_words,
    )


def generate_summary_markdown(
    target_date: date,
    *,
    note_files: Sequence[Path],
    lines: Sequence[str],
    stats: SummaryStats,
) -> str:
    unique_lines: list[str] = []
    seen: set[str] = set()
    for line in lines:
        if line in seen:
            continue
        seen.add(line)
        unique_lines.append(line)
    highlights = unique_lines[:10]
    top_terms = _top_terms(unique_lines, limit=8)

    content: list[str] = [
        "# Daily Summary - {}".format(target_date.isoformat()),
        "",
        "## Overview",
        "- Note files found: {}".format(stats.note_files),
        "- Non-empty notes: {}".format(stats.non_empty_notes),
        "- Extracted lines: {}".format(stats.extracted_lines),
        "- Total words analyzed: {}".format(stats.total_words),
        "",
    ]

    if not note_files:
        content.extend(
            [
                "## Summary",
                "No note files were found for this day.",
                "",
            ]
        )
        return "\n".join(content).rstrip() + "\n"

    if not highlights:
        content.extend(
            [
                "## Summary",
                "Notes were found, but no readable content could be extracted.",
                "",
            ]
        )
        return "\n".join(content).rstrip() + "\n"

    content.extend(["## Highlights"])
    for line in highlights:
        rendered = line if len(line) <= 180 else line[:177].rstrip() + "..."
        content.append("- {}".format(rendered))
    content.append("")

    if top_terms:
        content.extend(["## Frequent Terms"])
        for term, count in top_terms:
            content.append("- `{}` ({})".format(term, count))
        content.append("")

    return "\n".join(content).rstrip() + "\n"


def save_daily_summary(
    summary_text: str,
    target_date: date,
    *,
    summaries_dir: Path | None = None,
    config: Config | None = None,
) -> Path:
    resolved_config = _resolve_config(config)
    output_dir = (summaries_dir or resolved_config.paths.summaries_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / "{}.md".format(target_date.isoformat())
    output_path.write_text(summary_text, encoding="utf-8")
    logger.info("Saved daily summary to %s", output_path)
    return output_path


def generate_daily_summary(
    target_date: date | None = None,
    *,
    config: Config | None = None,
) -> tuple[Path, SummaryStats]:
    resolved_target = target_date or datetime.now().date()
    note_files = read_daily_notes(resolved_target, config=config)
    lines = extract_relevant_information(note_files)
    stats = aggregate_note_data(note_files, lines)
    summary_text = generate_summary_markdown(
        resolved_target,
        note_files=note_files,
        lines=lines,
        stats=stats,
    )
    output_path = save_daily_summary(summary_text, resolved_target, config=config)
    return output_path, stats


__all__ = [
    "SummarizerError",
    "SummaryStats",
    "parse_target_date",
    "read_daily_notes",
    "extract_relevant_information",
    "aggregate_note_data",
    "generate_summary_markdown",
    "save_daily_summary",
    "generate_daily_summary",
]
