"""Transcription trigger primitives for Wall_Bug."""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Protocol

from wallbug.audio_processor import AudioSegment


if TYPE_CHECKING:
    from wallbug.config import Config


def _load_config_symbols() -> tuple[type[Any], Any]:
    try:
        from wallbug.config import Config as runtime_config_class, load_config as runtime_load_config

        return runtime_config_class, runtime_load_config
    except Exception:
        legacy_module_name = "wallbug._transcription_trigger_legacy_config"
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


class TranscriptionTriggerError(RuntimeError):
    """Raised when a transcription trigger operation cannot be completed."""


class AudioProcessorLike(Protocol):
    """Protocol for audio processors used by TranscriptionTrigger."""

    def add_chunk(self, chunk: bytes) -> list[AudioSegment]:
        """Add raw audio and return any detected segments."""
        ...

    def flush(self) -> list[AudioSegment]:
        """Flush buffered audio and return final segments."""
        ...

    def reset(self) -> None:
        """Reset processor state."""
        ...


class TranscriberLike(Protocol):
    """Protocol for transcribers used by TranscriptionTrigger."""

    def transcribe(
        self,
        source: Optional[str | Path] = None,
        output_path: Optional[str | Path] = None,
        model: Optional[str] = None,
        language: Optional[str] = None,
        device: Optional[str] = None,
        beam_size: Optional[int] = None,
        include_metadata: bool = True,
    ) -> Path:
        """Transcribe an audio source and return the generated transcript path."""
        ...


@dataclass(frozen=True)
class TriggerEvent:
    """Represents one trigger decision produced from audio processing."""

    segment: AudioSegment
    should_transcribe: bool
    reason: str


class TranscriptionTrigger:
    """Coordinates segment detection with transcription trigger decisions."""

    def __init__(
        self,
        config: Optional[Config] = None,
        audio_processor: Optional[AudioProcessorLike] = None,
        transcriber: Optional[TranscriberLike] = None,
        min_segment_ms: int = 300,
    ) -> None:
        self.config = config or load_config()
        self.audio_processor = audio_processor
        self.transcriber = transcriber
        self.min_segment_ms = int(min_segment_ms)

        self._processed_segments = 0

    def add_audio_chunk(self, chunk: bytes) -> list[TriggerEvent]:
        """
        Consume a chunk of raw audio and return trigger events.

        Placeholder structure for WALLBUG-052 implementation.
        """
        if not isinstance(chunk, (bytes, bytearray)):
            raise TranscriptionTriggerError("chunk must be bytes-like.")
        if self.audio_processor is None:
            raise TranscriptionTriggerError("audio_processor is not configured.")
        if not chunk:
            return []

        segments = self.audio_processor.add_chunk(bytes(chunk))
        return self._build_events(segments)

    def flush(self) -> list[TriggerEvent]:
        """
        Flush buffered audio and return final trigger events.

        Placeholder structure for WALLBUG-052 implementation.
        """
        if self.audio_processor is None:
            raise TranscriptionTriggerError("audio_processor is not configured.")
        return self._build_events(self.audio_processor.flush())

    def reset(self) -> None:
        """Reset trigger state and delegated processor state."""
        self._processed_segments = 0
        if self.audio_processor is not None:
            self.audio_processor.reset()

    def _build_events(self, segments: list[AudioSegment]) -> list[TriggerEvent]:
        events: list[TriggerEvent] = []
        for segment in segments:
            duration_ms = max(0, int(segment.end_ms) - int(segment.start_ms))
            should_transcribe = duration_ms >= self.min_segment_ms
            reason = (
                "segment_duration_ms={} meets threshold {}".format(
                    duration_ms, self.min_segment_ms
                )
                if should_transcribe
                else "segment_duration_ms={} below threshold {}".format(
                    duration_ms, self.min_segment_ms
                )
            )
            events.append(
                TriggerEvent(
                    segment=segment,
                    should_transcribe=should_transcribe,
                    reason=reason,
                )
            )
            self._processed_segments += 1
        return events


def create_transcription_trigger(
    config: Optional[Config] = None,
    audio_processor: Optional[AudioProcessorLike] = None,
    transcriber: Optional[TranscriberLike] = None,
) -> TranscriptionTrigger:
    """Factory for TranscriptionTrigger instances."""
    return TranscriptionTrigger(
        config=config,
        audio_processor=audio_processor,
        transcriber=transcriber,
    )


__all__ = [
    "TranscriptionTriggerError",
    "AudioProcessorLike",
    "TranscriberLike",
    "TriggerEvent",
    "TranscriptionTrigger",
    "create_transcription_trigger",
]
