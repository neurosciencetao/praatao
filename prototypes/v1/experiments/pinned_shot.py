"""The pinned card, with the real mouse."""

from __future__ import annotations

import ctypes
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

user32 = ctypes.windll.user32


def main() -> int:
    import run as praatao_run
    from praatao.sensors.uia import PraatUI

    app = praatao_run.Praatao(lang="zh", use_llm=True)
    app.host.after(praatao_run.MOUSE_POLL_MS, app._mouse_poll)
    app.host.after(45, app._tick)

    ui = PraatUI()
    objects = ui.objects_window()
    ui._activate(objects)
    time.sleep(0.6)

    target = ui.find("Sound help")
    print("target:", target.name if target else None, target.rect if target else None)
    x = (target.rect[0] + target.rect[2]) // 2
    y = (target.rect[1] + target.rect[3]) // 2
    user32.SetCursorPos(x, y)

    deadline = time.time() + 2.5
    while time.time() < deadline:
        app.pump()
        time.sleep(0.02)
    print("card visible:", app._card_visible(), "| rect:", app._card_rect())
    print("card body   :", app.card.body.toPlainText()[:40].replace("\n", " "))

    pin = app.card.pin_rect()
    print("pin rect    :", pin)
    user32.SetCursorPos(pin[0] + 6, pin[1] + 6)
    time.sleep(0.3)
    from praatao.ui.overlay import cursor_pos

    cx, cy = cursor_pos()
    print("cursor now  :", (cx, cy))
    print("on card     :", app._pointer_on_card(cx, cy))
    print("card rect   :", app._card_rect())
    print("in pin rect :", pin[0] <= cx <= pin[2] and pin[1] <= cy <= pin[3])

    original_click = app._handle_click

    def traced_click(px, py):
        print("  >> _handle_click", (px, py), "pin:", app.card.pin_rect(),
              "on card:", app._pointer_on_card(px, py))
        original_click(px, py)
        print("  >> pinned now:", app.card.pinned)

    app._handle_click = traced_click

    original_dismiss = app._dismiss_hover

    def traced_dismiss():
        import traceback
        print("  >> _dismiss_hover called from:")
        traceback.print_stack(limit=6)
        original_dismiss()

    app._dismiss_hover = traced_dismiss
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    deadline = time.time() + 0.2
    while time.time() < deadline:
        app.pump()
        time.sleep(0.005)
    user32.mouse_event(0x0004, 0, 0, 0, 0)
    deadline = time.time() + 1.5
    while time.time() < deadline:
        app.pump()
        time.sleep(0.02)
    print("pinned      :", app.card.pinned)
    print("card visible:", app._card_visible())

    from PIL import ImageGrab

    OUT = ROOT / "docs" / "screenshots" / "acceptance"
    OUT.mkdir(parents=True, exist_ok=True)
    ImageGrab.grab(all_screens=True).save(OUT / "04-pinned.png")
    print("saved")
    app.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
