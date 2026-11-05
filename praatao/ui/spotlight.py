"""Spotlight ring: draws attention to the control the card is talking about."""

from __future__ import annotations

import tkinter as tk

from .overlay import keep_on_top, set_click_through, set_no_activate

TRANSPARENT = "#010203"
RING = "#e8590c"
RING_SOFT = "#ffd8a8"


class Spotlight:
    """A rounded rectangle drawn around a target, with a transparent interior.

    Uses Tk's ``-transparentcolor`` so the middle of the ring shows Praat
    unchanged; falls back to a plain coloured rectangle on platforms that
    do not support it.
    """

    def __init__(self, master: tk.Tk) -> None:
        self.master = master
        self.win = tk.Toplevel(master)
        self.win.withdraw()
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.transparent = True
        try:
            self.win.attributes("-transparentcolor", TRANSPARENT)
        except tk.TclError:
            self.transparent = False

        self.canvas = tk.Canvas(
            self.win, highlightthickness=0, bd=0,
            bg=TRANSPARENT if self.transparent else "#fff3e6",
        )
        self.canvas.pack(fill="both", expand=True)
        self._rect: tuple[int, int, int, int] | None = None

        keep_on_top(self.win)
        set_no_activate(self.win, True)
        # The transparent interior comes from Tk's ``-transparentcolor``: the
        # magic colour is fully transparent *and* click-through, so Praat still
        # receives the click in the middle of the ring.

    def show(self, rect: tuple[int, int, int, int], pad: int = 6) -> None:
        left, top, right, bottom = rect
        x1 = left - pad
        y1 = top - pad
        x2 = right + pad
        y2 = bottom + pad
        width = max(8, x2 - x1)
        height = max(8, y2 - y1)

        self.canvas.delete("all")
        if self.transparent:
            self.canvas.create_rectangle(
                x1, y1, x2, y2, outline=RING_SOFT, width=5,
            )
            self.canvas.create_rectangle(
                x1, y1, x2, y2, outline=RING, width=2,
            )
        else:
            self.canvas.create_rectangle(x1, y1, x2, y2, outline=RING, width=3)

        self.win.geometry(f"{width}x{height}+{x1}+{y1}")
        if not self.win.winfo_viewable():
            self.win.deiconify()
        # Tk recreates the HWND on deiconify and then applies its own
        # ``-transparentcolor`` styles, which wipes our ex-style bits.  So the
        # styles are re-applied on the next idle tick, once Tk is done.
        def _restyle() -> None:
            set_no_activate(self.win, True)
            keep_on_top(self.win)

        try:
            self.win.after(0, _restyle)
        except tk.TclError:
            _restyle()
        self._rect = rect

    def hide(self) -> None:
        self._rect = None
        if self.win.winfo_viewable():
            self.win.withdraw()

    def destroy(self) -> None:
        try:
            self.win.destroy()
        except tk.TclError:
            pass
