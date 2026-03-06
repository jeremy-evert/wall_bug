"""Daily summary command for Wall_Bug."""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

from wallbug.archive import ArchiveManager
from wallbug.config import load_config


class SummarizeDayError(RuntimeError):
    """Raised when summarize-day command input is invalid."""


def parse_target_date(raw_value: str | None) -> date:
    if raw_value is None:
        return datetime.now().date()

    try:
        return date.fromisoformat(raw_value)
    except ValueError as exc:
        raise SummarizeDayError(
            "Invalid --date value {!r}. Expected format: YYYY-MM-DD.".format(raw_value)
        ) from exc


def _safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _iter_day_entries(manager: ArchiveManager, target_date: date) -> list[Path]:
    expected = (target_date.strftime("%Y"), target_date.strftime("%m"), target_date.strftime("%d"))
    root = manager.archive_root.expanduser()

    selected: list[Path] = []
    for entry_dir in manager.list_entries():
        try:
            rel = entry_dir.resolve().relative_to(root.resolve())
        except ValueError:
            continue
        if len(rel.parts) >= 4 and tuple(rel.parts[:3]) == expected:
            selected.append(entry_dir)

    selected.sort(reverse=True)
    return selected


def _iter_content_files(entry_dir: Path) -> Iterable[Path]:
    for subdir in ("notes", "transcripts"):
        target_dir = entry_dir / subdir
        if not target_dir.exists() or not target_dir.is_dir():
            continue
        for path in sorted(target_dir.iterdir()):
            if path.is_file():
                yield path


def _extract_highlights(chunks: Iterable[str], limit: int = 8) -> list[str]:
    highlights: list[str] = []
    seen: set[str] = set()

    for chunk in chunks:
        if len(highlights) >= limit:
            break
        for line in chunk.splitlines():
            candidate = line.strip()
            if not candidate:
                continue
            if len(candidate) > 140:
                candidate = candidate[:137].rstrip() + "..."
            if candidate in seen:
                continue
            seen.add(candidate)
            highlights.append(candidate)
            break

    return highlights


def build_daily_summary(
    target_date: date,
    archive_manager: ArchiveManager | None = None,
) -> tuple[str, dict[str, int]]:
    manager = archive_manager or ArchiveManager(config=load_config())
    entries = _iter_day_entries(manager, target_date)

    file_count = 0
    chunks: list[str] = []

    for entry_dir in entries:
        for content_file in _iter_content_files(entry_dir):
            file_count += 1
            text = _safe_read_text(content_file)
            if text:
                chunks.append(text)

    word_count = sum(len(chunk.split()) for chunk in chunks)
    highlights = _extract_highlights(chunks)

    lines: list[str] = [
        "# Daily Summary - {}".format(target_date.isoformat()),
        "",
        "## Overview",
        "- Entries processed: {}".format(len(entries)),
        "- Files processed: {}".format(file_count),
        "- Total words analyzed: {}".format(word_count),
        "",
    ]

    if not chunks:
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
                "Collected content from archived notes and transcripts for this date.",
                "",
                "## Highlights",
            ]
        )
        if highlights:
            for item in highlights:
                lines.append("- {}".format(item))
        else:
            lines.append("- Content exists but no non-empty lines were found.")
        lines.append("")

    summary_text = "\n".join(lines).rstrip() + "\n"
    stats = {
        "entries": len(entries),
        "files": file_count,
        "words": word_count,
    }
    return summary_text, stats


def _write_summary(target_date: date, summary_text: str) -> Path:
    config = load_config()
    summaries_dir = Path(config.paths.summaries_dir).expanduser()
    summaries_dir.mkdir(parents=True, exist_ok=True)

    output_path = summaries_dir / "{}.md".format(target_date.isoformat())
    output_path.write_text(summary_text, encoding="utf-8")
    return output_path


def summarize_day_command(args: argparse.Namespace) -> int:
    try:
        target_date = parse_target_date(getattr(args, "date", None))
    except SummarizeDayError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    summary_text, stats = build_daily_summary(target_date)
    output_path = _write_summary(target_date, summary_text)

    print("Daily summary saved to: {}".format(output_path))
    print(
        "Entries: {entries}, Files: {files}, Words: {words}".format(
            entries=stats["entries"],
            files=stats["files"],
            words=stats["words"],
        )
    )
    return 0


handle = summarize_day_command


__all__ = [
    "SummarizeDayError",
    "parse_target_date",
    "build_daily_summary",
    "summarize_day_command",
    "handle",
]
