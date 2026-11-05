"""Catch the close of a window.

Qt only lets a ``QObject`` be installed as an event filter, and the
wrappers in this package (``QtSidePanel``, ``QtSettingsWindow``, the
greeting window) are plain Python objects.  This small ``QObject`` is the
bridge: it watches the window and calls the wrapper's ``on_close``
callback when the student closes it.
"""

from __future__ import annotations

from typing import Any


def _watcher_class() -> Any:
    from PySide6 import QtCore

    class _CloseWatcher(QtCore.QObject):
        """Call ``host.on_close`` when the watched window is closed."""

        def __init__(self, host: Any) -> None:
            super().__init__()
            self._host = host

        def eventFilter(self, obj: Any, event: Any) -> bool:
            if event.type() == QtCore.QEvent.Type.Close:
                callback = getattr(self._host, "on_close", None)
                if callback is not None:
                    try:
                        callback()
                    except Exception:  # noqa: BLE001
                        pass
            return False

    return _CloseWatcher


def watch_close(window: Any, host: Any) -> Any:
    """Watch *window*; when it is closed, ``host.on_close()`` is called."""

    try:
        watcher = _watcher_class()(host)
        window.installEventFilter(watcher)
        # Keep a reference: without it the watcher is garbage collected
        # and the filter disappears with it.
        setattr(host, "_close_watcher", watcher)
        return watcher
    except Exception:  # noqa: BLE001
        return None
