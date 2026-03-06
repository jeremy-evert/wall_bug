from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import datetime, timedelta

import pytest

from wallbug.metadata import MetadataError, attach_metadata


def test_attach_metadata_computes_stats_and_created_at() -> None:
    transcript = "  Hello world  \nThis is Wall_Bug\n\n"

    result = attach_metadata(transcript)

    assert result["transcript"] == transcript
    assert result["metadata"]["char_count"] == len(transcript)
    assert result["metadata"]["word_count"] == 5
    assert result["metadata"]["line_count"] == 3

    created_at = result["metadata"]["created_at"]
    parsed = datetime.fromisoformat(created_at)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timedelta(0)


def test_attach_metadata_merges_provided_metadata_and_allows_overrides() -> None:
    transcript = "one two"
    provided = {
        "source": "unit-test",
        "char_count": 999,
    }

    result = attach_metadata(transcript, metadata=provided)

    assert result["metadata"]["source"] == "unit-test"
    assert result["metadata"]["char_count"] == 999


def test_attach_metadata_raises_for_non_string_transcript() -> None:
    with pytest.raises(MetadataError):
        attach_metadata(123)  # type: ignore[arg-type]


def test_attach_metadata_raises_for_non_mapping_metadata() -> None:
    with pytest.raises(MetadataError):
        attach_metadata("hello", metadata=["not", "a", "mapping"])  # type: ignore[arg-type]


def test_attach_metadata_raises_for_non_string_metadata_keys() -> None:
    with pytest.raises(MetadataError):
        attach_metadata("hello", metadata={1: "not-allowed"})  # type: ignore[arg-type]


class _ExplodingMapping(Mapping[str, object]):
    def __getitem__(self, key: str) -> object:
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        raise RuntimeError("boom")

    def __len__(self) -> int:
        return 1


def test_attach_metadata_raises_when_mapping_conversion_fails() -> None:
    with pytest.raises(MetadataError):
        attach_metadata("hello", metadata=_ExplodingMapping())


def test_attach_metadata_handles_empty_transcript() -> None:
    result = attach_metadata("")

    assert result["transcript"] == ""
    assert result["metadata"]["char_count"] == 0
    assert result["metadata"]["word_count"] == 0
    assert result["metadata"]["line_count"] == 0
