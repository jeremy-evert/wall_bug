"""Configuration package entrypoint.

This package currently bridges to the legacy single-file configuration
implementation in ``wallbug/config.py`` while exposing a package interface.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any


_LEGACY_MODULE_NAME = "wallbug._legacy_config"
_LEGACY_MODULE_PATH = Path(__file__).resolve().parent.parent / "config.py"


def _load_legacy_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        _LEGACY_MODULE_NAME,
        _LEGACY_MODULE_PATH,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load legacy config module from {_LEGACY_MODULE_PATH}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_legacy = _load_legacy_module()

ENV_PREFIX = _legacy.ENV_PREFIX
PathsConfig = _legacy.PathsConfig
RecorderConfig = _legacy.RecorderConfig
TranscriptionConfig = _legacy.TranscriptionConfig
LLMConfig = _legacy.LLMConfig
LoggingConfig = _legacy.LoggingConfig
ToolsConfig = _legacy.ToolsConfig
Config = _legacy.Config
load_config = _legacy.load_config

__all__ = [
    "ENV_PREFIX",
    "PathsConfig",
    "RecorderConfig",
    "TranscriptionConfig",
    "LLMConfig",
    "LoggingConfig",
    "ToolsConfig",
    "Config",
    "load_config",
]


def __getattr__(name: str) -> Any:
    try:
        return getattr(_legacy, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__() -> list[str]:
    return sorted(set(__all__) | set(dir(_legacy)))
