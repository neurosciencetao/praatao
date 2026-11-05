"""Hovering a menu item must explain it *and* leave the menu open."""

from __future__ import annotations

import ctypes
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def main() -> int:
    import run as praatao_run
    from praatao.sensors import uia as uia_module
    from praatao.sensors.uia import PraatUI

    user32 = ctypes.windll.user32
    ui = PraatUI()
    objects = ui.objects_window()

    def menus() -> int:
        ctrl = ui._control_from_window(objects)
        return len([
            n for n, _d in ui._iter_controls(ctrl)
            if uia_module._text(n, "ControlTypeName") == "MenuControl"
        ])

    app = praatao_run.Praatao(lang="zh", use_llm=False, ui_backend="qt")
    app.host.after(praatao_run.MOUSE_POLL_MS, app._mouse_poll)
    app.host.after(45, app._tick)

    items = ui.open_menu(objects, "Open", keep_open=True)
    item = next((i for i in items if i.key == "Read from file..."), None)
    print("opened:", len(items), "| item:", item.key if item else None)
    user32.SetCursorPos(
        (item.rect[0] + item.rect[2]) // 2, (item.rect[1] + item.rect[3]) // 2
    )
    deadline = time.time() + 3.0
    while time.time() < deadline:
        app.pump()
        time.sleep(0.02)
    print("menus       :", menus(), "(expected 1)")
    print("card shown  :", app._card_visible())
    print("card title  :", app.card.title_label.text() if app._card_visible() else "")
    ui.close_popup()
    app.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
