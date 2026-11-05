"""Can the picture under the pointer be told apart row by row?

Praat's sound editor stacks several pictures (the waveform, the
spectrogram, the pitch curve...).  The coach classifies the whole
picture, so a pointer on the waveform can be told "this looks like a
pitch curve".  This script measures a narrow band around the pointer
and prints the numbers, to see whether the bands separate.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import uiautomation as auto  # noqa: E402

from praatao.sensors.canvas import CanvasSensor  # noqa: E402
from praatao.sensors.uia import PraatUI  # noqa: E402


def band_stats(image, y0: int, y1: int) -> dict[str, float]:
    crop = image.crop((0, max(0, y0), image.width, min(image.height, y1)))
    small = crop.convert("RGB").resize((160, 40))
    pixels = list(small.getdata())
    total = max(1, len(pixels))
    coloured = dark = bright = 0
    for r, g, b in pixels:
        if abs(r - g) > 22 or abs(g - b) > 22:
            coloured += 1
        level = (r + g + b) / 3.0
        if level < 90:
            dark += 1
        elif level > 200:
            bright += 1
    return {
        "coloured": coloured / total,
        "dark": dark / total,
        "bright": bright / total,
    }


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
    region = sensor.region_at(*_centre_of(editor))
    if region is None:
        print("no canvas region")
        return 1
    image = sensor.capture(region)
    if image is None:
        print("no picture")
        return 1
    print("picture size:", image.size)
    whole = sensor.classify(image)
    print("whole picture:", whole.kind, whole.confidence)
    height = image.height
    step = max(20, height // 12)
    for top in range(0, height, step):
        stats = band_stats(image, top, top + step)
        print(
            f"  y {top:4d}-{top + step:4d}"
            f"  coloured {stats['coloured']:.3f}"
            f"  dark {stats['dark']:.3f}"
            f"  bright {stats['bright']:.3f}"
        )
    return 0


def _centre_of(window) -> tuple[int, int]:
    left, top, right, bottom = window.rect
    return ((left + right) // 2, (top + bottom) // 2)


if __name__ == "__main__":
    sys.exit(main())
