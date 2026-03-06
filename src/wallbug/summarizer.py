"""Daily note summarization utilities for Wall_Bug."""

from __future__ import annotations

import importlib.util
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Protocol

from wallbug.logging import get_logger


if TYPE_CHECKING:
    from wallbug.config import Config


def _load_config_symbols() -> tuple[type[Any], Any]:
    try:
        from wallbug.config import Config as runtime_config_class, load_config as runtime_load_config

        return runtime_config_class, runtime_load_config
    except Exception:
        legacy_module_name = "wallbug._summarizer_legacy_config"
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


class SummarizerError(RuntimeError):
    """Raised when summary generation cannot be completed."""


class LLMBackend(Protocol):
    """Protocol for optional LLM backends used by Summarizer."""

    def generate_summary(self, prompt: str) -> str:
        """Return generated summary text from the provided prompt."""


@dataclass(frozen=True)
class SummaryAnalysis:
    """Holds extracted aggregate details from note content."""

    note_count: int
    word_count: int
    highlights: list[str]


class Summarizer:
    """Loads daily notes and generates markdown summaries."""

    def __init__(
        self,
        config: Optional[Config] = None,
        llm_backend: Optional[LLMBackend] = None,
    ) -> None:
        self.config = config or load_config()
        self.llm_backend = llm_backend
        self.logger = get_logger(__name__)

    def parse_target_date(self, value: Optional[str | date | datetime]) -> date:
        if value is None:
            return datetime.now().date()
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value))
        except ValueError as exc:
            raise SummarizerError(
                "Invalid date value {!r}. Expected YYYY-MM-DD.".format(value)
            ) from exc

    def list_note_files(self, target_date: Optional[str | date | datetime] = None) -> list[Path]:
        resolved_date = self.parse_target_date(target_date)
        notes_dir = Path(self.config.paths.notes_dir).expanduser()
        if not notes_dir.exists() or not notes_dir.is_dir():
            self.logger.debug("Notes directory missing: %s", notes_dir)
            return []

        selected: list[Path] = []
        for path in sorted(notes_dir.iterdir(), reverse=True):
            if not path.is_file() or path.suffix.lower() not in {".md", ".txt"}:
                continue
            file_date = self._extract_date_from_filename(path)
            if file_date == resolved_date:
                selected.append(path)

        selected.sort()
        return selected

    def read_notes(self, target_date: Optional[str | date | datetime] = None) -> list[str]:
        notes: list[str] = []
        for note_path in self.list_note_files(target_date=target_date):
            try:
                text = note_path.read_text(encoding="utf-8").strip()
            except OSError as exc:
                self.logger.warning("Unable to read note %s: %s", note_path, exc)
                continue
            if text:
                notes.append(text)
        return notes

    def analyze_notes(self, notes: list[str], highlight_limit: int = 10) -> SummaryAnalysis:
        if highlight_limit <= 0:
            raise SummarizerError("highlight_limit must be greater than zero.")

        word_count = sum(len(note.split()) for note in notes)
        highlights = self._extract_highlights(notes, limit=highlight_limit)
        return SummaryAnalysis(
            note_count=len(notes),
            word_count=word_count,
            highlights=highlights,
        )

    def generate_summary(
        self,
        target_date: Optional[str | date | datetime] = None,
        notes: Optional[list[str]] = None,
    ) -> str:
        resolved_date = self.parse_target_date(target_date)
        note_chunks = list(notes) if notes is not None else self.read_notes(target_date=resolved_date)
        analysis = self.analyze_notes(note_chunks)

        if self.llm_backend is not None and note_chunks:
            llm_summary = self._generate_with_llm(resolved_date, note_chunks)
            if llm_summary:
                return self._render_summary_markdown(
                    target_date=resolved_date,
                    analysis=analysis,
                    narrative=llm_summary,
                )

        return self._render_summary_markdown(
            target_date=resolved_date,
            analysis=analysis,
            narrative=self._fallback_narrative(analysis),
        )

    def save_summary(
        self,
        summary_text: str,
        target_date: Optional[str | date | datetime] = None,
    ) -> Path:
        resolved_date = self.parse_target_date(target_date)
        summaries_dir = Path(self.config.paths.summaries_dir).expanduser()
        summaries_dir.mkdir(parents=True, exist_ok=True)

        output_path = summaries_dir / "{}.md".format(resolved_date.isoformat())
        output_path.write_text(summary_text.rstrip() + "\n", encoding="utf-8")
        return output_path

    def summarize_day(
        self,
        target_date: Optional[str | date | datetime] = None,
    ) -> Path:
        resolved_date = self.parse_target_date(target_date)
        summary_text = self.generate_summary(target_date=resolved_date)
        output_path = self.save_summary(summary_text, target_date=resolved_date)
        self.logger.info("Daily summary generated: %s", output_path)
        return output_path

    def _extract_date_from_filename(self, path: Path) -> Optional[date]:
        match = re.search(r"(\d{4}-\d{2}-\d{2})", path.name)
        if not match:
            return None
        try:
            return date.fromisoformat(match.group(1))
        except ValueError:
            return None

    def _extract_highlights(self, notes: list[str], limit: int) -> list[str]:
        highlights: list[str] = []
        seen: set[str] = set()

        for note in notes:
            if len(highlights) >= limit:
                break
            for raw_line in note.splitlines():
                candidate = raw_line.strip()
                if not candidate:
                    continue
                if candidate.startswith("#"):
                    candidate = candidate.lstrip("#").strip()
                if len(candidate) > 160:
                    candidate = candidate[:157].rstrip() + "..."
                normalized = candidate.casefold()
                if normalized in seen:
                    continue
                seen.add(normalized)
                highlights.append(candidate)
                break

        return highlights

    def _build_llm_prompt(self, target_date: date, notes: list[str]) -> str:
        joined_notes = "\n\n---\n\n".join(notes)
        return (
            "You are summarizing daily engineering notes. "
            "Write concise markdown with sections: Overview, Key Decisions, Risks, Next Steps.\n"
            "Target date: {}\n\n"
            "Notes:\n{}"
        ).format(target_date.isoformat(), joined_notes)

    def _generate_with_llm(self, target_date: date, notes: list[str]) -> str:
        prompt = self._build_llm_prompt(target_date, notes)
        try:
            response = self.llm_backend.generate_summary(prompt)
        except Exception as exc:
            self.logger.warning("LLM summarization failed, using fallback summary: %s", exc)
            return ""

        cleaned = response.strip()
        if not cleaned:
            return ""
        return cleaned

    def _fallback_narrative(self, analysis: SummaryAnalysis) -> str:
        if analysis.note_count == 0:
            return "No notes were found for this date."
        if analysis.word_count == 0:
            return "Notes were found, but they did not contain readable text."
        return "Summarized {} notes containing {} words.".format(
            analysis.note_count,
            analysis.word_count,
        )

    def _render_summary_markdown(
        self,
        target_date: date,
        analysis: SummaryAnalysis,
        narrative: str,
    ) -> str:
        lines: list[str] = [
            "# Daily Summary - {}".format(target_date.isoformat()),
            "",
            "## Overview",
            "- Notes processed: {}".format(analysis.note_count),
            "- Total words analyzed: {}".format(analysis.word_count),
            "",
            "## Summary",
            narrative.strip() or "No summary content available.",
            "",
            "## Highlights",
        ]

        if analysis.highlights:
            for item in analysis.highlights:
                lines.append("- {}".format(item))
        else:
            lines.append("- No highlights available.")

        lines.append("")
        return "\n".join(lines)


def create_summarizer(
    config: Optional[Config] = None,
    llm_backend: Optional[LLMBackend] = None,
) -> Summarizer:
    """Factory for Summarizer instances."""
    return Summarizer(config=config, llm_backend=llm_backend)


__all__ = [
    "SummarizerError",
    "LLMBackend",
    "SummaryAnalysis",
    "Summarizer",
    "create_summarizer",
]
