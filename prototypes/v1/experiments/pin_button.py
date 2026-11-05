"""The card's own buttons: pin, close, and the body.

The application owns the mouse handling (Windows gives the first click on
an inactive window to activating it), so the test calls the application
directly with the coordinates of the button.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def main() -> int:
    import run as praatao_run

    app = praatao_run.Praatao(lang="zh", use_llm=False)
    print("backend:", app.backend)

    def show() -> None:
        app.card.show("测试标题", "这是什么：测试内容。",
                      anchor=(200, 200), rect=(200, 200, 320, 240),
                      source="测试", signature=("k", "s"))
        app._current_rect = (200, 200, 320, 240)
        app.pump()

    show()
    print("card rect :", app._card_rect())
    print("pin rect  :", app.card.pin_rect())
    print("close rect:", app.card.close_rect())

    # -- a click on the pin ------------------------------------------
    pin = app.card.pin_rect()
    app._handle_click(pin[0] + 4, pin[1] + 4)
    app.pump()
    print("pinned      :", app.card.pinned, "(expected True)")
    print("card visible:", app._card_visible(), "(expected True)")

    # -- the card survives the application's own "a click means work" rule
    app._last_mouse_down = True
    app._tick()
    print("after tick  :", app._card_visible(), "(expected True)")

    # -- a click on the body dismisses it ------------------------------
    app.card.set_pinned(False)
    app._handle_click(app._card_rect()[0] + 60, app._card_rect()[1] + 60)
    app.pump()
    print("body click  :", app._card_visible(), "(expected False)")

    # -- a click on the close button dismisses it ---------------------
    show()
    close = app.card.close_rect()
    app._handle_click(close[0] + 4, close[1] + 4)
    app.pump()
    print("close click :", app._card_visible(), "(expected False)")

    # -- a click far away dismisses it --------------------------------
    show()
    app.card.set_pinned(False)
    app._handle_click(1800, 1000)
    app.pump()
    print("far click   :", app._card_visible(), "(expected False)")

    # -- a pinned card ignores the click ------------------------------
    show()
    app.card.set_pinned(True)
    app._handle_click(1800, 1000)
    app.pump()
    print("pinned click:", app._card_visible(), "(expected True)")

    app.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
