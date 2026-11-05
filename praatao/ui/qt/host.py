"""Qt host: the application object and the event loop.

The Tk version of Praatao owns a ``tk.Tk`` root; the Qt version owns a
``QApplication``.  Both expose the same three things the rest of the program
needs:

``root``
    A widget to parent top-level windows to.
``after(ms, fn)``
    Run ``fn`` later, again and again.
``mainloop()`` / ``quit()``
    Run and stop the event loop.
"""

from __future__ import annotations

from typing import Any, Callable

__all__ = ["QtHost", "available", "qt_available"]


def qt_available() -> bool:
    """Is PySide6 importable?"""

    try:
        import PySide6  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


#: Alias kept for readability at the call sites.
available = qt_available


class QtHost:
    """Owns the ``QApplication`` and drives the timer."""

    def __init__(self) -> None:
        from PySide6 import QtWidgets

        self.app = QtWidgets.QApplication.instance()
        if self.app is None:
            self.app = QtWidgets.QApplication([])
        self.app.setApplicationName("Praatao")
        self.root = QtWidgets.QWidget()
        self.root.setWindowTitle("Praatao")
        self.root.setObjectName("PraataoRoot")
        self._timers: dict[Any, Any] = {}

    # -- the three things the program needs -------------------------
    def after(self, ms: int, fn: Callable[[], None]) -> None:
        """Run *fn* every *ms* milliseconds.

        Every callback gets its own timer, so several independent loops
        can run side by side (the hover tick and the fast mouse poll, for
        instance).  Calling ``after`` again with the same function
        restarts that function's timer.
        """

        from PySide6 import QtCore

        timer = self._timers.get(fn)
        if timer is None:
            timer = QtCore.QTimer()
            timer.timeout.connect(fn)
            self._timers[fn] = timer
        timer.start(max(1, int(ms)))

    def mainloop(self) -> None:
        self.app.exec()

    def quit(self) -> None:
        try:
            self.app.quit()
        except Exception:  # noqa: BLE001
            pass

    # -- helpers ----------------------------------------------------
    def process_events(self) -> None:
        """Let Qt repaint; used by the screenshot scripts."""

        try:
            self.app.processEvents()
        except Exception:  # noqa: BLE001
            pass
