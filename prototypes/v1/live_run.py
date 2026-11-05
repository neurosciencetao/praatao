"""Run the real Praatao application against the live Praat and capture it.

This drives `run.py`'s actual Praatao class (not a mock): the same tick loop,
the same hover logic, the same panel.  It only replaces the Tk mainloop with a
bounded number of ticks so the script can end by itself.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import tkinter as tk  # noqa: E402

from praatao import paths  # noqa: E402
from praatao.sensors.uia import PraatUI  # noqa: E402

OUT = ROOT / "docs" / "screenshots"


def _cursor_pos() -> tuple[int, int]:
    from praatao.ui.overlay import cursor_pos

    return cursor_pos()


def main() -> int:
    import run as praatao_run

    app = praatao_run.Praatao(lang="zh", use_llm=False)
    print("app started, backend:", app.backend)

    # Start the first lesson, as a user would with the panel.
    if app.lessons.lessons():
        app.runner.start(app.lessons.lessons()[0].id)
    app.panel.show()
    app._refresh_panel()

    # Put the real cursor on a control that has a knowledge entry and is
    # actually visible (the editor window covers most of the Objects window).
    ui = PraatUI()
    target = None
    for name in ("Sound help", "View & Edit", "Inspect"):
        target = ui.find(name)
        if target is not None:
            break
    if target is None:
        print("no target found")
        return 1
    print("hovering over", target.name, target.rect)

    # Bring the Objects window to the front, so that the capture shows Praat
    # and not whatever was in front of it.
    objects = ui.objects_window()
    if objects is not None and ui._activate(objects):
        print("activated", objects.title)
        time.sleep(0.6)

    import ctypes

    ctypes.windll.user32.SetCursorPos(
        int((target.rect[0] + target.rect[2]) / 2),
        int((target.rect[1] + target.rect[3]) / 2),
    )

    # Run the real tick loop for a couple of seconds.
    deadline = time.time() + 4.0
    ticks = 0
    while time.time() < deadline:
        app._poll_state(time.time())
        app._drain_state()
        pos = _cursor_pos()
        el = app._element_under_cursor(*pos)
        app._handle_hover(*pos)
        if ticks % 12 == 0:
            print(f"  tick {ticks}: pos={pos} el={getattr(el, 'name', None)!r} "
                  f"key={app._last_key!r} dwell={time.monotonic() - app._hover_since:.2f} "
                  f"card_visible={app._card_visible()}")
        app.pump()
        ticks += 1
        time.sleep(0.05)
    print("ticks:", ticks)

    # Also show a lesson step.
    app.runner.step_index = 2
    app._refresh_panel()
    app.pump()
    time.sleep(0.8)
    app.pump()

    OUT.mkdir(parents=True, exist_ok=True)
    from PIL import ImageGrab

    # Let the card finish repainting: a screen grab taken in the middle of a
    # resize catches a half-drawn frame.
    time.sleep(0.5)
    for _ in range(10):
        app.pump()
        time.sleep(0.05)
    try:
        app.card.win.repaint()
        app.card.body.repaint()
        app.pump()
    except Exception as exc:
        print("repaint failed:", exc)

    path = OUT / "app-running.png"
    ImageGrab.grab(all_screens=True).save(path)
    print("saved", path)

    # The card as Qt draws it, for comparison with the screen grab.
    try:
        card_path = OUT / "card-render.png"
        app.card.win.grab().save(str(card_path))
        print("saved", card_path)
    except Exception as exc:  # pragma: no cover
        print("card grab failed:", exc)

    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
