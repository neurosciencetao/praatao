"""Which part of the tick loop closes Praat's open menu?"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def menus(ui, objects) -> int:
    from praatao.sensors import uia as uia_module

    ctrl = ui._control_from_window(objects)
    return len([
        n for n, _d in ui._iter_controls(ctrl)
        if uia_module._text(n, "ControlTypeName") == "MenuControl"
    ])


def main() -> int:
    from praatao.sensors.uia import PraatUI

    ui = PraatUI()
    objects = ui.objects_window()

    def open_again():
        items = ui.open_menu(objects, "Open", keep_open=True)
        print("  opened, items:", len(items), "| menus:", menus(ui, objects))
        return items

    items = open_again()

    print("A: element_at_point over the popup")
    el = ui.element_at_point(300, 60)
    print("   element:", getattr(el, "name", None), "| menus:", menus(ui, objects))

    items = open_again()
    print("B: a plain pump loop (no hover)")
    deadline = time.time() + 1.0
    while time.time() < deadline:
        time.sleep(0.02)
    print("   menus:", menus(ui, objects))

    items = open_again()
    print("C: the app's _handle_hover")
    import run as praatao_run

    app = praatao_run.Praatao(lang="zh", use_llm=False)
    app._handle_hover(300, 60)
    print("   menus:", menus(ui, objects))

    items = open_again()
    print("D: the app's _tick")
    app.host.after(45, app._tick)
    deadline = time.time() + 1.0
    while time.time() < deadline:
        app.pump()
        time.sleep(0.02)
    print("   menus:", menus(ui, objects))

    items = open_again()
    print("E: only the state probe")
    app._poll_state(time.time())
    deadline = time.time() + 1.5
    while time.time() < deadline:
        app.pump()
        time.sleep(0.02)
    print("   menus:", menus(ui, objects))

    items = open_again()
    print("F: only the hotkeys")
    deadline = time.time() + 1.0
    while time.time() < deadline:
        for hot in app.hotkeys.poll():
            print("   hotkey:", hot)
        time.sleep(0.02)
    print("   menus:", menus(ui, objects))

    app.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
