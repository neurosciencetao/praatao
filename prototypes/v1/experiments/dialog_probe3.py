"""Open Praat's modal "Formant settings" dialog from the Sound editor.

This is what the student does: Sound editor -> Formants -> To Formant (burg)...
The dialog is modal, so the editor is blocked while it is open.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import uiautomation as auto  # noqa: E402
import win32gui  # noqa: E402

from praatao.sensors import uia as U  # noqa: E402


def describe(hwnd: int) -> str:
    return (
        f"class={win32gui.GetClassName(hwnd)!r} "
        f"title={win32gui.GetWindowText(hwnd)!r} "
        f"rect={win32gui.GetWindowRect(hwnd)}"
    )


def visible_windows() -> list[int]:
    found = []
    def cb(hwnd, _extra):
        if win32gui.IsWindowVisible(hwnd) and (win32gui.GetWindowText(hwnd) or ""):
            found.append(int(hwnd))
        return True

    win32gui.EnumWindows(cb, None)
    return found


def popup_hwnds() -> list[int]:
    found = []
    def cb(hwnd, _extra):
        if win32gui.GetClassName(hwnd) == "#32768":
            found.append(int(hwnd))
        return True

    win32gui.EnumWindows(cb, None)
    return found


def main() -> int:
    ui = U.PraatUI()
    objects = ui.objects_window()
    if objects is None:
        print("Praat is not running")
        return 1
    ui._activate(objects)
    time.sleep(0.4)

    # Open the Sound editor.
    view = ui.find("View & Edit")
    if view is not None:
        control = ui._find_control(view)
        if control is not None:
            ui._click_control(control)
        time.sleep(2.0)
    editors = ui.editor_windows()
    print("editors:", [(w.title, w.rect) for w in editors])
    if not editors:
        print("no editor window")
        return 1
    editor = editors[0]

    # Its menu bar: Formants.
    items = []
    for _attempt in range(3):
        items = ui.open_menu(editor, "Formants", keep_open=True)
        if items:
            break
        time.sleep(0.5)
    print("Formants menu:", [i.key for i in items][:8])
    if not items:
        ui.close_popup()
        return 1

    burg = next((i for i in items if i.key.startswith("Formant settings")), None)
    if burg is None:
        ui.close_popup()
        print("no Formant settings item")
        return 1
    print("clicking", burg.key)
    x = (burg.rect[0] + burg.rect[2]) // 2
    y = (burg.rect[1] + burg.rect[3]) // 2
    auto.Click(x, y)
    time.sleep(2.0)

    print("--- windows now")
    for hwnd in visible_windows():
        title = win32gui.GetWindowText(hwnd) or ""
        cls = win32gui.GetClassName(hwnd) or ""
        if "formant" in title.casefold() or "praat" in cls.casefold():
            print("   ", describe(hwnd))

    foreground = win32gui.GetForegroundWindow()
    print("foreground:", describe(foreground))
    print("praat_has_focus():", U.praat_has_focus())

    dialog = None
    for hwnd in visible_windows():
        if "Formant settings" in (win32gui.GetWindowText(hwnd) or ""):
            dialog = hwnd
    if dialog:
        rect = win32gui.GetWindowRect(dialog)
        point = (rect[0] + 200, rect[1] + 55)
        print("dialog rect:", rect, "-> hit test at", point)
        print("hit test:", ui.element_at_point(*point))
        from praatao.sensors.canvas import CanvasSensor
        canvas = CanvasSensor()
        print("canvas region under the dialog:", canvas.region_at(*point))
    else:
        print("the dialog was not found")

    return 0


if __name__ == "__main__":
    sys.exit(main())
