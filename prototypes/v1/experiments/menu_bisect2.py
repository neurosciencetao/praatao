"""Which part of the tick loop closes Praat's open menu?

One variable at a time, and the timer is stopped between the runs so that
nothing leaks from one case into the next.
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


class FakeSpot:
    def show(self, rect, **kw):
        pass

    def hide(self):
        pass

    def destroy(self):
        pass


def main() -> int:
    import run as praatao_run
    from praatao.sensors.uia import PraatUI

    ui = PraatUI()
    objects = ui.objects_window()
    app = praatao_run.Praatao(lang="zh", use_llm=False)
    timer = getattr(app.host, "_timer", None)

    def stop():
        if timer is not None:
            timer.stop()

    def open_again():
        stop()
        time.sleep(0.1)
        items = ui.open_menu(objects, "Open", keep_open=True)
        print(f"  opened: {len(items)} items, menus={menus(ui, objects)}")
        return items

    def run_with(label: str, **patched) -> None:
        stop()
        saved = {name: getattr(app, name) for name in patched}
        for name, value in patched.items():
            setattr(app, name, value)
        if timer is not None:
            timer.start(45)
        deadline = time.time() + 1.2
        while time.time() < deadline:
            app.pump()
            time.sleep(0.02)
        stop()
        print(f"  {label}: menus = {menus(ui, objects)}")
        for name, value in saved.items():
            setattr(app, name, value)

    open_again()
    run_with("D0 everything (control)")
    open_again()
    run_with("D1 no hover", _handle_hover=lambda x, y: None)
    open_again()
    run_with("D2 no poll_state", _poll_state=lambda now: None)
    open_again()
    run_with("D3 no spotlight", spot=FakeSpot())
    open_again()
    run_with("D4 no canvas sensor", canvas=None)

    app.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
