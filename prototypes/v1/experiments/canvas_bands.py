"""What does each row of the picture hold, at full resolution?

The numbers decide the thresholds of ``classify_at``.
"""

from __future__ import annotations

import colorsys
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import uiautomation as auto  # noqa: E402
from PIL import ImageGrab  # noqa: E402

from praatao.sensors.canvas import CanvasSensor  # noqa: E402
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
    ui._activate(editor)
    time.sleep(0.6)
    shot = ImageGrab.grab(bbox=region.rect, all_screens=True)
    print("picture size:", shot.size)

    width, height = shot.size
    band = max(6, int(height * 0.07))
    for centre in range(band, height - band, band):
        crop = shot.crop((0, centre - band, width, centre + band)).convert("RGB")
        total = 0
        dark = 0
        hues = {"red": 0, "green": 0, "blue": 0, "teal": 0}
        right_half = {"red": 0, "green": 0, "blue": 0, "teal": 0}
        for index, (r, g, b) in enumerate(crop.getdata()):
            total += 1
            level = (r + g + b) / 3.0
            if level < 90:
                dark += 1
            h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
            if s > 0.3 and v > 0.3:
                deg = h * 360.0
                if deg < 20 or deg >= 330:
                    key = "red"
                elif deg < 160:
                    key = "green"
                elif deg < 200:
                    key = "teal"
                else:
                    key = "blue"
                hues[key] += 1
                if index % width > int(width * 0.75):
                    right_half[key] += 1
        coloured = sum(hues.values())
        share = {k: round(v / max(1, total), 4) for k, v in hues.items()}
        right_share = {k: round(v / max(1, total), 4) for k, v in right_half.items()}
        print(
            f"  y {centre - band:4d}-{centre + band:4d}"
            f"  dark {dark / max(1, total):.3f}"
            f"  coloured {coloured / max(1, total):.4f}"
            f"  all {share}"
            f"  right {right_share}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
