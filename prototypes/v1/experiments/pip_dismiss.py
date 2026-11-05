"""How do we get rid of Praat's stuck tooltip ('pip') window?"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import win32con  # noqa: E402
import win32gui  # noqa: E402

from praatao.sensors import uia as U  # noqa: E402
from praatao.sensors.uia import PraatUI  # noqa: E402


def pips():
    out = []

    def cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            cls = win32gui.GetClassName(hwnd) or ""
            title = win32gui.GetWindowText(hwnd) or ""
            if cls.casefold() == "mouseinc" or title.casefold() == "pipwindow":
                out.append((hwnd, cls, title))

    win32gui.EnumWindows(cb, None)
    return out


def main() -> int:
    print("pips at start:", pips())

    for method in ("escape", "wm_close", "hide"):
        print(f"\n--- dismiss via {method} ---")
        for hwnd, cls, title in pips():
            try:
                if method == "escape":
                    win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0)
                    win32gui.PostMessage(hwnd, win32con.WM_KEYUP, win32con.VK_ESCAPE, 0)
                elif method == "wm_close":
                    win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                else:
                    win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
            except Exception as exc:
                print("   failed:", exc)
        time.sleep(0.6)
        print("   pips now:", pips())
        print("   foreground:", win32gui.GetForegroundWindow(),
              repr(win32gui.GetWindowText(win32gui.GetForegroundWindow())))

        ui = PraatUI()
        w = ui.objects_window()
        items = ui.open_menu(w, "Open")
        print("   open_menu ->", [i.key for i in items][:3], "n=", len(items))
        if items:
            print("   SUCCESS with method", method)
            return 0
        time.sleep(0.5)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
