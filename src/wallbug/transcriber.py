"""Transcription utilities for Wall_Bug."""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from wallbug.archive import ArchiveError, ArchiveManager
from wallbug.logging import get_logger
from wallbug.metadata import attach_metadata


if TYPE_CHECKING:
    from wallbug.config import Config


_BOOTSTRAP_LOGGER = logging.getLogger(__name__)


def _load_config_symbols() -> tuple[type[Any], Any]:
    try:
        from wallbug.config import Config as runtime_config_class, load_config as runtime_load_config

        return runtime_config_class, runtime_load_config
    except Exception as primary_exc:
        legacy_module_name = "wallbug._transcriber_legacy_config"
        legacy_module_path = Path(__file__).resolve().with_name("config.py")
        _BOOTSTRAP_LOGGER.warning(
            "Failed to import wallbug.config, falling back to legacy config module at %s: %s",
            legacy_module_path,
            primary_exc,
        )

        module = sys.modules.get(legacy_module_name)
        if module is None:
            spec = importlib.util.spec_from_file_location(
                legacy_module_name,
                legacy_module_path,
            )
            if spec is None or spec.loader is None:
                _BOOTSTRAP_LOGGER.error(
                    "Unable to load config module from %s (missing import spec/loader).",
                    legacy_module_path,
                )
                raise ImportError(f"Unable to load config module from {legacy_module_path}")

            module = importlib.util.module_from_spec(spec)
            sys.modules[legacy_module_name] = module
            try:
                spec.loader.exec_module(module)
            except Exception as exc:
                _BOOTSTRAP_LOGGER.error(
                    "Failed to execute legacy config module %s: %s",
                    legacy_module_path,
                    exc,
                )
                raise ImportError(
                    f"Unable to execute config module from {legacy_module_path}: {exc}"
                ) from exc

        try:
            return module.Config, module.load_config
        except AttributeError as exc:
            _BOOTSTRAP_LOGGER.error(
                "Legacy config module at %s does not expose Config/load_config.",
                legacy_module_path,
            )
            raise ImportError(
                f"Config module at {legacy_module_path} is missing Config/load_config"
            ) from exc


Config, load_config = _load_config_symbols()


class TranscriptionError(RuntimeError):
    """Raised when transcription cannot be completed."""


