"""Diagnostic 5: does the Praat Objects window need focus to show its buttons?"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import uiautomation as auto  # noqa: E402
import win32gui  # noqa: E402

from praatao.sensors.uia import PraatUI  # noqa: E402


def buttons(ui, obj):
    return [b.name for b in ui.find_all(window=obj, control_type="ButtonControl")]


def selection(ui, obj):
    ctrl = ui._control_from_window(obj)
    for node, _d in ui._iter_controls(ctrl):
        try:
            if node.ControlTypeName == "ListControl":
                return [c.Name for c in node.GetSelectionPattern().GetSelection()]
        except Exception as exc:
            return f"error: {exc}"
    return None


def item_node(ui, obj):
    for node, _d in ui._iter_controls(ui._control_from_window(obj)):
        try:
            if node.ControlTypeName == "ListItemControl" and "Sound" in node.Name:
                return node
        except Exception:
            pass
    return None


def main() -> int:
    ui = PraatUI()
    obj = ui.objects_window()
    print("fg before:", win32gui.GetWindowText(auto.GetForegroundWindow()))
    print("buttons:", buttons(ui, obj))
    print("selection:", selection(ui, obj))

    print("\n== bring the Objects window to the foreground ==")
    try:
        win32gui.SetForegroundWindow(obj.hwnd)
    except Exception as exc:
        print("   failed:", exc)
    time.sleep(1.0)
    print("   fg now:", win32gui.GetWindowText(auto.GetForegroundWindow()))
    print("   buttons:", buttons(ui, obj))
    print("   selection:", selection(ui, obj))

    print("\n== real click on the list item ==")
    node = item_node(ui, obj)
    if node is not None:
        node.Click(simulateMove=False)
        time.sleep(0.8)
    print("   buttons:", buttons(ui, obj))
    print("   selection:", selection(ui, obj))

    print("\n== click on the second item ==")
    node = item_node(ui, obj)
    if node is not None:
        node.Click(simulateMove=False)
        time.sleep(0.8)
    print("   buttons:", buttons(ui, obj))
    print("   selection:", selection(ui, obj))

    return 0


if __name__ == "__main__":
    sys.exit(main())
