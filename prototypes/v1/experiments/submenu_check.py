"""Does a submenu survive while the coach is running?

The coach's state probe sends a Praat script every few seconds, and a
script closes every menu that is open.  A submenu is owned by the menu
above it, so it has to be recognised as a Praat menu as well.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import uiautomation as auto  # noqa: E402

from praatao.sensors.praat_state import PraatStateProbe  # noqa: E402
from praatao.sensors.uia import PraatUI, _menu_popup_open  # noqa: E402

PACKAGED = ROOT / "dist" / "Praatao" / "Praatao.exe"
WAIT = 22.0


def popup_count() -> int:
    from praatao.sensors.uia import _menu_popup_windows, _praat_owned_popup

    return sum(1 for h in _menu_popup_windows() if _praat_owned_popup(h))


def main() -> int:
    import os

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"

    probe = PraatStateProbe()
    if not probe.fast().objects:
        probe.send("prototypes/v0/probes/load_demo.praat", timeout=10.0)
        time.sleep(1.5)

    coach = subprocess.Popen([str(PACKAGED)], cwd=str(PACKAGED.parent), env=env)
    time.sleep(9.0)

    ui = PraatUI()
    objects = ui.objects_window()
    ui._activate(objects)
    time.sleep(0.5)
    view = ui.find("View & Edit")
    control = ui._find_control(view) if view is not None else None
    if control is not None:
        ui._click_control(control)
    time.sleep(2.5)
    editors = ui.editor_windows()
    if not editors:
        print("no editor")
        coach.terminate()
        return 1
    editor = editors[0]

    # Open a dropdown from the menu bar and hang the pointer over it.
    items = []
    for _attempt in range(3):
        items = ui.open_menu(editor, "Sound", keep_open=True)
        if items:
            break
        time.sleep(0.4)
    if not items:
        print("no menu")
        coach.terminate()
        return 1
    print("the dropdown items:", [i.key for i in items][:5])
    import ctypes

    # Open the submenu of the item with the little arrow.
    sub = next((i for i in items if i.key.startswith("▼")), None)
    if sub is not None:
        x = (sub.rect[0] + sub.rect[2]) // 2
        y = (sub.rect[1] + sub.rect[3]) // 2
        auto.Click(x, y)
        time.sleep(1.2)
    first = items[0]
    x = (first.rect[0] + first.rect[2]) // 2
    y = (first.rect[1] + first.rect[3]) // 2
    ctypes.windll.user32.SetCursorPos(x + 2, y + 2)
    time.sleep(1.0)

    print("popups right after the submenu opened:", popup_count())
    from praatao.sensors.uia import _menu_popup_windows, _praat_owned_popup

    for h in _menu_popup_windows():
        print("   popup", h, "belongs to Praat:", _praat_owned_popup(h))
    print("the coach sees a menu:", _menu_popup_open())
    deadline = time.time() + WAIT
    closed_at = None
    while time.time() < deadline:
        time.sleep(0.5)
        if popup_count() == 0:
            closed_at = WAIT - (deadline - time.time())
            break
    if closed_at is None:
        print(f"the submenu was still open after {WAIT:.0f} s")
    else:
        print(f"the submenu closed after {closed_at:.1f} s")
    coach.terminate()
    return 0 if closed_at is None else 1


if __name__ == "__main__":
    sys.exit(main())
