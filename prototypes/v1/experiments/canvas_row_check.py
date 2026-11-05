"""Does the coach now explain the row under the pointer?

The sound editor is opened with a waveform, a pitch curve and the
formants on top of each other.  The pointer is put on the waveform and
on the pitch curve, and the card is read.
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

from praatao.sensors.canvas import CanvasSensor  # noqa: E402
from praatao.sensors.uia import PraatUI  # noqa: E402


def classify_at(sensor: CanvasSensor, region, x: int, y: int) -> str:
    _image, guess = sensor.capture_and_classify(region, x, y)
    return guess.kind


def main() -> int:
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
            x = (target.rect[0] + target.rect[2]) // 2
            y = (target.rect[1] + target.rect[3]) // 2
            auto.Click(x, y)
        ui.close_popup()
        time.sleep(1.0)

    sensor = CanvasSensor()
    left, top, right, bottom = editor.rect
    region = sensor.region_at((left + right) // 2, (top + bottom) // 2)
    if region is None:
        print("no canvas region")
        return 1
    print("picture:", region.rect)
    # The grab reads the screen, so the editor has to be in front.
    ui._activate(editor)
    time.sleep(0.6)
    print("visible:", sensor.is_visible(region))

    height = region.rect[3] - region.rect[1]
    for label, fraction in (
        ("top (the waveform)", 0.2),
        ("middle (the formants)", 0.55),
        ("the pitch curve", 0.78),
        ("bottom (the axis)", 0.95),
    ):
        y = region.rect[1] + int(height * fraction)
        x = (region.rect[0] + region.rect[2]) // 2
        print(f"  {label:28s} y={y:5d} -> {classify_at(sensor, region, x, y)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
