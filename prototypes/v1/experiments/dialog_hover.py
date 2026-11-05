"""Two checks the student asked for.

1. A modal dialog: the coach must explain the dialog, not the picture
   behind it.
2. Praat in the background: the coach must stop explaining and take the
   card away.
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

import run as praatao_run  # noqa: E402
from praatao.sensors.uia import PraatUI  # noqa: E402

SHOTS = ROOT / "docs" / "screenshots"


def settle(app, seconds: float) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        app.pump()
        time.sleep(0.02)


def find_dialog(title_part: str) -> int:
    found = 0

    def cb(hwnd, _extra):
        nonlocal found
        if title_part.casefold() in (win32gui.GetWindowText(hwnd) or "").casefold():
            found = int(hwnd)
        return True

    win32gui.EnumWindows(cb, None)
    return found


def main() -> int:
    ui = PraatUI()
    objects = ui.objects_window()
    if objects is None:
        print("Praat is not running")
        return 1

    app = praatao_run.Praatao(lang="zh", use_llm=False)
    app.host.after(praatao_run.MOUSE_POLL_MS, app._mouse_poll)
    app.host.after(45, app._tick)

    # -- open the Sound editor and its Formants menu --------------------
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
    editor = editors[0]

    items = []
    for _attempt in range(3):
        items = ui.open_menu(editor, "Formants", keep_open=True)
        if items:
            break
        time.sleep(0.5)
    print("Formants menu:", [i.key for i in items][:6])
    setting = next((i for i in items if i.key.startswith("Formant settings")), None)
    if setting is None:
        ui.close_popup()
        print("no Formant settings item")
        return 1
    x = (setting.rect[0] + setting.rect[2]) // 2
    y = (setting.rect[1] + setting.rect[3]) // 2
    auto.Click(x, y)
    time.sleep(2.0)

    dialog = find_dialog("Formant settings")
    print("dialog hwnd:", dialog)
    if not dialog:
        return 1
    rect = win32gui.GetWindowRect(dialog)
    print("dialog rect:", rect)

    # -- 1. hover a field of the dialog --------------------------------
    ui._activate(dialog)
    time.sleep(0.5)
    field = (rect[0] + 200, rect[1] + 55)
    ctypes.windll.user32.SetCursorPos(*field)
    settle(app, 2.5)
    print("card visible over the dialog:", app._card_visible())
    ImageGrab.grab(all_screens=True).save(str(SHOTS / "check-dialog.png"))

    # -- 2. another program in front -----------------------------------
    chrome = None

    def cb(hwnd, _extra):
        nonlocal chrome
        if win32gui.GetClassName(hwnd) == "Chrome_WidgetWin_1":
            chrome = hwnd
        return True

    win32gui.EnumWindows(cb, None)
    if chrome:
        win32gui.SetForegroundWindow(chrome)
        time.sleep(0.5)
        ctypes.windll.user32.SetCursorPos(400, 400)
        settle(app, 1.5)
        print("card visible while Praat is in the background:", app._card_visible())
        ImageGrab.grab(all_screens=True).save(str(SHOTS / "check-background.png"))

    app.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
