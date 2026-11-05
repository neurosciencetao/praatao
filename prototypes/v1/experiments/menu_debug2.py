"""Raw Win32 click on the Praat menu bar."""

from __future__ import annotations

import ctypes
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import win32api  # noqa: E402
import win32con  # noqa: E402
import win32gui  # noqa: E402

user32 = ctypes.windll.user32


def popup_windows():
    out = []

    def cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            cls = win32gui.GetClassName(hwnd)
            if cls in ("#32768", "#32770"):
                out.append((hwnd, cls, win32gui.GetWindowText(hwnd)))

    win32gui.EnumWindows(cb, None)
    return out


def raw_click(x, y):
    user32.SetCursorPos(x, y)
    time.sleep(0.25)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.08)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def main() -> int:
    for label, (x, y) in (("Praat", (38, 40)), ("Open", (118, 40)), ("Help", (518, 40))):
        user32.SetCursorPos(700, 700)
        time.sleep(0.5)
        raw_click(x, y)
        time.sleep(0.9)
        print(f"{label:6s} click at ({x},{y}) -> popups: {popup_windows()}")

    # Also: is the Objects window enabled / does it have focus?
    print("\nfocus window:", win32gui.GetForegroundWindow(),
          repr(win32gui.GetWindowText(win32gui.GetForegroundWindow())))
    for hwnd in (3738320,):
        print("objects enabled:", win32gui.IsWindowEnabled(hwnd),
              "visible:", win32gui.IsWindowVisible(hwnd))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
