"""Diagnostic 4: how do we select an object in the Praat object list?"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from praatao.sensors.uia import PraatUI  # noqa: E402


def buttons(ui, obj):
    return [b.name for b in ui.find_all(window=obj, control_type="ButtonControl")]


def selected(ui, obj):
    """Read the selection through the list's SelectionPattern."""
    ctrl = ui._control_from_window(obj)
    for node, _d in ui._iter_controls(ctrl):
        try:
            if node.ControlTypeName == "ListControl":
                pattern = node.GetSelectionPattern()
                return [c.Name for c in pattern.GetSelection()]
        except Exception as exc:
            return f"error: {exc}"
    return None


def main() -> int:
    ui = PraatUI()
    obj = ui.objects_window()
    print("buttons:", buttons(ui, obj))
    print("selection:", selected(ui, obj))

    ctrl = ui._control_from_window(obj)
    item = None
    for node, _d in ui._iter_controls(ctrl):
        try:
            if node.ControlTypeName == "ListItemControl" and "Sound" in node.Name:
                item = node
                break
        except Exception:
            pass
    print("item:", item.Name if item else None)
    if item is None:
        return 1

    print("\n== SelectionItemPattern.Select() ==")
    try:
        item.GetSelectionItemPattern().Select()
    except Exception as exc:
        print("   failed:", exc)
    time.sleep(0.6)
    print("   buttons:", buttons(ui, obj))
    print("   selection:", selected(ui, obj))

    print("\n== Click(simulateMove=False) ==")
    item2 = None
    for node, _d in ui._iter_controls(ui._control_from_window(obj)):
        try:
            if node.ControlTypeName == "ListItemControl" and "Sound" in node.Name:
                item2 = node
                break
        except Exception:
            pass
    try:
        item2.Click(simulateMove=False)
    except Exception as exc:
        print("   failed:", exc)
    time.sleep(0.6)
    print("   buttons:", buttons(ui, obj))
    print("   selection:", selected(ui, obj))

    print("\n== Invoke pattern ==")
    item3 = None
    for node, _d in ui._iter_controls(ui._control_from_window(obj)):
        try:
            if node.ControlTypeName == "ListItemControl" and "Sound" in node.Name:
                item3 = node
                break
        except Exception:
            pass
    try:
        item3.GetInvokePattern().Invoke()
    except Exception as exc:
        print("   failed:", exc)
    time.sleep(0.6)
    print("   buttons:", buttons(ui, obj))
    print("   selection:", selected(ui, obj))

    return 0


if __name__ == "__main__":
    sys.exit(main())
