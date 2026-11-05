"""Closing the panel must end the whole program."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import win32con  # noqa: E402
import win32gui  # noqa: E402


def find_panel() -> int:
    found = 0

    def cb(hwnd, _extra):
        nonlocal found
        title = win32gui.GetWindowText(hwnd) or ""
        cls = win32gui.GetClassName(hwnd) or ""
        if "Qt" in cls and title == "Praatao" and win32gui.IsWindowVisible(hwnd):
            rect = win32gui.GetWindowRect(hwnd)
            if rect[2] - rect[0] > 200:
                found = int(hwnd)
        return True

    win32gui.EnumWindows(cb, None)
    return found


def main() -> int:
    import os

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    run = [sys.executable, "run.py", "--no-praat", "--quiet"]

    print("1. start the coach and open the panel (Ctrl+Alt+P is hard to send,")
    print("   so start it twice: the second start brings the panel forward)")
    first = subprocess.Popen(run, cwd=str(ROOT), env=env)
    time.sleep(6.0)
    second = subprocess.Popen(run, cwd=str(ROOT), env=env)
    time.sleep(6.0)

    panel = find_panel()
    print("   panel window:", panel)
    if not panel:
        first.terminate()
        if second.poll() is None:
            second.terminate()
        return 1

    print("2. close the panel (the X a student would click)")
    win32gui.PostMessage(panel, win32con.WM_CLOSE, 0, 0)
    time.sleep(4.0)
    print("   the coach left:", first.poll() is not None)

    if first.poll() is None:
        first.terminate()
    if second.poll() is None:
        second.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
