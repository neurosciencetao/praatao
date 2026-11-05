"""Reproduce the flaky menu test, with tracing."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def main() -> int:
    import run as praatao_run
    from praatao.sensors import uia as uia_module
    from praatao.sensors.uia import PraatUI

    ui = PraatUI()
    objects = ui.objects_window()

    def menus() -> int:
        ctrl = ui._control_from_window(objects)
        return len([
            n for n, _d in ui._iter_controls(ctrl)
            if uia_module._text(n, "ControlTypeName") == "MenuControl"
        ])

    def make_app():
        app = praatao_run.Praatao(lang="zh", use_llm=False, ui_backend="qt")
        app.card.show("标题", "内容", anchor=(200, 200), rect=(200, 200, 320, 240),
                      source="测试", signature=("k", "s"))
        app._current_rect = (200, 200, 320, 240)
        app.pump()
        return app

    # --- test 1: a pinned card survives a click -----------------------
    app1 = make_app()
    app1.card.set_pinned(True)
    app1._handle_click(1800, 1000)
    app1.pump()
    print("test 1: pinned =", app1.card.pinned)
    app1.quit()

    # --- test 2: the menu must survive the coach -----------------------
    app = make_app()
    app.host.after(praatao_run.MOUSE_POLL_MS, app._mouse_poll)
    app.host.after(45, app._tick)

    if "--no-spot" in sys.argv:
        class FakeSpot:
            def show(self, rect, **kw):
                pass

            def hide(self):
                pass

            def destroy(self):
                pass

        app.spot = FakeSpot()
    if "--no-card" in sys.argv:
        app.card.show = lambda *a, **kw: None
    if "--no-hit" in sys.argv:
        app._element_under_cursor = lambda x, y: None
    if "--no-canvas" in sys.argv:
        app._canvas_under_cursor = lambda x, y: None
    for name in ("_poll_state", "_handle_hover", "_update_auto_hide"):
        original = getattr(app, name)

        def make(name=name, original=original):
            def traced(*args, **kwargs):
                original(*args, **kwargs)
                print(f"    after {name}: menus = {menus()}")
            return traced

        setattr(app, name, make())

    items = ui.open_menu(objects, "Open", keep_open=True)
    print("menu opened:", len(items), "menus:", menus())

    if "--move-to-item" in sys.argv:
        import ctypes

        item = next((i for i in items if i.key == "Read from file..."), None)
        if item is not None:
            ctypes.windll.user32.SetCursorPos(
                (item.rect[0] + item.rect[2]) // 2,
                (item.rect[1] + item.rect[3]) // 2,
            )
            print("moved to the item")
    deadline = time.time() + 3.0
    while time.time() < deadline:
        app.pump()
        time.sleep(0.02)
    print("after 3 s: menus =", menus())
    app.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
