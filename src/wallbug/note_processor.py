"""Note processor primitives for Wall_Bug."""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Protocol


if TYPE_CHECKING:
    from wallbug.config import Config


def _load_config_symbols() -> tuple[type[Any], Any]:
    try:
        from wallbug.config import Config as runtime_config_class, load_config as runtime_load_config

        return runtime_config_class, runtime_load_config
    except Exception:
        legacy_module_name = "wallbug._note_processor_legacy_config"
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


class NoteProcessorError(RuntimeError):
    """Raised when note processing cannot be completed."""


class LLMClientLike(Protocol):
    """Protocol for LLM backends used by NoteProcessor."""

    def complete(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Return model output for a prompt."""
        ...


@dataclass(frozen=True)
class StructuredNote:
    """Structured note fields extracted from transcript analysis."""

    title: str = "Session Notes"
    summary: str = ""
    key_points: list[str] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    raw_response: str = ""


class NoteProcessor:
    """Coordinates transcript reading, LLM analysis, and note rendering."""

    def __init__(
        self,
        config: Optional[Config] = None,
        llm_client: Optional[LLMClientLike] = None,
    ) -> None:
        self.config = config or load_config()
        self.llm_client = llm_client

    def read_transcript(self, transcript_path: str | Path) -> str:
        """
        Read transcript text from disk.

        Placeholder structure for WALLBUG-080 implementation.
        """
        path = Path(transcript_path).expanduser()
        if not path.exists() or not path.is_file():
            raise NoteProcessorError("Transcript file not found: {}".format(path))
        return ""

    def build_prompt(self, transcript: str) -> str:
        """Build the prompt sent to the LLM backend."""
        if not isinstance(transcript, str):
            raise NoteProcessorError("transcript must be a string.")
        return (
            "Create structured notes from this transcript.\n\n"
            "Transcript:\n"
            "{}".format(transcript.strip())
        )

    def invoke_llm(self, transcript: str) -> str:
        """
        Invoke configured LLM backend and return raw response text.

        Placeholder structure for WALLBUG-082 implementation.
        """
        if not isinstance(transcript, str):
            raise NoteProcessorError("transcript must be a string.")
        if self.llm_client is None:
            raise NoteProcessorError("llm_client is not configured.")
        return ""

    def parse_llm_response(self, response_text: str) -> StructuredNote:
        """
        Parse LLM response into structured note content.

        Placeholder structure for WALLBUG-083 implementation.
        """
        if not isinstance(response_text, str):
            raise NoteProcessorError("response_text must be a string.")
        return StructuredNote(raw_response=response_text)

    def generate_markdown(self, note: StructuredNote) -> str:
        """
        Render a StructuredNote as markdown text.

        Placeholder structure for WALLBUG-084 implementation.
        """
        if not isinstance(note, StructuredNote):
            raise NoteProcessorError("note must be a StructuredNote instance.")

        lines: list[str] = [
            "# {}".format(note.title.strip() or "Session Notes"),
            "",
            "## Summary",
            note.summary.strip() or "Summary not available.",
            "",
            "## Key Points",
        ]
        if note.key_points:
            lines.extend("- {}".format(item) for item in note.key_points)
        else:
            lines.append("- None")

        lines.extend(["", "## Action Items"])
        if note.action_items:
            lines.extend("- {}".format(item) for item in note.action_items)
        else:
            lines.append("- None")

        lines.extend(["", "## Open Questions"])
        if note.open_questions:
            lines.extend("- {}".format(item) for item in note.open_questions)
        else:
            lines.append("- None")

        lines.append("")
        return "\n".join(lines)

    def build_output_path(
        self,
        transcript_path: str | Path,
        output_path: Optional[str | Path] = None,
    ) -> Path:
        source = Path(transcript_path).expanduser()
        if output_path is None:
            notes_dir = Path(self.config.paths.notes_dir).expanduser()
            return notes_dir / "{}.md".format(source.stem)

        target = Path(output_path).expanduser()
        if target.suffix:
            return target
        return target / "{}.md".format(source.stem)

    def process(
        self,
        transcript_path: str | Path,
        output_path: Optional[str | Path] = None,
    ) -> Path:
        """
        End-to-end note processing pipeline.

        Placeholder structure for WALLBUG-080/WALLBUG-082/WALLBUG-083/WALLBUG-084.
        """
        transcript_text = self.read_transcript(transcript_path)
        llm_response = self.invoke_llm(transcript_text)
        structured = self.parse_llm_response(llm_response)
        markdown = self.generate_markdown(structured)

        target = self.build_output_path(transcript_path, output_path=output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(markdown, encoding="utf-8")
        return target


def create_note_processor(
    config: Optional[Config] = None,
    llm_client: Optional[LLMClientLike] = None,
) -> NoteProcessor:
    """Factory for NoteProcessor instances."""
    return NoteProcessor(config=config, llm_client=llm_client)


__all__ = [
    "NoteProcessorError",
    "LLMClientLike",
    "StructuredNote",
    "NoteProcessor",
    "create_note_processor",
]
