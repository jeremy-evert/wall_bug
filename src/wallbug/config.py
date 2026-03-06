"""Configuration for Wall_Bug default settings."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional


ENV_PREFIX = "WALLBUG_"


def _to_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _to_path(value: str) -> Path:
    return Path(value).expanduser()


@dataclass
class PathsConfig:
    base_dir: Path = field(default_factory=lambda: Path.home() / ".wallbug")
    data_dir: Path = field(default_factory=lambda: Path.home() / ".wallbug" / "data")
    audio_dir: Path = field(default_factory=lambda: Path.home() / ".wallbug" / "data" / "audio")
    transcripts_dir: Path = field(default_factory=lambda: Path.home() / ".wallbug" / "data" / "transcripts")
    notes_dir: Path = field(default_factory=lambda: Path.home() / ".wallbug" / "data" / "notes")
    summaries_dir: Path = field(default_factory=lambda: Path.home() / ".wallbug" / "data" / "summaries")
    logs_dir: Path = field(default_factory=lambda: Path.home() / ".wallbug" / "data" / "logs")
    archive_dir: Path = field(default_factory=lambda: Path.home() / ".wallbug" / "data" / "archive")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], base: Optional["PathsConfig"] = None) -> "PathsConfig":
        base = base or cls()
        return cls(
            base_dir=_to_path(str(data.get("base_dir", base.base_dir))),
            data_dir=_to_path(str(data.get("data_dir", base.data_dir))),
            audio_dir=_to_path(str(data.get("audio_dir", base.audio_dir))),
            transcripts_dir=_to_path(str(data.get("transcripts_dir", base.transcripts_dir))),
            notes_dir=_to_path(str(data.get("notes_dir", base.notes_dir))),
            summaries_dir=_to_path(str(data.get("summaries_dir", base.summaries_dir))),
            logs_dir=_to_path(str(data.get("logs_dir", base.logs_dir))),
            archive_dir=_to_path(str(data.get("archive_dir", base.archive_dir))),
        )


@dataclass
class RecorderConfig:
    sample_rate: int = 16000
    channels: int = 1
    chunk_size: int = 1024
    silence_timeout_seconds: float = 1.25
    max_record_seconds: int = 300
    output_format: str = "wav"

    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any], base: Optional["RecorderConfig"] = None
    ) -> "RecorderConfig":
        base = base or cls()
        return cls(
            sample_rate=int(data.get("sample_rate", base.sample_rate)),
            channels=int(data.get("channels", base.channels)),
            chunk_size=int(data.get("chunk_size", base.chunk_size)),
            silence_timeout_seconds=float(
                data.get("silence_timeout_seconds", base.silence_timeout_seconds)
            ),
            max_record_seconds=int(data.get("max_record_seconds", base.max_record_seconds)),
            output_format=str(data.get("output_format", base.output_format)),
        )


@dataclass
class TranscriptionConfig:
    model: str = "base"
    language: str = "en"
    device: str = "cpu"
    beam_size: int = 5

    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any], base: Optional["TranscriptionConfig"] = None
    ) -> "TranscriptionConfig":
        base = base or cls()
        return cls(
            model=str(data.get("model", base.model)),
            language=str(data.get("language", base.language)),
            device=str(data.get("device", base.device)),
            beam_size=int(data.get("beam_size", base.beam_size)),
        )


@dataclass
class LLMConfig:
    backend: str = "none"
    model: str = ""
    temperature: float = 0.2
    max_tokens: int = 512

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], base: Optional["LLMConfig"] = None) -> "LLMConfig":
        base = base or cls()
        return cls(
            backend=str(data.get("backend", base.backend)),
            model=str(data.get("model", base.model)),
            temperature=float(data.get("temperature", base.temperature)),
            max_tokens=int(data.get("max_tokens", base.max_tokens)),
        )


@dataclass
class LoggingConfig:
    level: str = "INFO"
    fmt: str = "%(asctime)s %(levelname)s %(name)s: %(message)s"

    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any], base: Optional["LoggingConfig"] = None
    ) -> "LoggingConfig":
        base = base or cls()
        return cls(
            level=str(data.get("level", base.level)),
            fmt=str(data.get("fmt", base.fmt)),
        )


@dataclass
class ToolsConfig:
    ffmpeg_path: str = "ffmpeg"
    whisper_cpp_path: str = "whisper-cli"

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], base: Optional["ToolsConfig"] = None) -> "ToolsConfig":
        base = base or cls()
        return cls(
            ffmpeg_path=str(data.get("ffmpeg_path", base.ffmpeg_path)),
            whisper_cpp_path=str(data.get("whisper_cpp_path", base.whisper_cpp_path)),
        )


@dataclass
class Config:
    paths: PathsConfig = field(default_factory=PathsConfig)
    recorder: RecorderConfig = field(default_factory=RecorderConfig)
    transcription: TranscriptionConfig = field(default_factory=TranscriptionConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    tools: ToolsConfig = field(default_factory=ToolsConfig)
    debug: bool = False

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], base: Optional["Config"] = None) -> "Config":
        base = base or cls()
        return cls(
            paths=PathsConfig.from_dict(data.get("paths", {}), base.paths),
            recorder=RecorderConfig.from_dict(data.get("recorder", {}), base.recorder),
            transcription=TranscriptionConfig.from_dict(
                data.get("transcription", {}), base.transcription
            ),
            llm=LLMConfig.from_dict(data.get("llm", {}), base.llm),
            logging=LoggingConfig.from_dict(data.get("logging", {}), base.logging),
            tools=ToolsConfig.from_dict(data.get("tools", {}), base.tools),
            debug=bool(data.get("debug", base.debug)),
        )

    @classmethod
    def from_file(cls, path: str | Path, base: Optional["Config"] = None) -> "Config":
        file_path = Path(path).expanduser()
        if not file_path.exists():
            return base or cls()
        with file_path.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
        if not isinstance(loaded, Mapping):
            return base or cls()
        return cls.from_dict(loaded, base=base)

    def with_env_overrides(self) -> "Config":
        data: dict[str, Any] = {
            "debug": self.debug,
            "paths": {
                "base_dir": self.paths.base_dir,
                "data_dir": self.paths.data_dir,
                "audio_dir": self.paths.audio_dir,
                "transcripts_dir": self.paths.transcripts_dir,
                "notes_dir": self.paths.notes_dir,
                "summaries_dir": self.paths.summaries_dir,
                "logs_dir": self.paths.logs_dir,
                "archive_dir": self.paths.archive_dir,
            },
            "recorder": {
                "sample_rate": self.recorder.sample_rate,
                "channels": self.recorder.channels,
                "chunk_size": self.recorder.chunk_size,
                "silence_timeout_seconds": self.recorder.silence_timeout_seconds,
                "max_record_seconds": self.recorder.max_record_seconds,
                "output_format": self.recorder.output_format,
            },
            "transcription": {
                "model": self.transcription.model,
                "language": self.transcription.language,
                "device": self.transcription.device,
                "beam_size": self.transcription.beam_size,
            },
            "llm": {
                "backend": self.llm.backend,
                "model": self.llm.model,
                "temperature": self.llm.temperature,
                "max_tokens": self.llm.max_tokens,
            },
            "logging": {
                "level": self.logging.level,
                "fmt": self.logging.fmt,
            },
            "tools": {
                "ffmpeg_path": self.tools.ffmpeg_path,
                "whisper_cpp_path": self.tools.whisper_cpp_path,
            },
        }

        env_map = {
            "DEBUG": ("debug", _to_bool),
            "BASE_DIR": ("paths.base_dir", _to_path),
            "DATA_DIR": ("paths.data_dir", _to_path),
            "AUDIO_DIR": ("paths.audio_dir", _to_path),
            "TRANSCRIPTS_DIR": ("paths.transcripts_dir", _to_path),
            "NOTES_DIR": ("paths.notes_dir", _to_path),
            "SUMMARIES_DIR": ("paths.summaries_dir", _to_path),
            "LOGS_DIR": ("paths.logs_dir", _to_path),
            "ARCHIVE_DIR": ("paths.archive_dir", _to_path),
            "SAMPLE_RATE": ("recorder.sample_rate", int),
            "CHANNELS": ("recorder.channels", int),
            "CHUNK_SIZE": ("recorder.chunk_size", int),
            "SILENCE_TIMEOUT_SECONDS": ("recorder.silence_timeout_seconds", float),
            "MAX_RECORD_SECONDS": ("recorder.max_record_seconds", int),
            "RECORD_OUTPUT_FORMAT": ("recorder.output_format", str),
            "TRANSCRIBE_MODEL": ("transcription.model", str),
            "TRANSCRIBE_LANGUAGE": ("transcription.language", str),
            "TRANSCRIBE_DEVICE": ("transcription.device", str),
            "TRANSCRIBE_BEAM_SIZE": ("transcription.beam_size", int),
            "LLM_BACKEND": ("llm.backend", str),
            "LLM_MODEL": ("llm.model", str),
            "LLM_TEMPERATURE": ("llm.temperature", float),
            "LLM_MAX_TOKENS": ("llm.max_tokens", int),
            "LOG_LEVEL": ("logging.level", str),
            "LOG_FORMAT": ("logging.fmt", str),
            "FFMPEG_PATH": ("tools.ffmpeg_path", str),
            "WHISPER_CPP_PATH": ("tools.whisper_cpp_path", str),
        }

        for suffix, (path, caster) in env_map.items():
            env_name = f"{ENV_PREFIX}{suffix}"
            raw_value = os.getenv(env_name)
            if raw_value is None:
                continue
            value = caster(raw_value)
            section, key = path.split(".")
            if section == "debug":
                data["debug"] = value
            else:
                data[section][key] = value

        return Config.from_dict(data)


def load_config(config_path: Optional[str | Path] = None) -> Config:
    config = Config()
    if config_path is not None:
        config = Config.from_file(config_path, base=config)
    return config.with_env_overrides()
