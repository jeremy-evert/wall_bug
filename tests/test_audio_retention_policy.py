from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from wallbug.audio_retention_policy import AudioRetentionPolicy, AudioRetentionPolicyError


def _set_file_age(path: Path, *, now: datetime, age_days: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"audio")
    ts = (now - timedelta(days=age_days)).timestamp()
    os.utime(path, (ts, ts))


def test_get_audio_files_filters_extensions_and_sorts(tmp_path: Path) -> None:
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir(parents=True)

    (audio_dir / "z.wav").write_bytes(b"1")
    (audio_dir / "a.mp3").write_bytes(b"1")
    (audio_dir / "note.txt").write_text("x", encoding="utf-8")
    (audio_dir / "c.OPUS").write_bytes(b"1")
    (audio_dir / "nested").mkdir()
    (audio_dir / "nested" / "inner.wav").write_bytes(b"1")

    policy = AudioRetentionPolicy(audio_dir=audio_dir)
    files = policy.get_audio_files()

    assert [p.name for p in files] == ["a.mp3", "c.OPUS", "z.wav"]


def test_calculate_file_age_days_uses_now_argument(tmp_path: Path) -> None:
    now = datetime(2026, 1, 10, tzinfo=timezone.utc)
    target = tmp_path / "audio" / "old.wav"
    _set_file_age(target, now=now, age_days=3.0)

    policy = AudioRetentionPolicy(audio_dir=tmp_path / "audio")
    age = policy.calculate_file_age_days(target, now=now)

    assert age == pytest.approx(3.0, rel=1e-6)


def test_is_expired_at_boundary(tmp_path: Path) -> None:
    now = datetime(2026, 1, 10, tzinfo=timezone.utc)
    target = tmp_path / "audio" / "boundary.wav"
    _set_file_age(target, now=now, age_days=30.0)

    policy = AudioRetentionPolicy(audio_dir=tmp_path / "audio", retention_days=30)

    assert policy.is_expired(target, now=now) is True


def test_enforce_deletes_only_expired_files(tmp_path: Path) -> None:
    now = datetime(2026, 1, 10, tzinfo=timezone.utc)
    audio_dir = tmp_path / "audio"

    old_file = audio_dir / "old.wav"
    fresh_file = audio_dir / "fresh.wav"
    _set_file_age(old_file, now=now, age_days=45.0)
    _set_file_age(fresh_file, now=now, age_days=5.0)

    policy = AudioRetentionPolicy(audio_dir=audio_dir, retention_days=30)
    result = policy.enforce(now=now)

    assert old_file.exists() is False
    assert fresh_file.exists() is True
    assert result.retention_days == 30
    assert result.scanned_files == 2
    assert result.expired_files == 1
    assert result.deleted_files == 1
    assert result.dry_run is False


def test_enforce_dry_run_keeps_expired_files(tmp_path: Path) -> None:
    now = datetime(2026, 1, 10, tzinfo=timezone.utc)
    audio_dir = tmp_path / "audio"

    old_file = audio_dir / "old.wav"
    _set_file_age(old_file, now=now, age_days=45.0)

    policy = AudioRetentionPolicy(audio_dir=audio_dir, retention_days=30, dry_run=True)
    result = policy.enforce(now=now)

    assert old_file.exists() is True
    assert result.scanned_files == 1
    assert result.expired_files == 1
    assert result.deleted_files == 0
    assert result.dry_run is True


def test_retention_days_reads_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("WALLBUG_AUDIO_RETENTION_DAYS", "7")

    policy = AudioRetentionPolicy(audio_dir=tmp_path / "audio")

    assert policy.retention_days == 7


def test_invalid_retention_days_from_env_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("WALLBUG_AUDIO_RETENTION_DAYS", "invalid")

    with pytest.raises(AudioRetentionPolicyError):
        AudioRetentionPolicy(audio_dir=tmp_path / "audio")


def test_calculate_file_age_days_missing_file_raises(tmp_path: Path) -> None:
    policy = AudioRetentionPolicy(audio_dir=tmp_path / "audio")
    missing = tmp_path / "audio" / "missing.wav"

    with pytest.raises(AudioRetentionPolicyError):
        policy.calculate_file_age_days(missing)
