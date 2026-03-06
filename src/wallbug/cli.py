from __future__ import annotations

import argparse
from importlib import metadata
from typing import Callable, Dict, List, Optional

Handler = Callable[[argparse.Namespace], int]


def _resolve_version() -> str:
    for distribution_name in ("wallbug", "wall-bug"):
        try:
            return metadata.version(distribution_name)
        except metadata.PackageNotFoundError:
            continue
    return "0.0.0"


def _not_implemented(command_name: str) -> Handler:
    def _handler(_: argparse.Namespace) -> int:
        print("Command '{}' is not implemented yet.".format(command_name))
        return 0

    return _handler


def _help_handler(
    parser: argparse.ArgumentParser,
    command_parsers: Dict[str, argparse.ArgumentParser],
) -> Handler:
    def _handler(args: argparse.Namespace) -> int:
        topic = getattr(args, "topic", None)
        if topic is None:
            parser.print_help()
        else:
            command_parsers[topic].print_help()
        return 0

    return _handler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wallbug",
        description="Capture spoken ideas and convert them into structured notes.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase output verbosity.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s {}".format(_resolve_version()),
        help="Show Wall_Bug version and exit.",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.required = True
    command_parsers: Dict[str, argparse.ArgumentParser] = {}

    status = subparsers.add_parser("status", help="Show current Wall_Bug status.")
    status.set_defaults(handler=_not_implemented("status"))
    command_parsers["status"] = status

    daemon = subparsers.add_parser("daemon", help="Run Wall_Bug in daemon mode.")
    daemon.add_argument(
        "--foreground",
        action="store_true",
        help="Run in foreground instead of background mode.",
    )
    daemon.set_defaults(handler=_not_implemented("daemon"))
    command_parsers["daemon"] = daemon

    record = subparsers.add_parser("record", help="Record an audio note.")
    record.add_argument(
        "--duration",
        type=int,
        default=None,
        help="Optional recording duration in seconds.",
    )
    record.set_defaults(handler=_not_implemented("record"))
    command_parsers["record"] = record

    transcribe = subparsers.add_parser("transcribe", help="Transcribe recorded audio.")
    transcribe.add_argument(
        "source",
        nargs="?",
        default=None,
        help="Optional path to audio input.",
    )
    transcribe.set_defaults(handler=_not_implemented("transcribe"))
    command_parsers["transcribe"] = transcribe

    search = subparsers.add_parser("search", help="Search across saved notes.")
    search.add_argument("query", help="Search query.")
    search.set_defaults(handler=_not_implemented("search"))
    command_parsers["search"] = search

    summarize_day = subparsers.add_parser(
        "summarize-day",
        help="Generate a daily summary from notes.",
    )
    summarize_day.add_argument(
        "--date",
        default=None,
        help="Date to summarize (YYYY-MM-DD). Defaults to today.",
    )
    summarize_day.set_defaults(handler=_not_implemented("summarize-day"))
    command_parsers["summarize-day"] = summarize_day

    help_cmd = subparsers.add_parser(
        "help",
        help="Show help for Wall_Bug or a specific command.",
    )
    help_cmd.add_argument(
        "topic",
        nargs="?",
        choices=sorted(command_parsers.keys()),
        help="Command to show help for.",
    )
    help_cmd.set_defaults(handler=_help_handler(parser, command_parsers))
    command_parsers["help"] = help_cmd

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 2

    try:
        return int(handler(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
