from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wallbug.search_engine import SearchEngine, SearchEngineError, SearchResult, create_search_engine


def _build_engine(tmp_path: Path) -> tuple[SearchEngine, Path, Path, Path]:
    notes_dir = tmp_path / "notes"
    transcripts_dir = tmp_path / "transcripts"
    summaries_dir = tmp_path / "summaries"
    notes_dir.mkdir()
    transcripts_dir.mkdir()
    summaries_dir.mkdir()

    config = SimpleNamespace(
        paths=SimpleNamespace(
            notes_dir=notes_dir,
            transcripts_dir=transcripts_dir,
            summaries_dir=summaries_dir,
        )
    )
    return SearchEngine(config=config), notes_dir, transcripts_dir, summaries_dir


def test_resolve_search_directories_uses_config_paths(tmp_path: Path) -> None:
    engine, notes_dir, transcripts_dir, summaries_dir = _build_engine(tmp_path)

    resolved = engine.resolve_search_directories()

    assert resolved == [notes_dir, transcripts_dir, summaries_dir]


def test_resolve_search_directories_expands_user(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    engine, _, _, _ = _build_engine(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    resolved = engine.resolve_search_directories(["~/one", "~/two"])

    assert resolved == [home / "one", home / "two"]


def test_search_returns_ranked_results_sorted_deterministically(tmp_path: Path) -> None:
    engine, notes_dir, transcripts_dir, _ = _build_engine(tmp_path)

    (notes_dir / "a.txt").write_text(
        "alpha beta\nalpha and beta\nonly alpha\n",
        encoding="utf-8",
    )
    (transcripts_dir / "b.md").write_text(
        "alpha beta gamma\n",
        encoding="utf-8",
    )

    results = engine.search("alpha beta", limit=None)

    assert [(r.path.name, r.line_number, r.score, r.line) for r in results] == [
        ("a.txt", 1, 4, "alpha beta"),
        ("b.md", 1, 4, "alpha beta gamma"),
        ("a.txt", 2, 2, "alpha and beta"),
    ]


def test_search_require_all_terms_false_includes_partial_matches(tmp_path: Path) -> None:
    engine, notes_dir, _, _ = _build_engine(tmp_path)

    (notes_dir / "notes.txt").write_text(
        "alpha only\nbeta only\nneither\n",
        encoding="utf-8",
    )

    results = engine.search("alpha beta", require_all_terms=False, limit=None)

    assert [r.line for r in results] == ["alpha only", "beta only"]


def test_search_honors_recursive_and_extensions(tmp_path: Path) -> None:
    engine, notes_dir, _, _ = _build_engine(tmp_path)

    (notes_dir / "top.txt").write_text("alpha beta", encoding="utf-8")
    (notes_dir / "skip.log").write_text("alpha beta", encoding="utf-8")
    nested = notes_dir / "nested"
    nested.mkdir()
    (nested / "deep.txt").write_text("alpha beta", encoding="utf-8")

    non_recursive = engine.search("alpha beta", recursive=False, limit=None)
    recursive = engine.search("alpha beta", recursive=True, limit=None)

    assert [r.path.name for r in non_recursive] == ["top.txt"]
    assert sorted(r.path.name for r in recursive) == ["deep.txt", "top.txt"]


def test_search_limit_behaviors(tmp_path: Path) -> None:
    engine, notes_dir, _, _ = _build_engine(tmp_path)

    (notes_dir / "n.txt").write_text("alpha beta\nalpha beta\n", encoding="utf-8")

    all_results = engine.search("alpha beta", limit=None)
    one_result = engine.search("alpha beta", limit=1)
    none_results = engine.search("alpha beta", limit=0)

    assert len(all_results) == 2
    assert len(one_result) == 1
    assert none_results == []


def test_search_skips_files_that_raise_oserror(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    engine, notes_dir, _, _ = _build_engine(tmp_path)

    broken = notes_dir / "broken.txt"
    good = notes_dir / "good.txt"
    broken.write_text("alpha beta", encoding="utf-8")
    good.write_text("alpha beta", encoding="utf-8")

    original_read_text = Path.read_text

    def _patched_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self.name == "broken.txt":
            raise OSError("cannot read")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _patched_read_text)

    results = engine.search("alpha beta", limit=None)

    assert [r.path.name for r in results] == ["good.txt"]


@pytest.mark.parametrize(
    "query,error_message",
    [
        (123, "query must be a string."),
        ("   ", "query cannot be empty."),
        ("!!!", "query must contain at least one searchable token."),
    ],
)
def test_search_rejects_invalid_queries(query: object, error_message: str, tmp_path: Path) -> None:
    engine, _, _, _ = _build_engine(tmp_path)

    with pytest.raises(SearchEngineError, match=error_message):
        engine.search(query)  # type: ignore[arg-type]


def test_search_result_to_dict_and_factory() -> None:
    result = SearchResult(path=Path("x.txt"), line_number=3, line="alpha", score=5)

    assert result.to_dict() == {
        "path": "x.txt",
        "line_number": 3,
        "line": "alpha",
        "score": 5,
    }

    config = SimpleNamespace(
        paths=SimpleNamespace(
            notes_dir=Path("/tmp/notes"),
            transcripts_dir=Path("/tmp/transcripts"),
            summaries_dir=Path("/tmp/summaries"),
        )
    )
    engine = create_search_engine(config=config)
    assert isinstance(engine, SearchEngine)
    assert engine.config is config