class Transcriber:
    """Runs local transcription through a whisper-compatible CLI binary."""

    def __init__(
        self,
        config: Optional[Config] = None,
        whisper_path: Optional[str] = None,
    ) -> None:
        self.logger = get_logger(__name__)

        try:
            self.config = config or load_config()
        except Exception as exc:
            self.logger.error("Unable to load transcription configuration: %s", exc)
            raise TranscriptionError("Unable to load transcription configuration: {}".format(exc)) from exc

        self.whisper_path = whisper_path or self.config.tools.whisper_cpp_path
        if not str(self.whisper_path).strip():
            self.logger.warning("Configured transcriber executable path is empty.")

        try:
            self.archive_manager = ArchiveManager(config=self.config)
        except Exception as exc:
            self.logger.error("Unable to initialize archive manager: %s", exc)
            raise TranscriptionError("Unable to initialize archive manager: {}".format(exc)) from exc

    def resolve_source(self, source: Optional[str | Path]) -> Path:
        if source is not None:
            candidate = Path(source).expanduser()
            if candidate.exists() and candidate.is_file():
                self.logger.debug("Using provided audio source: %s", candidate)
                return candidate
            self.logger.error("Provided audio source was not found: %s", candidate)
            raise TranscriptionError(f"Audio source not found: {candidate}")

        audio_dir = self.config.paths.audio_dir.expanduser()
        if not audio_dir.exists():
            self.logger.error("Configured audio directory does not exist: %s", audio_dir)
            raise TranscriptionError(
                "No source provided and audio directory does not exist: {}".format(audio_dir)
            )

        try:
            files = [p for p in audio_dir.iterdir() if p.is_file()]
        except OSError as exc:
            self.logger.error("Unable to read configured audio directory %s: %s", audio_dir, exc)
            raise TranscriptionError(
                "Unable to read audio directory {}: {}".format(audio_dir, exc)
            ) from exc

        if not files:
            self.logger.error("No audio files found in configured audio directory: %s", audio_dir)
            raise TranscriptionError(
                "No source provided and no audio files found in: {}".format(audio_dir)
            )

        try:
            files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        except OSError as exc:
            self.logger.error("Unable to inspect files in audio directory %s: %s", audio_dir, exc)
            raise TranscriptionError(
                "Unable to inspect audio files in {}: {}".format(audio_dir, exc)
            ) from exc

        self.logger.debug("Auto-selected latest audio source: %s", files[0])
        return files[0]

    def build_output_path(
        self,
        source: Path,
        output_path: Optional[str | Path] = None,
    ) -> Path:
        if output_path is None:
            transcripts_dir = self.config.paths.transcripts_dir.expanduser()
            target = transcripts_dir / "{}.txt".format(source.stem)
            self.logger.debug("Resolved default transcript output path: %s", target)
            return target

        target = Path(output_path).expanduser()
        if target.suffix:
            self.logger.debug("Resolved explicit transcript output file: %s", target)
            return target

        resolved_target = target / "{}.txt".format(source.stem)
        self.logger.debug("Resolved transcript output directory to file path: %s", resolved_target)
        return resolved_target

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
        self.logger.info(
            "Starting transcription run (source=%s, output=%s, include_metadata=%s).",
            source,
            output_path,
            include_metadata,
        )
        try:
            src = self.resolve_source(source)
            target = self.build_output_path(src, output_path=output_path)

            try:
                target.parent.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                self.logger.error(
                    "Unable to create transcript output directory %s: %s",
                    target.parent,
                    exc,
                )
                raise TranscriptionError(
                    "Unable to create transcript output directory {}: {}".format(target.parent, exc)
                ) from exc

            target_base = target.with_suffix("")
            command = self._build_command(
                source=src,
                output_base=target_base,
                model=model,
                language=language,
                device=device,
                beam_size=beam_size,
            )
            self.logger.debug("Built transcriber command for source %s and target %s", src, target)

            result = self._run(command)
            if result.returncode != 0:
                message = result.stderr.strip() or result.stdout.strip() or "Unknown transcription error."
                self.logger.error(
                    "Transcriber process failed (returncode=%s, source=%s): %s",
                    result.returncode,
                    src,
                    message,
                )
                raise TranscriptionError(message)

            generated = self._resolve_generated_file(src, target, target_base)
            try:
                transcript_text = generated.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                raise TranscriptionError(
                    "Unable to read generated transcript {}: {}".format(generated, exc)
                ) from exc

            if include_metadata:
                try:
                    payload = attach_metadata(
                        transcript_text,
                        metadata={
                            "source": str(src.resolve()),
                            "transcriber": str(self.whisper_path),
                            "model": model or self.config.transcription.model,
                            "language": language or self.config.transcription.language,
                            "device": device or self.config.transcription.device,
                            "beam_size": int(
                                self.config.transcription.beam_size
                                if beam_size is None
                                else beam_size
                            ),
                        },
                    )
                    target.write_text(payload["transcript"], encoding="utf-8")
                    archive_path = self._archive_transcript_text(
                        payload["transcript"],
                        source=src,
                        transcript_target=target,
                    )
                    payload["metadata"]["archive_transcript"] = str(archive_path)
                    metadata_path = target.with_suffix(".metadata.json")
                    metadata_path.write_text(
                        json.dumps(payload["metadata"], indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                except (OSError, UnicodeError, TypeError, ValueError, KeyError) as exc:
                    self.logger.error(
                        "Unable to persist transcript metadata for %s: %s",
                        target,
                        exc,
                    )
                    raise TranscriptionError(
                        "Unable to persist transcript metadata for {}: {}".format(target, exc)
                    ) from exc
            else:
                try:
                    target.write_text(transcript_text, encoding="utf-8")
                except (OSError, UnicodeError) as exc:
                    self.logger.error("Unable to write transcript file %s: %s", target, exc)
                    raise TranscriptionError(
                        "Unable to write transcript file {}: {}".format(target, exc)
                    ) from exc
                self._archive_transcript_text(
                    transcript_text,
                    source=src,
                    transcript_target=target,
                )

            remove_generated = generated != target
            try:
                remove_generated = generated.resolve() != target.resolve()
            except OSError:
                pass

            if remove_generated:
                try:
                    generated.unlink(missing_ok=True)
                except OSError as exc:
                    self.logger.warning(
                        "Unable to remove temporary generated file %s: %s",
                        generated,
                        exc,
                    )

            self.logger.info("Transcription completed successfully: %s", target)
            return target
        except TranscriptionError as exc:
            self.logger.error("Transcription failed: %s", exc)
            raise
        except Exception as exc:
            self.logger.exception("Unexpected transcription failure.")
            raise TranscriptionError(
                "Unexpected transcription failure: {}".format(exc)
            ) from exc

    def _archive_transcript_text(
        self,
        text: str,
        source: Path,
        transcript_target: Path,
    ) -> Path:
        entry_id = (
            self.archive_manager.entry_id_from_path(source)
            or self.archive_manager.entry_id_from_path(transcript_target)
        )
        try:
            archived_path = self.archive_manager.archive_transcript(
                text=text,
                entry_id=entry_id,
                filename=transcript_target.name,
            )
            self.logger.debug("Archived transcript to: %s", archived_path)
            return archived_path
        except (ArchiveError, OSError, UnicodeError) as exc:
            self.logger.error("Failed to archive transcript for %s: %s", transcript_target, exc)
            raise TranscriptionError("Unable to archive transcript: {}".format(exc)) from exc

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
        beam_value = self.config.transcription.beam_size if beam_size is None else beam_size

        try:
            resolved_beam_size = int(beam_value)
        except (TypeError, ValueError) as exc:
            self.logger.error("Invalid beam size value: %s", beam_value)
            raise TranscriptionError("Invalid beam size value: {}".format(beam_value)) from exc

        executable = str(self.whisper_path).strip()
        if not executable:
            self.logger.error("Transcriber executable path is empty.")
            raise TranscriptionError("Transcriber executable path is empty.")

        command = [
            executable,
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

        resolved_device_text = "" if resolved_device is None else str(resolved_device).strip().lower()
        if resolved_device_text == "cpu":
            command.append("-ng")

        self.logger.debug(
            "Transcriber options resolved (model=%s, language=%s, device=%s, beam_size=%s).",
            resolved_model,
            resolved_language,
            resolved_device,
            resolved_beam_size,
        )
        return command

    def _resolve_generated_file(self, source: Path, target: Path, output_base: Path) -> Path:
        candidates = [
            target,
            output_base.with_suffix(".txt"),
            source.with_suffix(".txt"),
        ]
        for candidate in candidates:
            try:
                if candidate.exists() and candidate.is_file():
                    self.logger.debug("Resolved generated transcript file: %s", candidate)
                    return candidate
            except OSError as exc:
                self.logger.warning(
                    "Unable to inspect generated transcript candidate %s: %s",
                    candidate,
                    exc,
                )

        self.logger.error(
            "Transcription output file not found. Checked candidates: %s",
            ", ".join(str(p) for p in candidates),
        )
        raise TranscriptionError("Transcription did not produce an output text file.")

    def _run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        safe_command = [str(part) for part in command]
        self.logger.debug("Executing transcriber command: %s", " ".join(safe_command))
        try:
            result = subprocess.run(
                safe_command,
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            self.logger.error("Transcriber executable not found: %s", self.whisper_path)
            raise TranscriptionError(
                "Transcriber executable not found: {}".format(self.whisper_path)
            ) from exc
        except OSError as exc:
            self.logger.error("Unable to start transcriber process: %s", exc)
            raise TranscriptionError("Unable to start transcriber process: {}".format(exc)) from exc

        if result.stdout.strip():
            self.logger.debug("Transcriber stdout: %s", result.stdout.strip())
        if result.stderr.strip():
            self.logger.debug("Transcriber stderr: %s", result.stderr.strip())

        return result


def transcribe_once(
    source: Optional[str | Path] = None,
    output_path: Optional[str | Path] = None,
    config: Optional[Config] = None,
) -> Path:
    transcriber = Transcriber(config=config)
    return transcriber.transcribe(source=source, output_path=output_path)


def transcribe_command(args: argparse.Namespace) -> int:
    logger = get_logger(__name__)
    source = getattr(args, "source", None)
    output = getattr(args, "output", None)
    logger.debug("Received transcription CLI args: source=%s output=%s", source, output)
    try:
        target = transcribe_once(source=source, output_path=output)
    except TranscriptionError as exc:
        logger.error("Transcription failed: %s", exc)
        print("Transcription failed: {}".format(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        logger.exception("Unexpected failure while running transcription command.")
        print("Transcription failed: {}".format(exc), file=sys.stderr)
        return 1

    logger.info("Transcription command completed: %s", target)
    print(str(target))
    return 0


__all__ = [
    "TranscriptionError",
    "Transcriber",
    "transcribe_once",
    "transcribe_command",
]
