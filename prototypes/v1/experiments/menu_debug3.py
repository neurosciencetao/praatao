"""Reproduce the menu failure that only shows up after other tests ran."""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import uiautomation as auto  # noqa: E402
import win32gui  # noqa: E402

from praatao.sensors import uia as U  # noqa: E402
from praatao.sensors.uia import PraatUI  # noqa: E402


def popups():
    out = []

    def cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            cls = win32gui.GetClassName(hwnd)
            if cls in ("#32768", "#32770", "PipWindow"):
                out.append((hwnd, cls, win32gui.GetWindowText(hwnd)))

    win32gui.EnumWindows(cb, None)
    return out


def report(tag: str) -> None:
    ui = PraatUI()
    w = ui.objects_window()
    print(f"\n[{tag}] objects window: {w}")
    ctrl = ui._control_from_window(w)
    item = None
    for node, _d in ui._iter_controls(ctrl, max_depth=8):
        if U._text(node, "ControlTypeName") == "MenuItemControl" and U._text(node, "Name") == "Open":
            item = node
            break
    print(f"[{tag}] menu item: {item}")
    if item is not None:
        r = U._safe_rect(item)
        print(f"[{tag}] rect={r} enabled={item.IsEnabled} hwnd={item.NativeWindowHandle}")
        print(f"[{tag}] tooltip covering centre: "
              f"{U._tooltip_covering((r[0]+r[2])//2, (r[1]+r[3])//2)}")
    print(f"[{tag}] popups now: {popups()}")
    print(f"[{tag}] foreground: {win32gui.GetForegroundWindow()} "
          f"{win32gui.GetWindowText(win32gui.GetForegroundWindow())!r}")
    items = ui.open_menu(w, "Open")
    print(f"[{tag}] open_menu -> {[i.key for i in items][:4]} (n={len(items)})")


def main() -> int:
    report("before")

    print("\n=== running test_advisor (the module that breaks it) ===")
    loader = unittest.TestLoader()
    suite = loader.discover(str(ROOT / "tests"), pattern="test_advisor.py")
    unittest.TextTestRunner(verbosity=0).run(suite)

    report("after")

    print("\n=== raw click test ===")
    ui = PraatUI()
    w = ui.objects_window()
    ctrl = ui._control_from_window(w)
    item = None
    for node, _d in ui._iter_controls(ctrl, max_depth=8):
        if U._text(node, "ControlTypeName") == "MenuItemControl" and U._text(node, "Name") == "Open":
            item = node
            break
    r = U._safe_rect(item)
    x, y = (r[0] + r[2]) // 2, (r[1] + r[3]) // 2
    print("raw click at", (x, y), "->", U._raw_click(x, y))
    time.sleep(1.0)
    print("popups:", popups())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
