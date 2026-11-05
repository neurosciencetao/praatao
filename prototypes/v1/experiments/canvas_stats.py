"""Statistics of Praat's real drawing areas, to design a local classifier."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import uiautomation as auto  # noqa: E402
from PIL import Image, ImageGrab  # noqa: E402

from praatao.sensors import uia as U  # noqa: E402
from praatao.sensors.uia import PraatUI  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "docs" / "screenshots"


def describe(image: Image.Image, tag: str) -> None:
    small = image.convert("RGB").resize((160, 90))
    pixels = list(small.getdata())
    total = len(pixels)
    grey = [p for p in pixels if abs(p[0] - p[1]) < 18 and abs(p[1] - p[2]) < 18]
    coloured = [p for p in pixels if not (abs(p[0] - p[1]) < 18 and abs(p[1] - p[2]) < 18)]
    dark = [p for p in pixels if sum(p) / 3 < 90]
    bright = [p for p in pixels if sum(p) / 3 > 200]
    mid = [p for p in pixels if 90 <= sum(p) / 3 <= 200]
    print(f"\n[{tag}] {image.size}")
    print(f"   grey {len(grey)/total:.0%}  coloured {len(coloured)/total:.0%}  "
          f"dark {len(dark)/total:.0%}  mid {len(mid)/total:.0%}  bright {len(bright)/total:.0%}")
    if coloured:
        print(f"   mean colour of coloured pixels: "
              f"{tuple(round(sum(c[i] for c in coloured)/len(coloured)) for i in range(3))}")
    # row profile of "ink" (non-background) per row, 12 buckets
    h = small.height
    rows = []
    for y in range(h):
        row = [small.getpixel((x, y)) for x in range(small.width)]
        ink = sum(1 for p in row if sum(p) / 3 < 170) / small.width
        rows.append(ink)
    buckets = []
    for b in range(12):
        chunk = rows[b * h // 12:(b + 1) * h // 12]
        buckets.append(round(sum(chunk) / max(1, len(chunk)), 2))
    print(f"   ink per row band (top->bottom): {buckets}")


def main() -> int:
    ui = PraatUI()
    OUT.mkdir(parents=True, exist_ok=True)
    for w in ui.windows() + ui.editor_windows():
        ctrl = auto.ControlFromHandle(w.hwnd)
        if ctrl is None:
            continue
        for node, _d in ui._iter_controls(ctrl, max_depth=6):
            if U._text(node, "ClassName") == "PraatDrawingArea1 Praat":
                rect = U._safe_rect(node)
                if not rect:
                    continue
                # The capture reads the *screen*, so an occluded window
                # gives the picture of whatever is in front of it.  Bring
                # Praat to the front first.
                ui._activate(w)
                time.sleep(0.5)
                shot = ImageGrab.grab(bbox=rect, all_screens=True)
                name = (w.title or "canvas").replace(" ", "_")
                path = OUT / f"canvas-{name}.png"
                shot.save(path)
                print(f"saved {path}")
                describe(shot, f"{w.title} [{w.kind}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
