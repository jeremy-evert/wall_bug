"""Audio recording utilities for Wall_Bug."""

from __future__ import annotations

import importlib.util
import math
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional


if TYPE_CHECKING:
    from wallbug.config import Config


def _load_config_symbols() -> tuple[type[Any], Any]:
    try:
        from wallbug.config import Config as runtime_config_class, load_config as runtime_load_config

        return runtime_config_class, runtime_load_config
    except Exception:
        legacy_module_name = "wallbug._recorder_legacy_config"
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


class RecorderError(RuntimeError):
    """Raised when recording cannot be started or completed."""


class Recorder:
    """Records microphone audio to files and in-memory buffers via ffmpeg."""

    def __init__(
        self,
        config: Optional[Config] = None,
        ffmpeg_path: Optional[str] = None,
        input_format: str = "pulse",
        input_source: str = "default",
    ) -> None:
        self.config = config or load_config()
        self.ffmpeg_path = ffmpeg_path or self.config.tools.ffmpeg_path
        self.input_format = input_format
        self.input_source = input_source

        self._process: Optional[subprocess.Popen[bytes]] = None
        self._output_path: Optional[Path] = None

    @property
    def is_recording(self) -> bool:
        return self._process is not None and self._process.poll() is None

    @property
    def output_path(self) -> Optional[Path]:
        return self._output_path

    def build_filename(
        self,
        created_at: Optional[datetime] = None,
        prefix: str = "recording",
    ) -> str:
        ts = (created_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
        ext = self.config.recorder.output_format.strip().lstrip(".") or "wav"
        return "{}_{}.{}".format(prefix, ts.strftime("%Y%m%dT%H%M%S%fZ"), ext)

    def build_output_path(
        self,
        output_path: Optional[str | Path] = None,
        created_at: Optional[datetime] = None,
    ) -> Path:
        if output_path is not None:
            target = Path(output_path).expanduser()
            if target.suffix:
                return target
            return target / self.build_filename(created_at=created_at)

        audio_dir = self.config.paths.audio_dir.expanduser()
        return audio_dir / self.build_filename(created_at=created_at)

    def start(
        self,
        duration: Optional[float] = None,
        output_path: Optional[str | Path] = None,
        overwrite: bool = True,
    ) -> Path:
        if self.is_recording:
            raise RecorderError("Recorder is already running.")

        target = self.build_output_path(output_path=output_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        if not overwrite and target.exists():
            raise RecorderError("Refusing to overwrite existing file: {}".format(target))

        command = self._base_ffmpeg_input_command()
        command.extend(
            [
                "-ac",
                str(self.config.recorder.channels),
                "-ar",
                str(self.config.recorder.sample_rate),
            ]
        )

        seconds = self._resolve_duration(duration)
        if seconds is not None:
            command.extend(["-t", self._format_duration(seconds)])

        command.extend(["-y" if overwrite else "-n", str(target)])

        self._process = self._spawn(command, capture_stdout=False)
        self._output_path = target
        return target

    def wait(self, timeout: Optional[float] = None) -> int:
        if self._process is None:
            raise RecorderError("Recorder has not been started.")

        process = self._process
        try:
            return_code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise RecorderError("Timed out while waiting for recording to finish.") from exc

        self._process = None
        if return_code != 0:
            raise RecorderError(
                "ffmpeg exited with status {}: {}".format(
                    return_code, self._read_stderr(process)
                )
            )
        return return_code

    def stop(self, timeout: float = 5.0) -> Optional[int]:
        if self._process is None:
            return None

        process = self._process
        if process.poll() is not None:
            self._process = None
            return process.returncode

        try:
            process.send_signal(signal.SIGINT)
        except Exception:
            process.terminate()

        try:
            return_code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            return_code = process.wait()

        self._process = None
        return return_code

    def record_buffer(
        self,
        duration: float,
        sample_rate: Optional[int] = None,
        channels: Optional[int] = None,
        chunk_size: Optional[int] = None,
    ) -> bytes:
        seconds = self._resolve_duration(duration)
        if seconds is None:
            raise RecorderError("record_buffer requires a finite duration.")

        sr = int(self.config.recorder.sample_rate if sample_rate is None else sample_rate)
        ch = int(self.config.recorder.channels if channels is None else channels)
        frames_per_chunk = int(
            self.config.recorder.chunk_size if chunk_size is None else chunk_size
        )

        if sr <= 0:
            raise RecorderError("Sample rate must be greater than zero.")
        if ch <= 0:
            raise RecorderError("Channels must be greater than zero.")
        if frames_per_chunk <= 0:
            raise RecorderError("Chunk size must be greater than zero.")

        bytes_per_chunk = frames_per_chunk * ch * 2

        command = self._base_ffmpeg_input_command()
        command.extend(
            [
                "-t",
                self._format_duration(seconds),
                "-ac",
                str(ch),
                "-ar",
                str(sr),
                "-f",
                "s16le",
                "pipe:1",
            ]
        )

        process = self._spawn(command, capture_stdout=True)
        if process.stdout is None:
            raise RecorderError("Unable to capture ffmpeg stdout for buffer recording.")

        payload = bytearray()
        try:
            while True:
                block = process.stdout.read(bytes_per_chunk)
                if not block:
                    break
                payload.extend(block)
        finally:
            process.stdout.close()

        return_code = process.wait()
        if return_code != 0:
            raise RecorderError(
                "ffmpeg exited with status {}: {}".format(
                    return_code, self._read_stderr(process)
                )
            )

        return bytes(payload)

    def _base_ffmpeg_input_command(self) -> list[str]:
        return [
            self.ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-f",
            self.input_format,
            "-i",
            self.input_source,
        ]

    def _spawn(
        self,
        command: list[str],
        *,
        capture_stdout: bool,
    ) -> subprocess.Popen[bytes]:
        try:
            return subprocess.Popen(
                command,
                stdout=subprocess.PIPE if capture_stdout else subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise RecorderError("ffmpeg executable not found: {}".format(self.ffmpeg_path)) from exc
        except OSError as exc:
            raise RecorderError("Unable to start ffmpeg process: {}".format(exc)) from exc

    def _resolve_duration(self, duration: Optional[float]) -> Optional[float]:
        if duration is None:
            configured = float(self.config.recorder.max_record_seconds)
            if not math.isfinite(configured):
                raise RecorderError("Configured max_record_seconds must be finite.")
            if configured <= 0:
                return None
            return configured

        value = float(duration)
        if not math.isfinite(value) or value <= 0:
            raise RecorderError("Duration must be a finite number greater than zero.")
        return value

    def _format_duration(self, seconds: float) -> str:
        return "{:.3f}".format(seconds).rstrip("0").rstrip(".")

    def _read_stderr(self, process: subprocess.Popen[bytes]) -> str:
        if process.stderr is None:
            return ""
        return process.stderr.read().decode("utf-8", errors="replace").strip()


def record_once(
    duration: Optional[float] = None,
    output_path: Optional[str | Path] = None,
    config: Optional[Config] = None,
) -> Path:
    recorder = Recorder(config=config)
    target = recorder.start(duration=duration, output_path=output_path)
    recorder.wait()
    return target


__all__ = [
    "RecorderError",
    "Recorder",
    "record_once",
]
