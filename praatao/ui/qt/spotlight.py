"""Spotlight ring, drawn with Qt.

A soft orange ring around the control the card is talking about.  The
interior is genuinely transparent (not a hole in a coloured rectangle), so
Praat shows through and still receives the clicks.
"""

from __future__ import annotations

from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets

__all__ = ["QtSpotlight"]

RING = "#E8590C"
RING_SOFT = "#FFD8A8"


class _RingWindow(QtWidgets.QWidget):
    """A frameless translucent window that draws a rounded ring."""

    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.Tool
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
            | QtCore.Qt.WindowType.WindowDoesNotAcceptFocus
            | QtCore.Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_AlwaysStackOnTop, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        rect = QtCore.QRectF(2, 2, self.width() - 4, self.height() - 4)
        path = QtGui.QPainterPath()
        path.addRoundedRect(rect, 6, 6)
        soft = QtGui.QPen(QtGui.QColor(RING_SOFT), 5)
        hard = QtGui.QPen(QtGui.QColor(RING), 2)
        painter.setPen(soft)
        painter.drawPath(path)
        painter.setPen(hard)
        painter.drawPath(path)


class QtSpotlight:
    """A rounded rectangle drawn around a target."""

    def __init__(self, master: Any = None) -> None:
        self.master = master
        self.win = _RingWindow()
        self.win.setObjectName("PraataoSpotlight")
        self.win.hide()
        self._rect: tuple[int, int, int, int] | None = None

    def show(self, rect: tuple[int, int, int, int], pad: int = 6) -> None:
        left, top, right, bottom = rect
        x1 = left - pad
        y1 = top - pad
        x2 = right + pad
        y2 = bottom + pad
        width = max(8, x2 - x1)
        height = max(8, y2 - y1)
        self.win.setGeometry(x1, y1, width, height)
        self.win.show()
        self.win.raise_()
        self._rect = rect

    def hide(self) -> None:
        self._rect = None
        if self.win.isVisible():
            self.win.hide()

    def is_visible(self) -> bool:
        """Is the ring on screen?"""

        try:
            return bool(self.win.isVisible())
        except Exception:  # noqa: BLE001
            return False

    def destroy(self) -> None:
        try:
            self.win.close()
            self.win.deleteLater()
        except Exception:  # noqa: BLE001
            pass
