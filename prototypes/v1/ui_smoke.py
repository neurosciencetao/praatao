"""Smoke test for the overlay UI: does the card render, is it on top, is the
spotlight transparent in the middle?  Saves a screenshot to look at."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import tkinter as tk  # noqa: E402

from praatao.ui.hover import HoverCard  # noqa: E402
from praatao.ui.spotlight import Spotlight  # noqa: E402
from praatao.ui.panel import SidePanel  # noqa: E402


def main() -> int:
    root = tk.Tk()
    root.withdraw()

    card = HoverCard(root, lang="zh")
    print("card created")
    card.show(
        "打开声音编辑器",
        "打开当前选中对象的编辑器，Praat 会显示波形与频谱图。\n\n"
        "先在 Objects 窗口里选中一个 Sound，再点这个按钮。"
        "如果按钮是灰的，说明还没有选中对象。\n\n"
        "常见坑：TextGrid 的 Annotate 按钮只有选中 TextGrid 时才出现。",
        anchor=(400, 300),
        rect=(298, 86, 533, 106),
        source="离线知识库 / offline knowledge base",
        signature=("view & edit", "打开声音编辑器"),
    )
    root.update()
    print("card geometry:", card.win.winfo_geometry(), "viewable:", card.win.winfo_viewable())

    spot = Spotlight(root)
    spot.show((298, 86, 533, 106))
    root.update()
    print("spotlight transparent:", spot.transparent)

    panel = SidePanel(root, lang="zh")
    panel.set_lessons([("01-first-sound", "你的第一个声音"), ("02-spectrogram", "看懂频谱图")])
    panel.set_lesson("你的第一个声音", "载入一个 WAV 文件\n\nPraat 需要一个文件才能开始。", (1, 3))
    panel.set_state("2 obj | sel: Sound demo_vowel")
    panel.set_answer("离线知识库命中 3 条：...")
    panel.show()
    root.update()

    time.sleep(1.5)
    root.update()

    from PIL import ImageGrab

    out = ROOT / "docs" / "screenshots"
    out.mkdir(parents=True, exist_ok=True)
    path = out / "ui-smoke.png"
    ImageGrab.grab(all_screens=True).save(path)
    print("saved", path)

    card.destroy()
    spot.destroy()
    panel.destroy()
    root.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
