"""Basic logging helpers for Wall_Bug."""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional


if TYPE_CHECKING:
    from wallbug.config import Config


def _load_config_symbols() -> tuple[type[Any] | None, Any | None]:
    try:
        from wallbug.config import Config as runtime_config_class, load_config as runtime_load_config

        return runtime_config_class, runtime_load_config
    except Exception:
        legacy_module_name = "wallbug._logging_legacy_config"
        legacy_module_path = Path(__file__).resolve().with_name("config.py")
        if not legacy_module_path.exists():
            return None, None

        spec = importlib.util.spec_from_file_location(
            legacy_module_name,
            legacy_module_path,
        )
        if spec is None or spec.loader is None:
            return None, None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return getattr(module, "Config", None), getattr(module, "load_config", None)


Config, load_config = _load_config_symbols()

_DEFAULT_LEVEL = "INFO"
_DEFAULT_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_DEFAULT_LOGGER_NAME = "wallbug"
_DEFAULT_LOG_FILE = "wallbug.log"

_configured = False


def _normalize_level(level: str | int | None) -> int:
    if isinstance(level, int):
        return level
    if isinstance(level, str):
        normalized = level.strip().upper()
        if normalized.isdigit():
            return int(normalized)
        return int(getattr(logging, normalized, logging.INFO))
    return logging.INFO


def _extract_logging_config(config: Any) -> tuple[int, str]:
    if config is None:
        return _normalize_level(_DEFAULT_LEVEL), _DEFAULT_FORMAT

    logging_cfg = getattr(config, "logging", None)
    level_value = getattr(logging_cfg, "level", _DEFAULT_LEVEL)
    format_value = getattr(logging_cfg, "fmt", _DEFAULT_FORMAT)
    return _normalize_level(level_value), str(format_value)


def _default_log_path(config: Any) -> Optional[Path]:
    if config is None:
        return None
    paths_cfg = getattr(config, "paths", None)
    logs_dir = getattr(paths_cfg, "logs_dir", None)
    if logs_dir is None:
        return None
    return Path(logs_dir).expanduser() / _DEFAULT_LOG_FILE


def setup_logging(
    config: Optional["Config"] = None,
    *,
    logger_name: str = _DEFAULT_LOGGER_NAME,
    log_file: str | Path | None = None,
    console: bool = True,
    force: bool = False,
) -> logging.Logger:
    global _configured

    if config is None and callable(load_config):
        try:
            config = load_config()
        except Exception:
            config = None

    logger = logging.getLogger(logger_name)
    level, fmt = _extract_logging_config(config)
    formatter = logging.Formatter(fmt)

    if force:
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass

    if logger.handlers and not force:
        logger.setLevel(level)
        _configured = True
        return logger

    logger.setLevel(level)
    logger.propagate = False

    if console:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(level)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    resolved_log_file = Path(log_file).expanduser() if log_file is not None else _default_log_path(config)
    if resolved_log_file is not None:
        try:
            resolved_log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(resolved_log_file, encoding="utf-8")
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except OSError:
            pass

    _configured = True
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    global _configured

    if not _configured:
        setup_logging()

    if name:
        return logging.getLogger(name)
    return logging.getLogger(_DEFAULT_LOGGER_NAME)


__all__ = ["get_logger", "setup_logging"]
