"""Check the three card rules on the real application.

1. the pointer leaves -> the card disappears after two seconds
2. a click -> the card disappears
3. the pin button -> the card stays
"""

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

    app = praatao_run.Praatao(lang="zh", use_llm=False)
    print("backend:", app.backend)

    # Pretend the card is on screen, with a target rectangle.
    app.card.show("测试标题", "这是什么：测试内容。",
                  anchor=(100, 100), rect=(100, 100, 200, 130),
                  source="测试", signature=("k", "s"))
    app._current_rect = (100, 100, 200, 130)
    app._shown_signature = ("k", "s")
    app.pump()
    print("card visible:", app._card_visible())

    # -- rule 1: the pointer leaves -> gone after two seconds ---------
    user32.SetCursorPos(1600, 900)
    app._update_auto_hide(1600, 900)
    app.pump()
    print("just left  :", app._card_visible())
    time.sleep(2.4)
    app._update_auto_hide(1600, 900)
    app.pump()
    print("after 2 s  :", app._card_visible(), "(expected False)")

    # -- rule 3: pinned -> stays ---------------------------------------
    app.card.show("测试标题", "这是什么：测试内容。",
                  anchor=(100, 100), rect=(100, 100, 200, 130),
                  source="测试", signature=("k2", "s"))
    app._current_rect = (100, 100, 200, 130)
    app.pump()
    app.card.set_pinned(True)
    user32.SetCursorPos(1600, 900)
    time.sleep(2.4)
    app._update_auto_hide(1600, 900)
    app.pump()
    print("pinned     :", app._card_visible(), "(expected True)")

    # -- rule 2: a click -> dismissed ----------------------------------
    app.card.set_pinned(False)
    app._card_dismissed()
    app.pump()
    print("after click:", app._card_visible(), "(expected False)")

    app.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
