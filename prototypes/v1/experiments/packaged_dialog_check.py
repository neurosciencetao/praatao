"""Open the Formant settings dialog and let the *running* coach explain it.

No coach is started here: the packaged program is already running and
does the work on its own.  The screenshot shows what the student sees.
"""

from __future__ import annotations

import ctypes
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import uiautomation as auto  # noqa: E402
import win32gui  # noqa: E402
from PIL import ImageGrab  # noqa: E402

from praatao.sensors.uia import PraatUI  # noqa: E402


def main() -> int:
    ui = PraatUI()
    objects = ui.objects_window()
    if objects is None:
        print("Praat is not running")
        return 1

    ui._activate(objects)
    time.sleep(0.4)
    view = ui.find("View & Edit")
    if view is not None:
        control = ui._find_control(view)
        if control is not None:
            ui._click_control(control)
        time.sleep(2.0)
    editors = ui.editor_windows()
    if not editors:
        print("no editor")
        return 1

    items = []
    for _attempt in range(3):
        items = ui.open_menu(editors[0], "Formants", keep_open=True)
        if items:
            break
        time.sleep(0.5)
    setting = next((i for i in items if i.key.startswith("Formant settings")), None)
    if setting is None:
        ui.close_popup()
        print("no Formant settings item")
        return 1
    x = (setting.rect[0] + setting.rect[2]) // 2
    y = (setting.rect[1] + setting.rect[3]) // 2
    auto.Click(x, y)
    time.sleep(2.0)

    dialog = 0

    def cb(hwnd, _extra):
        nonlocal dialog
        if (win32gui.GetWindowText(hwnd) or "") == "Formant settings":
            dialog = int(hwnd)
        return True

    win32gui.EnumWindows(cb, None)
    if not dialog:
        print("no dialog")
        return 1
    rect = win32gui.GetWindowRect(dialog)
    field = (rect[0] + 200, rect[1] + 55)
    ctypes.windll.user32.SetCursorPos(*field)
    time.sleep(3.0)
    ImageGrab.grab(all_screens=True).save(
        str(ROOT / "docs/screenshots/dialog-01-formant-settings.png")
    )
    print("screenshot written; the pointer sat at", field)
    return 0


if __name__ == "__main__":
    sys.exit(main())
