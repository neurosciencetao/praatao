"""The Qt front-end of Praatao.

Everything in this package is optional: when PySide6 is not installed the
program falls back to the Tk implementation in :mod:`praatao.ui`.
"""

from __future__ import annotations

from .host import QtHost, qt_available

__all__ = ["QtHost", "qt_available", "hover", "panel", "spotlight"]


def _lazy(name: str):  # pragma: no cover - thin import shim
    from importlib import import_module

    module = import_module(f"{__name__}.{name}")
    return {
        "hover": getattr(module, "QtHoverCard"),
        "panel": getattr(module, "QtSidePanel"),
        "spotlight": getattr(module, "QtSpotlight"),
    }[name]
