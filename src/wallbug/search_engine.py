"""Search engine primitives for Wall_Bug."""

from __future__ import annotations

import importlib.util
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Optional, Sequence


if TYPE_CHECKING:
    from wallbug.config import Config


def _load_config_symbols() -> tuple[type[Any], Any]:
    try:
        from wallbug.config import Config as runtime_config_class, load_config as runtime_load_config

        return runtime_config_class, runtime_load_config
    except Exception:
        legacy_module_name = "wallbug._search_engine_legacy_config"
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

_TOKEN_RE = re.compile(r"[A-Za-z0-9']+")


class SearchEngineError(RuntimeError):
    """Raised when search operations cannot be completed."""


@dataclass(frozen=True)
class SearchResult:
    """Represents one matching line found during search."""

    path: Path
    line_number: int
    line: str
    score: int

    def to_dict(self) -> dict[str, str | int]:
        return {
            "path": str(self.path),
            "line_number": self.line_number,
            "line": self.line,
            "score": self.score,
        }


class SearchEngine:
    """Searches Wall_Bug note/transcript content for text queries."""

    def __init__(self, config: Optional[Config] = None) -> None:
        self.config = config or load_config()

    def resolve_search_directories(
        self,
        directories: Optional[Sequence[str | Path]] = None,
    ) -> list[Path]:
        if directories is not None:
            return [Path(directory).expanduser() for directory in directories]

        paths = self.config.paths
        return [
            Path(paths.notes_dir).expanduser(),
            Path(paths.transcripts_dir).expanduser(),
            Path(paths.summaries_dir).expanduser(),
        ]

    def _iter_files(
        self,
        directories: Iterable[Path],
        recursive: bool,
        extensions: Sequence[str],
    ) -> list[Path]:
        normalized_extensions = {ext.lower() for ext in extensions}
        found: dict[str, Path] = {}

        for directory in directories:
            if not directory.exists() or not directory.is_dir():
                continue
            iterator = directory.rglob("*") if recursive else directory.glob("*")
            for path in iterator:
                if not path.is_file():
                    continue
                if path.suffix.lower() not in normalized_extensions:
                    continue
                found[str(path.resolve())] = path

        return sorted(found.values())

    def _tokenize_query(self, query: str) -> list[str]:
        return [token.lower() for token in _TOKEN_RE.findall(query)]

    def search(
        self,
        query: str,
        *,
        directories: Optional[Sequence[str | Path]] = None,
        limit: Optional[int] = 25,
        recursive: bool = True,
        extensions: Sequence[str] = (".md", ".txt"),
        require_all_terms: bool = True,
    ) -> list[SearchResult]:
        if not isinstance(query, str):
            raise SearchEngineError("query must be a string.")
        normalized_query = query.strip()
        if not normalized_query:
            raise SearchEngineError("query cannot be empty.")

        query_tokens = self._tokenize_query(normalized_query)
        if not query_tokens:
            raise SearchEngineError("query must contain at least one searchable token.")

        search_directories = self.resolve_search_directories(directories)
        files = self._iter_files(search_directories, recursive=recursive, extensions=extensions)

        phrase = normalized_query.lower()
        results: list[SearchResult] = []

        for path in files:
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue

            for line_number, line in enumerate(text.splitlines(), start=1):
                stripped = line.strip()
                if not stripped:
                    continue

                lowered = stripped.lower()
                phrase_hit = phrase in lowered
                token_hits = sum(1 for token in query_tokens if token in lowered)

                if require_all_terms:
                    term_match = token_hits == len(query_tokens)
                else:
                    term_match = token_hits > 0

                if not phrase_hit and not term_match:
                    continue

                score = token_hits + (2 if phrase_hit else 0)
                results.append(
                    SearchResult(
                        path=path,
                        line_number=line_number,
                        line=stripped,
                        score=score,
                    )
                )

        results.sort(
            key=lambda item: (
                -item.score,
                str(item.path).lower(),
                item.line_number,
            )
        )

        if limit is None:
            return results
        if limit <= 0:
            return []
        return results[:limit]


def create_search_engine(config: Optional[Config] = None) -> SearchEngine:
    """Factory for SearchEngine instances."""
    return SearchEngine(config=config)


__all__ = [
    "SearchEngineError",
    "SearchResult",
    "SearchEngine",
    "create_search_engine",
]
