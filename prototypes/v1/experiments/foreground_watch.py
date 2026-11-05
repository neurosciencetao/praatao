"""Does Praat jump to the front even when the coach is not running?

If it does, the cause is not the coach but something else on this
machine (another program, or Praat itself).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import tkinter  # noqa: E402

import win32gui  # noqa: E402


def foreground() -> str:
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return "<none>"
    return f"{win32gui.GetClassName(hwnd)} {win32gui.GetWindowText(hwnd)[:26]!r}"


def main() -> int:
    root = tkinter.Tk()
    root.title("Praatao watcher")
    root.geometry("320x120+40+700")
    root.update()
    frame = int(root.wm_frame(), 16)
    win32gui.SetForegroundWindow(frame)
    time.sleep(0.6)
    print("foreground now:", foreground())

    start = time.time()
    last = foreground()
    while time.time() - start < 20.0:
        time.sleep(0.05)
        now = foreground()
        if now != last:
            print(f"{time.time() - start:6.2f}s  {last[:36]} -> {now[:36]}")
            last = now
    print("done; foreground:", foreground())
    root.destroy()
    return 0


if __name__ == "__main__":
    sys.exit(main())
