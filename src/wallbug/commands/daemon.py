"""Daemon command support for Wall_Bug."""

from __future__ import annotations

import argparse
import importlib.util
import signal
import sys
import threading
from pathlib import Path
from types import FrameType
from typing import TYPE_CHECKING, Any, Callable, Optional


if TYPE_CHECKING:
    from wallbug.config import Config


def _load_config_symbols() -> tuple[type[Any], Any]:
    try:
        from wallbug.config import Config as runtime_config_class, load_config as runtime_load_config

        return runtime_config_class, runtime_load_config
    except Exception:
        legacy_module_name = "wallbug._daemon_legacy_config"
        legacy_module_path = Path(__file__).resolve().parent.parent / "config.py"

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


class DaemonError(RuntimeError):
    """Raised when daemon execution cannot proceed."""


class WallBugDaemon:
    """Basic daemon skeleton for long-running Wall_Bug tasks."""

    def __init__(
        self,
        config: Optional[Config] = None,
        *,
        poll_interval_seconds: float = 1.0,
    ) -> None:
        if poll_interval_seconds <= 0:
            raise DaemonError("poll_interval_seconds must be greater than zero.")

        self.config = config or load_config()
        self.poll_interval_seconds = float(poll_interval_seconds)
        self._stop_requested = threading.Event()
        self._is_running = False

    @property
    def is_running(self) -> bool:
        return self._is_running

    def request_stop(self) -> None:
        self._stop_requested.set()

    def run_foreground(self) -> int:
        if self._is_running:
            raise DaemonError("Daemon is already running.")

        previous_handlers = self._install_signal_handlers()
        self._is_running = True
        self._stop_requested.clear()

        try:
            self._ensure_directories()
            while not self._stop_requested.is_set():
                self.tick()
                self._stop_requested.wait(self.poll_interval_seconds)
            return 0
        finally:
            self._is_running = False
            self._restore_signal_handlers(previous_handlers)

    def run_background(self) -> int:
        # Background process management is intentionally minimal for now.
        self._ensure_directories()
        self.tick()
        return 0

    def tick(self) -> None:
        """Single daemon iteration."""
        return None

    def _ensure_directories(self) -> None:
        paths = self.config.paths
        required = (
            paths.base_dir,
            paths.data_dir,
            paths.audio_dir,
            paths.transcripts_dir,
            paths.notes_dir,
            paths.summaries_dir,
            paths.logs_dir,
            paths.archive_dir,
        )
        for directory in required:
            Path(directory).expanduser().mkdir(parents=True, exist_ok=True)

    def _install_signal_handlers(self) -> dict[int, Any]:
        if threading.current_thread() is not threading.main_thread():
            return {}

        def _handler(_: int, __: FrameType | None) -> None:
            self.request_stop()

        previous: dict[int, Any] = {}
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous[signum] = signal.getsignal(signum)
            signal.signal(signum, _handler)
        return previous

    def _restore_signal_handlers(self, previous: dict[int, Any]) -> None:
        if threading.current_thread() is not threading.main_thread():
            return
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def handle(args: argparse.Namespace, config: Optional[Config] = None) -> int:
    daemon = WallBugDaemon(config=config)
    if bool(getattr(args, "foreground", False)):
        return daemon.run_foreground()
    return daemon.run_background()


run: Callable[[argparse.Namespace], int] = handle

__all__ = [
    "DaemonError",
    "WallBugDaemon",
    "handle",
    "run",
]
