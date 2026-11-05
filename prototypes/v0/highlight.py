"""Simple always-on-top highlight rectangle over a Praat window region."""

from __future__ import annotations

import tkinter as tk

from praat_bridge import PraatWindow


class HighlightOverlay:
    def __init__(self) -> None:
        self.root = tk.Toplevel()
        self.root.title("praatao-highlight")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        try:
            self.root.attributes("-alpha", 0.35)
        except tk.TclError:
            pass
        self.root.configure(bg="#e85d04")
        self.root.withdraw()
        self._visible = False
        self._last_geom: tuple[int, int, int, int] | None = None

    def hide(self) -> None:
        if self._visible:
            self.root.withdraw()
            self._visible = False
            self._last_geom = None

    def show_on_window(
        self,
        win: PraatWindow | None,
        *,
        nx: float = 0.52,
        ny: float = 0.38,
        nw: float = 0.42,
        nh: float = 0.1,
    ) -> None:
        if win is None:
            self.hide()
            return
        left, top, right, bottom = win.rect
        width = max(1, right - left)
        height = max(1, bottom - top)
        x = int(left + nx * width)
        y = int(top + ny * height)
        w = int(nw * width)
        h = int(nh * height)
        geom = (x, y, w, h)
        if self._visible and geom == self._last_geom:
            return  # avoid flicker from resetting geometry every poll
        self._last_geom = geom
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        if not self._visible:
            self.root.deiconify()
            self._visible = True

    def destroy(self) -> None:
        try:
            self.root.destroy()
        except tk.TclError:
            pass
