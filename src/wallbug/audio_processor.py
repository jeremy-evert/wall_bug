"""Audio processor primitives for Wall_Bug."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Protocol


if TYPE_CHECKING:
    from wallbug.config import Config


def _load_config_symbols() -> tuple[type[Any], Any]:
    try:
        from wallbug.config import Config as runtime_config_class, load_config as runtime_load_config

        return runtime_config_class, runtime_load_config
    except Exception:
        legacy_module_name = "wallbug._audio_processor_legacy_config"
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


class AudioProcessorError(RuntimeError):
    """Raised when audio processing cannot be completed."""


class VADLike(Protocol):
    """Protocol for a VAD engine used by AudioProcessor."""

    def is_speech(self, frame: bytes, sample_rate: int) -> bool:
        """Return True when the frame contains speech."""
        ...


@dataclass(frozen=True)
class AudioSegment:
    """Represents a speech segment extracted from an audio stream."""

    audio: bytes
    sample_rate: int
    channels: int
    start_ms: int
    end_ms: int


class AudioProcessor:
    """Stateful audio processor that groups audio frames into speech segments."""

    def __init__(
        self,
        config: Optional[Config] = None,
        vad_engine: Optional[VADLike] = None,
        sample_rate: Optional[int] = None,
        channels: Optional[int] = None,
        frame_ms: int = 30,
    ) -> None:
        self.config = config or load_config()
        self.vad_engine = vad_engine
        self.sample_rate = int(
            self.config.recorder.sample_rate if sample_rate is None else sample_rate
        )
        self.channels = int(self.config.recorder.channels if channels is None else channels)
        self.frame_ms = int(frame_ms)

        self._buffer = bytearray()
        self._current_start_ms = 0
        self._consumed_ms = 0

    def add_chunk(self, chunk: bytes) -> list[AudioSegment]:
        """
        Add raw PCM bytes to the processor.

        Placeholder structure for WALLBUG-050 implementation.
        """
        if not isinstance(chunk, (bytes, bytearray)):
            raise AudioProcessorError("chunk must be bytes-like.")
        if not chunk:
            return []

        self._buffer.extend(chunk)
        return []

    def process_buffer(self, audio: bytes) -> list[AudioSegment]:
        """
        Process a full in-memory buffer and return detected speech segments.

        Placeholder structure for WALLBUG-050 implementation.
        """
        self.reset()
        return self.add_chunk(audio)

    def flush(self) -> list[AudioSegment]:
        """
        Flush buffered state and emit any final segments.

        Placeholder structure for WALLBUG-050 implementation.
        """
        self._buffer.clear()
        return []

    def reset(self) -> None:
        """Reset processor state."""
        self._buffer.clear()
        self._current_start_ms = 0
        self._consumed_ms = 0


def audio_requires_conversion(source: str | Path, sample_rate: int, channels: int) -> bool:
    """Return True when an input file should be converted for transcription."""
    src = Path(source).expanduser()
    if src.suffix.lower() != ".wav":
        return True

    try:
        with wave.open(str(src), "rb") as wav_file:
            return (
                wav_file.getframerate() != int(sample_rate)
                or wav_file.getnchannels() != int(channels)
                or wav_file.getsampwidth() != 2
            )
    except (wave.Error, OSError):
        return True


def convert_audio_file(
    source: str | Path,
    destination: Optional[str | Path] = None,
    *,
    sample_rate: int = 16000,
    channels: int = 1,
    ffmpeg_path: str = "ffmpeg",
    overwrite: bool = True,
) -> Path:
    """Convert an audio file to 16-bit PCM WAV suitable for transcription."""
    src = Path(source).expanduser()
    if not src.exists() or not src.is_file():
        raise AudioProcessorError("Audio source not found: {}".format(src))

    resolved_sample_rate = int(sample_rate)
    resolved_channels = int(channels)
    if resolved_sample_rate <= 0:
        raise AudioProcessorError("sample_rate must be greater than zero.")
    if resolved_channels <= 0:
        raise AudioProcessorError("channels must be greater than zero.")

    if destination is None:
        if src.suffix.lower() == ".wav":
            dst = src.with_name("{}_converted.wav".format(src.stem))
        else:
            dst = src.with_suffix(".wav")
    else:
        dst = Path(destination).expanduser()

    dst.parent.mkdir(parents=True, exist_ok=True)

    command = [
        ffmpeg_path,
        "-y" if overwrite else "-n",
        "-i",
        str(src),
        "-ac",
        str(resolved_channels),
        "-ar",
        str(resolved_sample_rate),
        "-vn",
        "-sn",
        "-dn",
        "-c:a",
        "pcm_s16le",
        str(dst),
    ]

    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise AudioProcessorError("ffmpeg executable not found: {}".format(ffmpeg_path)) from exc
    except OSError as exc:
        raise AudioProcessorError("Unable to start ffmpeg process: {}".format(exc)) from exc

    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "Unknown ffmpeg conversion error."
        raise AudioProcessorError(message)

    if not dst.exists() or not dst.is_file():
        raise AudioProcessorError("ffmpeg completed but output file was not created: {}".format(dst))

    return dst


def create_audio_processor(
    config: Optional[Config] = None,
    vad_engine: Optional[VADLike] = None,
) -> AudioProcessor:
    """Factory for AudioProcessor instances."""
    return AudioProcessor(config=config, vad_engine=vad_engine)


__all__ = [
    "AudioProcessorError",
    "VADLike",
    "AudioSegment",
    "AudioProcessor",
    "audio_requires_conversion",
    "convert_audio_file",
    "create_audio_processor",
]
