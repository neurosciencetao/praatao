"""Why does the hover card sometimes not appear?"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import run as praatao_run  # noqa: E402
from praatao.sensors.uia import PraatUI, praat_has_focus  # noqa: E402


def centre(rect):
    return (rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2


def main() -> int:
    ui = PraatUI()
    objects = ui.objects_window()
    app = praatao_run.Praatao(lang="zh", use_llm=False, ui_backend="qt")
    app.host.after(praatao_run.MOUSE_POLL_MS, app._mouse_poll)
    app.host.after(45, app._tick)

    ui._activate(objects)
    time.sleep(0.6)
    target = ui.find("Sound help")
    print("target:", target.name if target else None, target.rect if target else None)
    print("praat has focus:", praat_has_focus())

    import ctypes

    x, y = centre(target.rect)
    ctypes.windll.user32.SetCursorPos(x, y)
    for moment in range(0, 24):
        app.pump()
        time.sleep(0.1)
        if moment % 6 == 5:
            print(
                f"  {moment/10:4.1f}s card={app._card_visible()} "
                f"key={app._last_key!r} misses={app._misses} "
                f"focus={praat_has_focus()} menu={app._menu_open()}"
            )
    app.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
