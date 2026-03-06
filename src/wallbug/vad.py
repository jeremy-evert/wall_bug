"""Voice Activity Detection (VAD) interfaces for Wall_Bug."""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Protocol, runtime_checkable


if TYPE_CHECKING:
    from wallbug.config import Config


def _load_config_symbols() -> tuple[type[Any], Any]:
    try:
        from wallbug.config import Config as runtime_config_class, load_config as runtime_load_config

        return runtime_config_class, runtime_load_config
    except Exception:
        legacy_module_name = "wallbug._vad_legacy_config"
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


class VADError(RuntimeError):
    """Raised when VAD operations cannot be completed."""


@runtime_checkable
class VADEngine(Protocol):
    """Interface for pluggable VAD backends."""

    def is_speech(self, audio_chunk: bytes, sample_rate: int) -> bool:
        """Return True when the audio chunk contains speech."""


@dataclass(frozen=True)
class VADResult:
    """VAD inference result for one audio chunk."""

    is_speech: bool
    sample_rate: int
    num_bytes: int


class VoiceActivityDetector:
    """High-level VAD facade used by Wall_Bug processing components."""

    def __init__(
        self,
        config: Optional[Config] = None,
        engine: Optional[VADEngine] = None,
    ) -> None:
        self.config = config or load_config()
        self.engine = engine

    @property
    def has_engine(self) -> bool:
        return self.engine is not None

    def is_speech(
        self,
        audio_chunk: bytes,
        sample_rate: Optional[int] = None,
    ) -> bool:
        if not isinstance(audio_chunk, (bytes, bytearray, memoryview)):
            raise VADError("audio_chunk must be a bytes-like object.")

        if self.engine is None:
            raise VADError("No VAD engine configured.")

        resolved_sample_rate = int(
            self.config.recorder.sample_rate if sample_rate is None else sample_rate
        )
        if resolved_sample_rate <= 0:
            raise VADError("sample_rate must be greater than zero.")

        try:
            return bool(self.engine.is_speech(bytes(audio_chunk), resolved_sample_rate))
        except Exception as exc:
            raise VADError("VAD engine failed: {}".format(exc)) from exc

    def detect(
        self,
        audio_chunk: bytes,
        sample_rate: Optional[int] = None,
    ) -> VADResult:
        resolved_sample_rate = int(
            self.config.recorder.sample_rate if sample_rate is None else sample_rate
        )
        decision = self.is_speech(audio_chunk=audio_chunk, sample_rate=resolved_sample_rate)
        return VADResult(
            is_speech=decision,
            sample_rate=resolved_sample_rate,
            num_bytes=len(bytes(audio_chunk)),
        )

    def reset(self) -> None:
        if self.engine is None:
            return
        reset_fn = getattr(self.engine, "reset", None)
        if callable(reset_fn):
            reset_fn()


def create_detector(
    config: Optional[Config] = None,
    engine: Optional[VADEngine] = None,
) -> VoiceActivityDetector:
    return VoiceActivityDetector(config=config, engine=engine)


__all__ = [
    "VADError",
    "VADEngine",
    "VADResult",
    "VoiceActivityDetector",
    "create_detector",
]
