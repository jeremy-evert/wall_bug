"""Main transcriber script for Wall_Bug."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from wallbug.audio_processor import (
    AudioProcessorError,
    audio_requires_conversion,
    convert_audio_file,
)
from wallbug.metadata import attach_metadata


if TYPE_CHECKING:
    from wallbug.config import Config


def _load_config_symbols() -> tuple[type[Any], Any]:
    try:
        from wallbug.config import Config as runtime_config_class, load_config as runtime_load_config

        return runtime_config_class, runtime_load_config
    except Exception:
        legacy_module_name = "wallbug._transcriber_legacy_config"
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


class TranscriptionError(RuntimeError):
    """Raised when transcription cannot be completed."""


class Transcriber:
    """Runs local transcription through a whisper-compatible CLI binary."""

    def __init__(
        self,
        config: Optional[Config] = None,
        whisper_path: Optional[str] = None,
        ffmpeg_path: Optional[str] = None,
    ) -> None:
        self.config = config or load_config()
        self.whisper_path = whisper_path or self.config.tools.whisper_cpp_path
        self.ffmpeg_path = ffmpeg_path or self.config.tools.ffmpeg_path

    def resolve_source(self, source: Optional[str | Path]) -> Path:
        if source is not None:
            candidate = Path(source).expanduser()
            if candidate.exists() and candidate.is_file():
                return candidate
            raise TranscriptionError("Audio source not found: {}".format(candidate))

        audio_dir = self.config.paths.audio_dir.expanduser()
        if not audio_dir.exists():
            raise TranscriptionError(
                "No source provided and audio directory does not exist: {}".format(audio_dir)
            )

        files = [p for p in audio_dir.iterdir() if p.is_file()]
        if not files:
            raise TranscriptionError(
                "No source provided and no audio files found in: {}".format(audio_dir)
            )

        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return files[0]

    def build_output_path(
        self,
        source: Path,
        output_path: Optional[str | Path] = None,
    ) -> Path:
        if output_path is None:
            transcripts_dir = self.config.paths.transcripts_dir.expanduser()
            return transcripts_dir / "{}.txt".format(source.stem)

        target = Path(output_path).expanduser()
        if target.suffix:
            return target
        return target / "{}.txt".format(source.stem)

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
        src = self.resolve_source(source)
        prepared_src, temp_dir = self._prepare_source_for_transcription(src)

        try:
            target = self.build_output_path(src, output_path=output_path)
            target.parent.mkdir(parents=True, exist_ok=True)

            target_base = target.with_suffix("")
            command = self._build_command(
                source=prepared_src,
                output_base=target_base,
                model=model,
                language=language,
                device=device,
                beam_size=beam_size,
            )

            result = self._run(command)
            if result.returncode != 0:
                message = (
                    result.stderr.strip() or result.stdout.strip() or "Unknown transcription error."
                )
                raise TranscriptionError(message)

            generated = self._resolve_generated_file(prepared_src, target, target_base)
            transcript_text = generated.read_text(encoding="utf-8")

            if include_metadata:
                payload = attach_metadata(
                    transcript_text,
                    metadata={
                        "source": str(src.resolve()),
                        "transcription_source": str(prepared_src.resolve()),
                        "transcriber": str(self.whisper_path),
                        "model": model or self.config.transcription.model,
                        "language": language or self.config.transcription.language,
                        "device": device or self.config.transcription.device,
                        "beam_size": int(
                            self.config.transcription.beam_size if beam_size is None else beam_size
                        ),
                    },
                )
                target.write_text(payload["transcript"], encoding="utf-8")
                metadata_path = target.with_suffix(".metadata.json")
                metadata_path.write_text(
                    json.dumps(payload["metadata"], indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
            else:
                target.write_text(transcript_text, encoding="utf-8")

            if generated.resolve() != target.resolve():
                generated.unlink(missing_ok=True)

            return target
        finally:
            if temp_dir is not None:
                shutil.rmtree(temp_dir, ignore_errors=True)

    def _prepare_source_for_transcription(self, source: Path) -> tuple[Path, Optional[Path]]:
        target_sample_rate = int(self.config.recorder.sample_rate)
        target_channels = int(self.config.recorder.channels)

        if not audio_requires_conversion(
            source,
            sample_rate=target_sample_rate,
            channels=target_channels,
        ):
            return source, None

        temp_dir = Path(tempfile.mkdtemp(prefix="wallbug_transcriber_"))
        converted_path = temp_dir / "{}.wav".format(source.stem)

        try:
            converted = convert_audio_file(
                source,
                destination=converted_path,
                sample_rate=target_sample_rate,
                channels=target_channels,
                ffmpeg_path=self.ffmpeg_path,
                overwrite=True,
            )
        except AudioProcessorError as exc:
            raise TranscriptionError("Audio conversion failed: {}".format(exc)) from exc

        return converted, temp_dir

    def _build_command(
        self,
        source: Path,
        output_base: Path,
        model: Optional[str],
        language: Optional[str],
        device: Optional[str],
        beam_size: Optional[int],
    ) -> list[str]:
        resolved_model = self.config.transcription.model if model is None else model
        resolved_language = self.config.transcription.language if language is None else language
        resolved_device = self.config.transcription.device if device is None else device
        resolved_beam_size = (
            int(self.config.transcription.beam_size) if beam_size is None else int(beam_size)
        )

        command = [
            self.whisper_path,
            "-f",
            str(source),
            "-of",
            str(output_base),
            "-otxt",
        ]

        if resolved_model:
            command.extend(["-m", str(resolved_model)])
        if resolved_language:
            command.extend(["-l", str(resolved_language)])
        if resolved_beam_size > 0:
            command.extend(["-bs", str(resolved_beam_size)])
        if str(resolved_device).strip().lower() == "cpu":
            command.append("-ng")

        return command

    def _resolve_generated_file(self, source: Path, target: Path, output_base: Path) -> Path:
        candidates = [
            target,
            output_base.with_suffix(".txt"),
            source.with_suffix(".txt"),
        ]
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return candidate
        raise TranscriptionError("Transcription did not produce an output text file.")

    def _run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            raise TranscriptionError(
                "Transcriber executable not found: {}".format(self.whisper_path)
            ) from exc
        except OSError as exc:
            raise TranscriptionError("Unable to start transcriber process: {}".format(exc)) from exc


def transcribe_once(
    source: Optional[str | Path] = None,
    output_path: Optional[str | Path] = None,
    config: Optional[Config] = None,
) -> Path:
    transcriber = Transcriber(config=config)
    return transcriber.transcribe(source=source, output_path=output_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wallbug-transcriber",
        description="Transcribe Wall_Bug audio files.",
    )
    parser.add_argument("source", nargs="?", default=None, help="Optional audio source path.")
    parser.add_argument(
        "--output",
        default=None,
        help="Output transcript path (file or directory).",
    )
    parser.add_argument("--model", default=None, help="Optional transcription model override.")
    parser.add_argument("--language", default=None, help="Optional language override.")
    parser.add_argument("--device", default=None, help="Optional device override (cpu/gpu).")
    parser.add_argument("--beam-size", type=int, default=None, help="Optional beam size override.")
    parser.add_argument(
        "--no-metadata",
        action="store_true",
        help="Disable metadata sidecar generation.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    transcriber = Transcriber()
    try:
        output = transcriber.transcribe(
            source=args.source,
            output_path=args.output,
            model=args.model,
            language=args.language,
            device=args.device,
            beam_size=args.beam_size,
            include_metadata=not bool(args.no_metadata),
        )
    except TranscriptionError as exc:
        print("Transcription failed: {}".format(exc), file=sys.stderr)
        return 1

    print(str(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "TranscriptionError",
    "Transcriber",
    "transcribe_once",
    "build_parser",
    "main",
]
