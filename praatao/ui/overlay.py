"""Shared Win32/Tk helpers for the overlay windows.

Every overlay window obeys three rules:

* always on top of Praat
* never steal keyboard focus from Praat
* never block mouse input that Praat should receive
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import tkinter as tk

user32 = ctypes.windll.user32

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TOOLWINDOW_ = WS_EX_TOOLWINDOW

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
HWND_TOPMOST = -1

user32.SetWindowPos.restype = wintypes.BOOL
user32.GetWindowLongW.restype = ctypes.c_long
user32.SetWindowLongW.restype = ctypes.c_long


def hwnd_of(widget: tk.Misc) -> int:
    """Top-level HWND of a Tk window (the frame, not the inner client area)."""
    try:
        frame = widget.wm_frame()
    except Exception:
        frame = ""
    if frame:
        try:
            hwnd = int(frame, 16)
            if hwnd:
                return hwnd
        except (TypeError, ValueError):
            pass
    return int(widget.winfo_id())


def _get_ex_style(hwnd: int) -> int:
    return int(user32.GetWindowLongW(hwnd, GWL_EXSTYLE))


def _set_ex_style(hwnd: int, style: int) -> None:
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ctypes.c_long(style))


def set_click_through(widget: tk.Misc, enabled: bool = True) -> bool:
    """Make a window transparent to mouse input (clicks pass through to Praat).

    ``WS_EX_LAYERED`` is deliberately **not** added here: a layered window
    that nobody configured with ``SetLayeredWindowAttributes`` renders
    invisible, and Tk only configures layering itself when
    ``-transparentcolor`` is used (which is how the spotlight gets its
    transparent hole).
    """
    try:
        hwnd = hwnd_of(widget)
        style = _get_ex_style(hwnd)
        if enabled:
            style |= WS_EX_TRANSPARENT
        else:
            style &= ~WS_EX_TRANSPARENT
        _set_ex_style(hwnd, style)
        return True
    except Exception:
        return False


def set_no_activate(widget: tk.Misc, enabled: bool = True) -> bool:
    """Stop the window from taking focus away from Praat."""
    try:
        hwnd = hwnd_of(widget)
        style = _get_ex_style(hwnd)
        if enabled:
            style |= WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
        else:
            style &= ~(WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
        _set_ex_style(hwnd, style)
        return True
    except Exception:
        return False


def keep_on_top(widget: tk.Misc) -> bool:
    try:
        widget.attributes("-topmost", True)
    except tk.TclError:
        pass
    try:
        hwnd = hwnd_of(widget)
        user32.SetWindowPos(
            wintypes.HWND(hwnd),
            wintypes.HWND(HWND_TOPMOST),
            0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
        )
    except Exception:
        pass
    return True


def screen_size() -> tuple[int, int]:
    try:
        return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)  # cx, cy
    except Exception:
        return (1920, 1080)


def cursor_pos() -> tuple[int, int]:
    """Current mouse position in screen pixels."""
    pt = wintypes.POINT()
    try:
        user32.GetCursorPos(ctypes.byref(pt))
    except Exception:
        return (0, 0)
    return (int(pt.x), int(pt.y))


def mouse_button_down(button: int = 1) -> bool:
    """Is the given mouse button currently held down?  1 = left."""
    try:
        return bool(user32.GetAsyncKeyState(button) & 0x8000)
    except Exception:
        return False


def clamp_rect(rect: tuple[int, int, int, int],
               width: int, height: int,
               margin: int = 8) -> tuple[int, int]:
    """Place a ``width x height`` window next to ``rect`` without leaving the screen.

    The window is put *beside* the target (never on top of it), so the
    control being explained stays visible and clickable.
    """
    screen_w, screen_h = screen_size()
    left, top, right, bottom = rect

    gap = 16
    x = right + gap
    if x + width + margin > screen_w:
        x = left - width - gap
    if x < margin:
        x = min(screen_w - width - margin, max(margin, right + gap))

    y = top - height // 2
    if y + height + margin > screen_h:
        y = screen_h - height - margin
    if y < margin:
        y = margin
    return (int(x), int(y))
