"""Diagnostic 3: restore the object selection and verify open_menu is polite."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from praatao.sensors.uia import PraatUI  # noqa: E402


def buttons(ui, obj):
    return [b.name for b in ui.find_all(window=obj, control_type="ButtonControl")]


def main() -> int:
    ui = PraatUI()
    obj = ui.objects_window()
    assert obj is not None

    print("buttons now:", buttons(ui, obj))
    if "View & Edit" not in buttons(ui, obj):
        print("\n== selecting the first Sound in the list ==")
        items = ui.find_all(window=obj, control_type="ListItemControl")
        print("   list items:", [i.name for i in items])
        target = next((i for i in items if "Sound" in i.name), None)
        if target is None:
            print("   no sound in the list")
            return 1
        print("   invoking:", target.name)
        print("   invoke ->", ui.invoke(target))
        time.sleep(0.8)
        print("   buttons after:", buttons(ui, obj))

    print("\n== open_menu x2, selection must survive ==")
    for round_no in (1, 2):
        items = ui.open_menu(obj, "Open", timeout=3.0)
        time.sleep(0.5)
        btns = buttons(ui, obj)
        menus = ui.find_all(window=obj, control_type="MenuControl")
        print(
            f"   round {round_no}: items={len(items)} "
            f"first={[i.key for i in items][:2]} "
            f"popup_open={bool(menus)} view_edit={'View & Edit' in btns}"
        )

    print("\n== open_menu on a missing menu (must not disturb anything) ==")
    items = ui.open_menu(obj, "NoSuchMenu", timeout=1.0)
    time.sleep(0.4)
    btns = buttons(ui, obj)
    print(f"   items={len(items)} view_edit={'View & Edit' in btns}")

    print("\n== element_at_point over a popup item ==")
    ui.open_menu(obj, "Open", timeout=3.0)
    menus = ui.find_all(window=obj, control_type="MenuControl")
    print("   popup present:", [m.name for m in menus])
    ui._close_popup(obj, None)

    return 0


if __name__ == "__main__":
    sys.exit(main())
