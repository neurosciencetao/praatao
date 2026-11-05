"""Regression check: an open Praat menu must survive the coach.

Prints what the probe does while the menu is open.
"""

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
    import run as praatao_run
    from praatao.sensors.uia import PraatUI, _menu_popup_open

    ui = PraatUI()
    objects = ui.objects_window()
    assert objects is not None
    ui.close_popup()
    time.sleep(0.4)

    app = praatao_run.Praatao(lang="zh", use_llm=False)

    # Watch the probe.
    original_snapshot = app.probe.snapshot

    def snapshot():
        print(f"  [probe] starts, menu open = {_menu_popup_open()}")
        result = original_snapshot()
        print("  [probe] done")
        return result

    app.probe.snapshot = snapshot

    app.host.after(45, app._tick)
    time.sleep(1.2)

    items = ui.open_menu(objects, "Open", keep_open=True)
    print("menu opened  : items =", len(items), "| menus =", menus(ui, objects))

    start = time.time()
    deadline = start + 15.0
    while time.time() < deadline:
        app.pump()
        time.sleep(0.05)
        if menus(ui, objects) == 0:
            print(f"  the menu died after {time.time() - start:.1f} s")
            break
    print("after 15 s   : menus =", menus(ui, objects))
    print("state        : selected =",
          [o.name for o in (app.state.selected if app.state else [])],
          "| objects =", len(app.state.objects if app.state else []))
    app.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
