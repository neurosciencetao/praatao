"""Render the Qt hover card on its own, to check its layout."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from PySide6 import QtCore, QtWidgets  # noqa: E402

from praatao.ui.qt.hover import QtHoverCard  # noqa: E402

BODY = """这是什么：Praat 的 Objects 窗口会列出你所有的物件，按类型分组，每一行是一个物件。看见它们被取出来做成新物件，你就能明白 Praat 的设计。

怎么用：Sound → Extract selected sound (preserve times) 会把选区放进清单；Sound → Get amplitude(s) 则报告选区的峰值。

概念：用 preserve times 取出选区会保留原本的绝对时间轴，当量测结果要对齐整段录音来播音时就要用这个。

常见坑：
• Extract selected sound (time from 0) 让新物件从 0 开始，所有时间参照都会平移。
• Reverse selection(Ctrl-R) 只反转选区，不是整段声音。
"""

OUT = ROOT / "docs" / "screenshots" / "card-only.png"


def main() -> int:
    app = QtWidgets.QApplication([])
    card = QtHoverCard(None, lang="zh")
    card.show("Sound 菜单", BODY,
              anchor=(300, 300), rect=(300, 300, 500, 330),
              source="离线知识库 / offline knowledge base",
              signature=("k", "s"))
    for _ in range(20):
        app.processEvents()
        time.sleep(0.02)
    print("card size:", card.win.size())
    print("body size:", card.body.size(),
          "viewport:", card.body.viewport().size())
    doc = card.body.document()
    print("document size:", doc.size(), "scroll:", card.body.verticalScrollBar().value(),
          "max:", card.body.verticalScrollBar().maximum())
    print("geometry:", card.geometry())
    card.win.grab().save(str(OUT))
    print("saved", OUT)

    # Now grab the same region from the *screen*: for a layered window the
    # two can disagree, and that is what the documentation screenshots show.
    from PIL import ImageGrab

    left, top, right, bottom = card.geometry()
    screen = ImageGrab.grab(bbox=(left, top, right, bottom), all_screens=True)
    screen_path = OUT.with_name("card-screen.png")
    screen.save(screen_path)
    print("saved", screen_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
