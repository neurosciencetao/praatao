"""Which UIA call pulls Praat to the front?

``open_popup_items()`` walks the Praat window's tree.  Walking the tree
must not activate the window.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import win32gui  # noqa: E402

from praatao.sensors.uia import PraatUI  # noqa: E402


def foreground() -> str:
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return "<none>"
    return f"{win32gui.GetClassName(hwnd)} {win32gui.GetWindowText(hwnd)[:30]!r}"


def other_window() -> int:
    found = 0

    def _collect(hwnd: int, _extra: object) -> None:
        nonlocal found
        if found:
            return
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return
            cls = (win32gui.GetClassName(hwnd) or "").casefold()
            if "praat" in cls or cls in ("consolewindowclass", "progman",
                                        "thumbnaildevicehelperwnd"):
                return
            found = hwnd
        except Exception:
            return

    win32gui.EnumWindows(_collect, None)
    return found


def main() -> int:
    ui = PraatUI()
    windows = ui.windows()
    print("praat windows:", [(w.title, w.class_name) for w in windows])
    if not windows:
        return 1

    other = other_window()
    if other:
        win32gui.SetForegroundWindow(other)
        time.sleep(0.6)

    window = windows[0]
    print(f"foreground before : {foreground()}")

    control = ui._control_from_window(window)
    print(f"after the window control : {foreground()}")

    nodes = list(ui._iter_controls(control, max_depth=ui.MAX_DEPTH))
    print(f"after walking {len(nodes)} nodes : {foreground()}")

    items = ui.open_popup_items()
    print(f"after open_popup_items ({len(items)}) : {foreground()}")

    from praatao.sensors import uia as uia_module

    hit = uia_module.auto.ControlFromPoint(
        window.rect[0] + 20, window.rect[1] + 20
    )
    print(f"after a hit test : {foreground()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
