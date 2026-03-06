from __future__ import annotations

from pathlib import Path

import pytest

from wallbug.config import Config, PathsConfig
from wallbug.directory_manager import (
    DirectoryManager,
    DirectoryManagerError,
    create_directory_manager,
    ensure_configured_directories,
)


def _build_config(root: Path) -> Config:
    return Config(
        paths=PathsConfig(
            base_dir=root / "wallbug",
            data_dir=root / "wallbug" / "data",
            audio_dir=root / "wallbug" / "data" / "audio",
            transcripts_dir=root / "wallbug" / "data" / "transcripts",
            notes_dir=root / "wallbug" / "data" / "notes",
            summaries_dir=root / "wallbug" / "data" / "summaries",
            logs_dir=root / "wallbug" / "data" / "logs",
            archive_dir=root / "wallbug" / "data" / "archive",
        )
    )


def test_directory_map_returns_configured_paths(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    manager = DirectoryManager(config=config)

    directory_map = manager.directory_map()

    assert directory_map == {
        "base_dir": config.paths.base_dir,
        "data_dir": config.paths.data_dir,
        "audio_dir": config.paths.audio_dir,
        "transcripts_dir": config.paths.transcripts_dir,
        "notes_dir": config.paths.notes_dir,
        "summaries_dir": config.paths.summaries_dir,
        "logs_dir": config.paths.logs_dir,
        "archive_dir": config.paths.archive_dir,
    }


@pytest.mark.parametrize(
    ("name", "expected_key"),
    [
        ("base", "base_dir"),
        ("HOME", "base_dir"),
        ("data", "data_dir"),
        ("audio", "audio_dir"),
        ("recordings", "audio_dir"),
        ("transcripts", "transcripts_dir"),
        (" note ", "notes_dir"),
        ("SUMMARY", "summaries_dir"),
        ("logs", "logs_dir"),
        ("archive", "archive_dir"),
    ],
)
def test_get_directory_supports_aliases(name: str, expected_key: str, tmp_path: Path) -> None:
    manager = DirectoryManager(config=_build_config(tmp_path))

    assert manager.get_directory(name) == manager.directory_map()[expected_key]


def test_get_directory_rejects_invalid_names(tmp_path: Path) -> None:
    manager = DirectoryManager(config=_build_config(tmp_path))

    with pytest.raises(DirectoryManagerError, match="name must be a non-empty string"):
        manager.get_directory("")  # type: ignore[arg-type]

    with pytest.raises(DirectoryManagerError, match="name must be a non-empty string"):
        manager.get_directory(None)  # type: ignore[arg-type]

    with pytest.raises(DirectoryManagerError, match="Unknown directory name"):
        manager.get_directory("does-not-exist")


def test_ensure_directory_creates_target(tmp_path: Path) -> None:
    manager = DirectoryManager(config=_build_config(tmp_path))

    audio_dir = manager.ensure_directory("audio")

    assert audio_dir == manager.directory_map()["audio_dir"]
    assert audio_dir.exists()
    assert audio_dir.is_dir()


def test_missing_and_validate_directories(tmp_path: Path) -> None:
    manager = DirectoryManager(config=_build_config(tmp_path))

    assert manager.validate_directories() is False
    assert set(manager.missing_directories()) == set(manager.directory_map().values())

    created = manager.ensure_directories()

    assert set(created) == set(manager.directory_map().values())
    assert manager.missing_directories() == []
    assert manager.validate_directories() is True


def test_create_directory_manager_factory(tmp_path: Path) -> None:
    config = _build_config(tmp_path)

    manager = create_directory_manager(config=config)

    assert isinstance(manager, DirectoryManager)
    assert manager.config is config


def test_ensure_configured_directories_factory(tmp_path: Path) -> None:
    config = _build_config(tmp_path)

    created = ensure_configured_directories(config=config)
    expected = set(DirectoryManager(config=config).directory_map().values())

    assert set(created) == expected
    assert all(path.exists() and path.is_dir() for path in created)


def test_directory_manager_loads_config_when_not_provided(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = _build_config(tmp_path)
    monkeypatch.setattr("wallbug.directory_manager.load_config", lambda: config)

    manager = DirectoryManager()

    assert manager.config is config
