"""What does the card say when the pointer is on the waveform?

The card's title is read from the screen: the coach puts it on top of
the picture.
"""

from __future__ import annotations

import ctypes
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import uiautomation as auto  # noqa: E402
import win32gui  # noqa: E402
from PIL import ImageGrab  # noqa: E402

from praatao.sensors.canvas import CanvasSensor  # noqa: E402
from praatao.sensors.uia import PraatUI  # noqa: E402

PACKAGED = ROOT / "dist" / "Praatao" / "Praatao.exe"


def main() -> int:
    import os

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    coach = subprocess.Popen([str(PACKAGED)], cwd=str(PACKAGED.parent), env=env)
    time.sleep(9.0)

    ui = PraatUI()
    objects = ui.objects_window()
    if objects is None:
        print("Praat is not running")
        return 1
    ui._activate(objects)
    time.sleep(0.4)
    view = ui.find("View & Edit")
    control = ui._find_control(view) if view is not None else None
    if control is not None:
        ui._click_control(control)
    time.sleep(2.5)
    editors = ui.editor_windows()
    if not editors:
        print("no editor")
        return 1
    editor = editors[0]
    for menu, item in (("Pitch", "Show pitch"), ("Formants", "Show formants")):
        for _attempt in range(3):
            items = ui.open_menu(editor, menu, keep_open=True)
            if items:
                break
            time.sleep(0.4)
        target = next((i for i in items if i.key.startswith(item)), None)
        if target is not None:
            auto.Click((target.rect[0] + target.rect[2]) // 2,
                       (target.rect[1] + target.rect[3]) // 2)
        ui.close_popup()
        time.sleep(1.0)

    sensor = CanvasSensor()
    left, top, right, bottom = editor.rect
    region = sensor.region_at((left + right) // 2, (top + bottom) // 2)
    if region is None:
        print("no canvas region")
        return 1
    height = region.rect[3] - region.rect[1]
    x = (region.rect[0] + region.rect[2]) // 2

    for label, fraction in (("the waveform", 0.2), ("the formants", 0.55),
                            ("the pitch curve", 0.78)):
        y = region.rect[1] + int(height * fraction)
        ctypes.windll.user32.SetCursorPos(x, y)
        time.sleep(0.4)
        ctypes.windll.user32.SetCursorPos(x + 3, y + 1)
        time.sleep(2.2)
        print(f"  {label:18s} -> {read_card_title()}")
    ImageGrab.grab(all_screens=True).save(
        str(ROOT / "docs/screenshots/canvas-card.png")
    )
    coach.terminate()
    return 0


def read_card_title() -> str:
    for control in auto.GetRootControl().GetChildren():
        try:
            if control.Name != "Praatao 讲解卡":
                continue
        except Exception:
            continue
        for node, _depth in auto.WalkControl(control, maxDepth=3):
            try:
                if node.ControlTypeName == "TextControl" and node.Name:
                    return node.Name
            except Exception:
                continue
    return "(no card)"


if __name__ == "__main__":
    sys.exit(main())
