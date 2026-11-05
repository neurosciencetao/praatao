"""Why is the hover card invisible?  Check mapping, geometry and ex-styles."""

from __future__ import annotations

import ctypes
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import tkinter as tk  # noqa: E402

from praatao.ui.hover import HoverCard  # noqa: E402
from praatao.ui.overlay import hwnd_of  # noqa: E402
from praatao.ui.spotlight import Spotlight  # noqa: E402

user32 = ctypes.windll.user32


def styles(widget, label):
    hwnd = hwnd_of(widget)
    ex = user32.GetWindowLongW(hwnd, -20)
    print(f"  {label}: hwnd={hwnd} exstyle=0x{ex:08x} "
          f"layered={bool(ex & 0x80000)} transparent={bool(ex & 0x20)} "
          f"noactivate={bool(ex & 0x08000000)}")
    print(f"      viewable={widget.winfo_viewable()} ismapped={widget.winfo_ismapped()} "
          f"geom={widget.winfo_geometry()} rootxy={widget.winfo_rootx()},{widget.winfo_rooty()}")


def main() -> int:
    # clear any leftover Praat modal dialog first
    try:
        from praatao.sensors.praat_state import PraatStateProbe
        PraatStateProbe().dismiss_dialogs()
    except Exception as exc:
        print("dismiss failed:", exc)

    root = tk.Tk()
    root.withdraw()

    card = HoverCard(root, lang="zh")
    print("after create:")
    styles(card.win, "card")

    card.show(
        "打开声音编辑器",
        "打开当前选中对象的编辑器，Praat 会显示波形与频谱图。\n\n"
        "先在 Objects 窗口里选中一个 Sound，再点这个按钮。",
        anchor=(400, 300), rect=(298, 86, 533, 106),
        source="离线知识库 / offline knowledge base",
        signature=("x", "y"),
    )
    root.update()
    time.sleep(0.4)
    root.update()
    print("after show:")
    styles(card.win, "card")

    spot = Spotlight(root)
    spot.show((298, 86, 533, 106))
    root.update()
    time.sleep(0.3)
    root.update()
    print("after spotlight:")
    styles(spot.win, "spotlight")
    styles(spot.canvas, "spotlight-canvas")

    from PIL import ImageGrab

    out = ROOT / "docs" / "screenshots"
    out.mkdir(parents=True, exist_ok=True)
    img = ImageGrab.grab(all_screens=True)
    img.save(out / "ui-debug.png")
    # Crop the area where the card should be.
    img.crop((250, 0, 850, 300)).save(out / "ui-debug-crop.png")
    print("saved", out / "ui-debug.png")

    card.destroy()
    spot.destroy()
    root.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
