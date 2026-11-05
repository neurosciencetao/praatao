"""Global hotkeys, polled via ``GetAsyncKeyState`` (no extra dependencies)."""

from __future__ import annotations

import ctypes

user32 = ctypes.windll.user32

VK_CONTROL = 0x11
VK_MENU = 0x12
VK_SHIFT = 0x10
VK_ESCAPE = 0x1B
VK_F1 = 0x70
VK_F2 = 0x71

VK_P = 0x50
VK_N = 0x4E
VK_R = 0x52
VK_H = 0x48
VK_Q = 0x51
VK_S = 0x53
VK_X = 0x58


def _down(vk: int) -> bool:
    try:
        return bool(user32.GetAsyncKeyState(vk) & 0x8000)
    except Exception:
        return False


class Hotkeys:
    """Edge-triggered global hotkeys.

    Recognised combos (all global, i.e. they work while Praat has focus):

    ==============  ==========================================
    ``Ctrl+Alt+P``  show / hide the side panel
    ``Ctrl+Alt+N``  next lesson step
    ``Ctrl+Alt+R``  restart the current lesson
    ``Ctrl+Alt+H``  hide every overlay
    ``Ctrl+Alt+Q``  focus the question box
    ``Ctrl+Alt+S``  open the Praatao settings window
    ``Ctrl+Alt+X``  quit the coach
    ``F1``          pin / unpin the hover card
    ``Esc``         dismiss the hover card
    ==============  ==========================================
    """

    def __init__(self) -> None:
        self._prev: set[str] = set()

    def _current(self) -> set[str]:
        ctrl = _down(VK_CONTROL)
        alt = _down(VK_MENU)
        found: set[str] = set()
        if ctrl and alt:
            if _down(VK_P):
                found.add("panel")
            if _down(VK_N):
                found.add("next")
            if _down(VK_R):
                found.add("restart")
            if _down(VK_H):
                found.add("hide")
            if _down(VK_Q):
                found.add("ask")
            if _down(VK_S):
                found.add("settings")
            if _down(VK_X):
                found.add("quit")
        if _down(VK_F1):
            found.add("pin")
        if _down(VK_ESCAPE):
            found.add("escape")
        return found

    def poll(self) -> list[str]:
        """Return the hotkeys that were pressed since the last call."""
        current = self._current()
        pressed = current - self._prev
        self._prev = current
        return sorted(pressed)
