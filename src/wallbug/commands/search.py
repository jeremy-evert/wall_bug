"""Search command for Wall_Bug CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

from wallbug.config import load_config


class SearchCommandError(RuntimeError):
    """Raised when search command arguments are invalid."""


def _normalize_query(raw_value: object) -> str:
    query = str(raw_value or "").strip()
    if not query:
        raise SearchCommandError("Search query must not be empty.")
    return query


def _iter_roots(args: argparse.Namespace) -> list[Path]:
    config = load_config()
    include_transcripts = bool(getattr(args, "include_transcripts", True))
    roots = [Path(config.paths.notes_dir).expanduser()]
    if include_transcripts:
        roots.append(Path(config.paths.transcripts_dir).expanduser())
    return roots


def _iter_text_files(roots: Iterable[Path]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".md", ".txt"}:
                continue
            files.append(path)
    files.sort()
    return files


def _safe_read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []


def _line_matches(line: str, query: str, case_sensitive: bool) -> bool:
    if case_sensitive:
        return query in line
    return query.casefold() in line.casefold()


def search_command(args: argparse.Namespace) -> int:
    try:
        query = _normalize_query(getattr(args, "query", ""))
    except SearchCommandError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    case_sensitive = bool(getattr(args, "case_sensitive", False))
    limit_raw = getattr(args, "limit", None)
    limit = int(limit_raw) if isinstance(limit_raw, int) and limit_raw > 0 else None

    files = _iter_text_files(_iter_roots(args))
    if not files:
        print("No searchable files were found.")
        return 0

    matches = 0
    for path in files:
        lines = _safe_read_lines(path)
        for line_number, line in enumerate(lines, start=1):
            if not _line_matches(line, query, case_sensitive):
                continue
            print("{}:{}: {}".format(path, line_number, line.strip()))
            matches += 1
            if limit is not None and matches >= limit:
                print("Displayed {} match(es) (limit reached).".format(matches))
                return 0

    if matches == 0:
        print("No matches found for query: {!r}".format(query))
        return 0

    print("Found {} match(es).".format(matches))
    return 0


handle = search_command


__all__ = [
    "SearchCommandError",
    "search_command",
    "handle",
]
