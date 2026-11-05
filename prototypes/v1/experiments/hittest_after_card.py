"""Does mapping the hover card break the UIA hit test on Praat?"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import tkinter as tk  # noqa: E402
import uiautomation as auto  # noqa: E402
import win32gui  # noqa: E402

from praatao.sensors.uia import PraatUI  # noqa: E402
from praatao.ui.hover import HoverCard  # noqa: E402


def probe(label):
    ui = PraatUI()
    pt = (415, 96)
    raw = auto.ControlFromPoint(*pt)
    print(f"{label}: ControlFromPoint -> {raw!r}")
    if raw is not None:
        try:
            print(f"   name={raw.Name!r} type={raw.ControlTypeName!r}")
        except Exception as exc:
            print("   (stale)", exc)
    hwnd = win32gui.WindowFromPoint(pt)
    try:
        print(f"   WindowFromPoint -> {hwnd} {win32gui.GetClassName(hwnd)!r} "
              f"{win32gui.GetWindowText(hwnd)!r}")
    except Exception as exc:
        print("   WindowFromPoint failed", exc)
    el = ui.element_at_point(*pt)
    print(f"   element_at_point -> {el.name if el else None!r}")


def main() -> int:
    probe("before card")

    root = tk.Tk()
    root.withdraw()
    card = HoverCard(root, lang="zh")
    card.show("test", "hello world", anchor=(415, 96), rect=(298, 86, 533, 106),
              signature=("a", "b"))
    root.update()
    time.sleep(0.4)
    root.update()

    probe("after card")
    print("card geometry:", card.win.winfo_geometry(),
          "rootxy:", card.win.winfo_rootx(), card.win.winfo_rooty())

    card.destroy()
    root.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
