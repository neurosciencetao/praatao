"""What colour is in each row of Praat's picture?"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import uiautomation as auto  # noqa: E402

from praatao.sensors.canvas import CanvasSensor  # noqa: E402
from praatao.sensors.uia import PraatUI  # noqa: E402


def hue_stats(image, y0: int, y1: int) -> dict[str, float]:
    import colorsys

    crop = image.crop((0, max(0, y0), image.width, min(image.height, y1)))
    small = crop.convert("RGB")
    counts = {"red": 0, "green": 0, "blue": 0, "cyan": 0, "other": 0}
    total = 0
    for r, g, b in small.getdata():
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if s < 0.25 or v < 0.25:
            continue
        total += 1
        deg = h * 360
        if deg < 20 or deg >= 330:
            counts["red"] += 1
        elif deg < 70:
            counts["green"] += 1
        elif deg < 200:
            counts["blue"] += 1
        elif deg < 260:
            counts["cyan"] += 1
        else:
            counts["other"] += 1
    if not total:
        return {k: 0.0 for k in counts}
    return {k: v / total for k, v in counts.items()}


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
    for menu, item in (
        ("Pitch", "Show pitch"),
        ("Formants", "Show formants"),
        ("Intensity", "Show intensity"),
    ):
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
    image = sensor.capture(region)
    if image is None:
        print("no picture")
        return 1
    print("picture size:", image.size)
    height = image.height
    step = max(20, height // 12)
    for top_y in range(0, height, step):
        stats = hue_stats(image, top_y, top_y + step)
        top = ", ".join(
            f"{k} {v:.2f}" for k, v in sorted(stats.items(), key=lambda p: -p[1])[:3]
        )
        print(f"  y {top_y:4d}-{top_y + step:4d}   {top}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
