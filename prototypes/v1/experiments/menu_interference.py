"""Why does the menu close when another test ran before it?"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def main() -> int:
    import run as praatao_run
    from praatao.sensors import uia as uia_module
    from praatao.sensors.praat_state import PraatStateProbe
    from praatao.sensors.uia import PraatUI

    ui = PraatUI()
    objects = ui.objects_window()

    def menus() -> int:
        ctrl = ui._control_from_window(objects)
        return len([
            n for n, _d in ui._iter_controls(ctrl)
            if uia_module._text(n, "ControlTypeName") == "MenuControl"
        ])

    # --- the first test: a pinned card ---------------------------------
    app1 = praatao_run.Praatao(lang="zh", use_llm=False, ui_backend="qt")
    app1.card.show("t", "b", anchor=(200, 200), rect=(200, 200, 320, 240),
                   source="", signature=("k", "s"))
    app1._current_rect = (200, 200, 320, 240)
    app1._handle_click(1800, 1000)
    app1.pump()
    print("test 1 done; quitting")
    app1.quit()

    # --- the second test: the menu must survive ------------------------
    original_send = PraatStateProbe.send

    def spy(self, script, timeout=10.0):  # noqa: ANN001
        print("  !! a Praat script was sent")
        return original_send(self, script, timeout)

    PraatStateProbe.send = spy  # type: ignore[method-assign]
    app = praatao_run.Praatao(lang="zh", use_llm=False, ui_backend="qt")
    app.host.after(praatao_run.MOUSE_POLL_MS, app._mouse_poll)
    app.host.after(45, app._tick)

    original_poll = app._poll_state

    def traced_poll(now: float) -> None:
        original_poll(now)
        print("  poll done, menus =", menus())

    app._poll_state = traced_poll
    original_hover = app._handle_hover

    def traced_hover(x: int, y: int) -> None:
        original_hover(x, y)
        print("  hover done, menus =", menus())

    app._handle_hover = traced_hover

    items = ui.open_menu(objects, "Open", keep_open=True)
    print("menu opened:", len(items), "menus:", menus())
    deadline = time.time() + 3.0
    while time.time() < deadline:
        app.pump()
        time.sleep(0.02)
        if menus() == 0:
            print("  the menu died")
            break
    print("after 3 s: menus =", menus())
    PraatStateProbe.send = original_send  # type: ignore[method-assign]
    app.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
