from __future__ import annotations

import argparse
from importlib import metadata
from typing import Callable, Dict, List, Optional

from wallbug.commands import daemon, record, search, summarize_day, transcribe

Handler = Callable[[argparse.Namespace], int]


def _resolve_version() -> str:
    for distribution_name in ("wallbug", "wall-bug"):
        try:
            return metadata.version(distribution_name)
        except metadata.PackageNotFoundError:
            continue
    return "0.0.0"


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

    # STATUS
    status = subparsers.add_parser("status", help="Show current Wall_Bug status.")
    status.set_defaults(handler=lambda args: print("WallBug status OK") or 0)
    command_parsers["status"] = status

    # DAEMON
    daemon_cmd = subparsers.add_parser("daemon", help="Run Wall_Bug in daemon mode.")
    daemon_cmd.add_argument(
        "--foreground",
        action="store_true",
        help="Run in foreground instead of background mode.",
    )
    daemon_cmd.set_defaults(handler=lambda args: daemon.run(args) or 0)
    command_parsers["daemon"] = daemon_cmd

    # RECORD
    record_cmd = subparsers.add_parser("record", help="Record an audio note.")
    record_cmd.add_argument(
        "--duration",
        type=int,
        default=None,
        help="Optional recording duration in seconds.",
    )
    record_cmd.set_defaults(handler=lambda args: record.run(args) or 0)
    command_parsers["record"] = record_cmd

    # TRANSCRIBE
    transcribe_cmd = subparsers.add_parser("transcribe", help="Transcribe recorded audio.")
    transcribe_cmd.add_argument(
        "source",
        nargs="?",
        default=None,
        help="Optional path to audio input.",
    )
    transcribe_cmd.set_defaults(handler=lambda args: transcribe.run(args) or 0)
    command_parsers["transcribe"] = transcribe_cmd

    # SEARCH
    search_cmd = subparsers.add_parser("search", help="Search across saved notes.")
    search_cmd.add_argument("query", help="Search query.")
    search_cmd.set_defaults(handler=lambda args: search.run(args) or 0)
    command_parsers["search"] = search_cmd

    # SUMMARIZE
    summarize_cmd = subparsers.add_parser(
        "summarize-day",
        help="Generate a daily summary from notes.",
    )
    summarize_cmd.add_argument(
        "--date",
        default=None,
        help="Date to summarize (YYYY-MM-DD). Defaults to today.",
    )
    summarize_cmd.set_defaults(handler=lambda args: summarize_day.run(args) or 0)
    command_parsers["summarize-day"] = summarize_cmd

    # HELP
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
        result = handler(args)
        return int(result) if isinstance(result, int) else 0
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
