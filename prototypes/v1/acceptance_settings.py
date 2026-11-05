"""A picture of the Praatao settings window.

The settings window is part of the delivery, so it gets a picture of its
own next to the acceptance screenshots.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

def _root() -> Path:
    """The repository root (the directory with run.py in it)."""

    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "run.py").exists() and (parent / "praatao").is_dir():
            return parent
    raise SystemExit("the repository root was not found")


ROOT = _root()
sys.path.insert(0, str(ROOT))

from PIL import ImageGrab  # noqa: E402

import run as praatao_run  # noqa: E402


def main() -> int:
    out = ROOT / "docs" / "screenshots" / "acceptance"
    out.mkdir(parents=True, exist_ok=True)

    app = praatao_run.Praatao(lang="zh", use_llm=False, ui_backend="qt")
    app.host.after(praatao_run.MOUSE_POLL_MS, app._mouse_poll)
    app.host.after(45, app._tick)
    window = app.settings_window
    if window is None:
        print("no settings window (the Tk front-end has none)")
        app.quit()
        return 1

    window.show()
    for _ in range(20):
        app.pump()
        time.sleep(0.05)
    time.sleep(0.4)

    rect = window.win.geometry()
    left, top, right, bottom = rect.getRect()
    if right <= left or bottom <= top:
        # The window has not been laid out yet; ask Qt for its size.
        left, top = rect.x(), rect.y()
        width = rect.width() or window.win.width()
        height = rect.height() or window.win.height()
        right, bottom = left + width, top + height
    shot = ImageGrab.grab(
        bbox=(max(0, left - 10), max(0, top - 10), right + 10, bottom + 10),
        all_screens=True,
    )
    shot.save(out / "09-settings-window.png")
    print("saved 09-settings-window.png", shot.size)

    app.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
