"""Diagnostic: what does open_menu return, and does ESC disturb Praat?"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from praatao.sensors.uia import PraatUI, praat_available  # noqa: E402


def snapshot(ui, label):
    obj = ui.objects_window()
    print(f"\n-- {label} --")
    if obj is None:
        print("   no objects window")
        return
    buttons = ui.find_all(window=obj, control_type="ButtonControl")
    print("   buttons:", [b.name for b in buttons])
    items = ui.find_all(window=obj, control_type="ListItemControl")
    print("   list items:", [i.name for i in items])
    menus = ui.find_all(window=obj, control_type="MenuControl")
    print("   menuctrl:", [m.name for m in menus])


def main() -> int:
    print("praat_available:", praat_available())
    ui = PraatUI()
    snapshot(ui, "before open_menu")

    obj = ui.objects_window()
    assert obj is not None
    items = ui.open_menu(obj, "Open", timeout=3.0)
    print("\n== open_menu returned", len(items), "items ==")
    for it in items:
        print(f"   [{it.control_type}] {it.name!r} -> key={it.key!r} depth={it.depth}")

    time.sleep(0.5)
    snapshot(ui, "after open_menu")

    # Try ESC while a popup is open, and check the selection afterwards.
    print("\n== manual: click Open, check selection, ESC, check selection ==")
    from praatao.sensors import uia

    ctrl = ui._control_from_window(obj)
    menu_item = None
    for node, _d in ui._iter_controls(ctrl):
        try:
            if node.ControlTypeName == "MenuItemControl" and node.Name == "Open":
                menu_item = node
                break
        except Exception:
            pass
    ui._click_control(menu_item)
    time.sleep(0.8)
    snapshot(ui, "popup open")
    uia.auto.SendKeys("{ESC}")
    time.sleep(0.8)
    snapshot(ui, "after ESC")

    return 0


if __name__ == "__main__":
    sys.exit(main())
