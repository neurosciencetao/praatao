"""Why does the menu close while the coach's tick loop is running?"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def main() -> int:
    import run as praatao_run
    from praatao.sensors.uia import PraatUI

    app = praatao_run.Praatao(lang="zh", use_llm=False)
    app.host.after(45, app._tick)
    ui = PraatUI()
    objects = ui.objects_window()
    print("objects:", objects.title if objects else None)

    items = ui.open_menu(objects, "Open", keep_open=True)
    print("items:", [i.key for i in items][:5])
    item = next((i for i in items if i.key == "Read from file..."), None)
    print("item rect:", item.rect if item else None)

    # Is the popup still open?
    from praatao.sensors import uia as uia_module

    ctrl = ui._control_from_window(objects)
    menus = [
        n for n, _d in ui._iter_controls(ctrl)
        if uia_module._text(n, "ControlTypeName") == "MenuControl"
    ]
    print("MenuControls now:", len(menus))
    for node in menus:
        print("   class:", uia_module._text(node, "ClassName"),
              "rect:", uia_module._safe_rect(node))

    # Now let the coach's tick loop run for a moment and look again.
    deadline = time.time() + 1.5
    while time.time() < deadline:
        app.pump()
        time.sleep(0.02)
    menus = [
        n for n, _d in ui._iter_controls(ctrl)
        if uia_module._text(n, "ControlTypeName") == "MenuControl"
    ]
    print("MenuControls after the tick loop:", len(menus))
    app.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
