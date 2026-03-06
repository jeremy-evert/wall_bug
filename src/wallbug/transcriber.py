"""Main transcriber script for Wall_Bug."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from wallbug.commands.transcribe import Transcriber, TranscriptionError
from wallbug.config import Config, load_config


class TranscriberCLIError(RuntimeError):
    """Raised when CLI input for transcriber is invalid."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wallbug-transcriber",
        description="Transcribe audio using Wall_Bug and whisper-compatible tooling.",
    )
    parser.add_argument(
        "source",
        nargs="?",
        default=None,
        help="Optional audio source path. Defaults to the newest file in audio_dir.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output transcript path or directory.",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Optional JSON config file path.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Transcription model override.",
    )
    parser.add_argument(
        "--language",
        default=None,
        help="Language override (example: en).",
    )
    parser.add_argument(
        "--device",
        default=None,
        help="Device override (example: cpu).",
    )
    parser.add_argument(
        "--beam-size",
        type=int,
        default=None,
        help="Beam size override.",
    )
    parser.add_argument(
        "--whisper-path",
        default=None,
        help="Override whisper executable path.",
    )
    parser.add_argument(
        "--no-metadata",
        action="store_true",
        help="Do not write metadata alongside transcript output.",
    )
    return parser


def _resolve_config(config_path: Optional[str | Path]) -> Config:
    try:
        return load_config(config_path=config_path)
    except Exception as exc:
        raise TranscriberCLIError("Failed to load config: {}".format(exc)) from exc


def run(args: argparse.Namespace) -> int:
    config = _resolve_config(getattr(args, "config", None))
    transcriber = Transcriber(
        config=config,
        whisper_path=getattr(args, "whisper_path", None),
    )

    try:
        output_path = transcriber.transcribe(
            source=getattr(args, "source", None),
            output_path=getattr(args, "output", None),
            model=getattr(args, "model", None),
            language=getattr(args, "language", None),
            device=getattr(args, "device", None),
            beam_size=getattr(args, "beam_size", None),
            include_metadata=not bool(getattr(args, "no_metadata", False)),
        )
    except TranscriptionError as exc:
        print("Transcription failed: {}".format(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print("Unexpected transcriber error: {}".format(exc), file=sys.stderr)
        return 1

    print(str(output_path))
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        return run(args)
    except TranscriberCLIError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "TranscriberCLIError",
    "build_parser",
    "run",
    "main",
]
