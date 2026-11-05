"""Does the second start bring the first coach's panel forward?"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import win32gui  # noqa: E402


def coach_windows() -> list[tuple[str, tuple[int, int, int, int], bool]]:
    found: list[tuple[str, tuple[int, int, int, int], bool]] = []

    def cb(hwnd, _extra):
        title = win32gui.GetWindowText(hwnd) or ""
        cls = win32gui.GetClassName(hwnd) or ""
        if "Qt" in cls and title == "Praatao":
            found.append(
                (title, win32gui.GetWindowRect(hwnd), win32gui.IsWindowVisible(hwnd))
            )
        return True

    win32gui.EnumWindows(cb, None)
    return found


def main() -> int:
    import os

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    run = [sys.executable, "run.py", "--no-praat", "--quiet"]

    first = subprocess.Popen(run, cwd=str(ROOT), env=env)
    time.sleep(6.0)
    print("windows after the first start:", coach_windows())

    second = subprocess.Popen(run, cwd=str(ROOT), env=env)
    time.sleep(6.0)
    print("the second copy is gone:", second.poll() is not None)
    print("windows after the second start:", coach_windows())

    # The panel is the window with a real size (the card is tiny).
    for title, rect, visible in coach_windows():
        width = rect[2] - rect[0]
        height = rect[3] - rect[1]
        print(f"   {title} {rect} visible={visible} size={width}x{height}")

    first.terminate()
    if second.poll() is None:
        second.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
