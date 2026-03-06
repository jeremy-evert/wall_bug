"""Configuration for Wall_Bug default settings."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional


ENV_PREFIX = "WALLBUG_"

CONFIG_PATH_ENV_VARS: tuple[str, ...] = (
    f"{ENV_PREFIX}CONFIG_FILE",
    f"{ENV_PREFIX}CONFIG_PATH",
    f"{ENV_PREFIX}CONFIG",
)

ENV_FILE_ENV_VARS: tuple[str, ...] = (
    f"{ENV_PREFIX}ENV_FILE",
    f"{ENV_PREFIX}ENV_PATH",
)


def _to_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return _to_bool(value)
    return bool(value)


def _to_path(value: str) -> Path:
    return Path(value).expanduser()


def _set_nested_value(target: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    node: dict[str, Any] = target
    for key in parts[:-1]:
        child = node.get(key)
        if not isinstance(child, dict):
            child = {}
            node[key] = child
        node = child
    node[parts[-1]] = value


def _iter_leaf_paths(node: Any, prefix: str = "") -> list[tuple[str, Any]]:
    if not isinstance(node, dict):
        return [(prefix, node)] if prefix else []
    leaves: list[tuple[str, Any]] = []
    for key, value in node.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            leaves.extend(_iter_leaf_paths(value, path))
        else:
            leaves.append((path, value))
    return leaves


def _caster_for_default(value: Any) -> Any:
    if isinstance(value, bool):
        return _to_bool
    if isinstance(value, int):
        return int
    if isinstance(value, float):
        return float
    if isinstance(value, Path):
        return _to_path
    return str


def _candidate_env_suffixes(path: str) -> list[str]:
    upper_path = path.upper()
    candidates = [
        upper_path.replace(".", "_"),
        upper_path.replace(".", "__"),
    ]

    deduped: list[str] = []
    for candidate in candidates:
        if candidate not in deduped:
            deduped.append(candidate)
    return deduped


def _default_config_candidates() -> list[Path]:
    home = Path.home()
    return [
        home / ".wallbug" / "config.json",
        home / ".config" / "wallbug" / "config.json",
        Path.cwd() / "config.json",
    ]


def _default_env_file_candidates() -> list[Path]:
    home = Path.home()
    return [
        home / ".wallbug" / "wallbug.env",
        home / ".config" / "wallbug" / "wallbug.env",
        Path.cwd() / ".env.wallbug",
    ]


def _normalize_candidate_paths(paths: list[str | Path | None]) -> list[Path]:
    normalized: list[Path] = []
    seen: set[str] = set()
    for candidate in paths:
        if candidate is None:
            continue
        path = Path(candidate).expanduser()
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(path)
    return normalized


def _strip_env_value(raw: str) -> str:
    value = raw.strip()
    if not value:
        return value
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    return value


def _load_env_file(path: Path) -> None:
    if not path.exists() or not path.is_file():
        return

    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("export "):
            stripped = stripped[len("export ") :].lstrip()

        if "=" not in stripped:
            continue

        key, raw_value = stripped.split("=", 1)
        env_key = key.strip()
        if not env_key:
            continue

        os.environ.setdefault(env_key, _strip_env_value(raw_value))


def _load_service_env_overrides() -> None:
    candidates: list[str | Path | None] = [os.getenv(name) for name in ENV_FILE_ENV_VARS]
    candidates.extend(_default_env_file_candidates())
    for path in _normalize_candidate_paths(candidates):
        _load_env_file(path)


def _resolve_config_path(config_path: Optional[str | Path]) -> Optional[Path]:
    if config_path is not None:
        return Path(config_path).expanduser()

    for env_name in CONFIG_PATH_ENV_VARS:
        value = os.getenv(env_name)
        if value:
            return Path(value).expanduser()

    for candidate in _default_config_candidates():
        if candidate.exists():
            return candidate

    return None


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
class RecorderSettings:
    sample_rate: int = 16000
    channels: int = 1
    chunk_size: int = 1024
    silence_timeout_seconds: float = 1.25
    max_record_seconds: int = 300
    output_format: str = "wav"

    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any], base: Optional["RecorderSettings"] = None
    ) -> "RecorderSettings":
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


RecorderConfig = RecorderSettings


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
    recorder: RecorderSettings = field(default_factory=RecorderSettings)
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
            recorder=RecorderSettings.from_dict(data.get("recorder", {}), base.recorder),
            transcription=TranscriptionConfig.from_dict(
                data.get("transcription", {}), base.transcription
            ),
            llm=LLMConfig.from_dict(data.get("llm", {}), base.llm),
            logging=LoggingConfig.from_dict(data.get("logging", {}), base.logging),
            tools=ToolsConfig.from_dict(data.get("tools", {}), base.tools),
            debug=_coerce_bool(data.get("debug", base.debug)),
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

        env_aliases: dict[str, str] = {
            "DEBUG": "debug",
            "BASE_DIR": "paths.base_dir",
            "DATA_DIR": "paths.data_dir",
            "AUDIO_DIR": "paths.audio_dir",
            "TRANSCRIPTS_DIR": "paths.transcripts_dir",
            "NOTES_DIR": "paths.notes_dir",
            "SUMMARIES_DIR": "paths.summaries_dir",
            "LOGS_DIR": "paths.logs_dir",
            "ARCHIVE_DIR": "paths.archive_dir",
            "SAMPLE_RATE": "recorder.sample_rate",
            "CHANNELS": "recorder.channels",
            "CHUNK_SIZE": "recorder.chunk_size",
            "SILENCE_TIMEOUT_SECONDS": "recorder.silence_timeout_seconds",
            "MAX_RECORD_SECONDS": "recorder.max_record_seconds",
            "RECORD_OUTPUT_FORMAT": "recorder.output_format",
            "RECORDER_OUTPUT_FORMAT": "recorder.output_format",
            "TRANSCRIBE_MODEL": "transcription.model",
            "TRANSCRIBE_LANGUAGE": "transcription.language",
            "TRANSCRIBE_DEVICE": "transcription.device",
            "TRANSCRIBE_BEAM_SIZE": "transcription.beam_size",
            "TRANSCRIPTION_MODEL": "transcription.model",
            "TRANSCRIPTION_LANGUAGE": "transcription.language",
            "TRANSCRIPTION_DEVICE": "transcription.device",
            "TRANSCRIPTION_BEAM_SIZE": "transcription.beam_size",
            "LLM_BACKEND": "llm.backend",
            "LLM_MODEL": "llm.model",
            "LLM_TEMPERATURE": "llm.temperature",
            "LLM_MAX_TOKENS": "llm.max_tokens",
            "LOG_LEVEL": "logging.level",
            "LOG_FORMAT": "logging.fmt",
            "FFMPEG_PATH": "tools.ffmpeg_path",
            "WHISPER_CPP_PATH": "tools.whisper_cpp_path",
        }

        casters = {path: _caster_for_default(value) for path, value in _iter_leaf_paths(data)}
        candidate_to_path: dict[str, str] = {}
        for path in casters:
            for suffix in _candidate_env_suffixes(path):
                candidate_to_path.setdefault(suffix, path)

        top_sections = {"paths", "recorder", "transcription", "llm", "logging", "tools"}

        def apply_override(path: str, raw_value: str) -> None:
            caster = casters.get(path)
            if caster is None:
                return
            try:
                coerced = caster(raw_value)
            except (TypeError, ValueError):
                return
            _set_nested_value(data, path, coerced)

        for env_name, raw_value in os.environ.items():
            if not env_name.startswith(ENV_PREFIX):
                continue

            suffix = env_name[len(ENV_PREFIX) :]
            normalized_suffix = suffix.upper()

            if normalized_suffix in env_aliases:
                continue

            path = candidate_to_path.get(normalized_suffix)

            if path is None and "__" in normalized_suffix:
                candidate = normalized_suffix.lower().replace("__", ".")
                if candidate in casters:
                    path = candidate

            if path is None and "_" in normalized_suffix:
                section, remainder = normalized_suffix.split("_", 1)
                section = section.lower()
                if section in top_sections:
                    candidate = f"{section}.{remainder.lower()}"
                    if candidate in casters:
                        path = candidate

            if path is None:
                continue

            apply_override(path, raw_value)

        for suffix, path in env_aliases.items():
            raw_value = os.getenv(f"{ENV_PREFIX}{suffix}")
            if raw_value is None:
                continue
            apply_override(path, raw_value)

        return Config.from_dict(data)


Configuration = Config


def load_config(config_path: Optional[str | Path] = None) -> Config:
    _load_service_env_overrides()

    config = Config()
    resolved_config_path = _resolve_config_path(config_path)
    if resolved_config_path is not None:
        config = Config.from_file(resolved_config_path, base=config)
    return config.with_env_overrides()
