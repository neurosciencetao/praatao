"""Compare the card's layout in the app and in isolation."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from PySide6 import QtWidgets  # noqa: E402


def dump(tag: str, card) -> None:
    body = card.body
    doc = body.document()
    layout = doc.documentLayout()
    block = doc.firstBlock()
    print(f"--- {tag} ---")
    print("  window     :", card.win.size(), "body pos:", body.pos())
    print("  body       :", body.size(), "viewport:", body.viewport().size())
    print("  doc size   :", doc.size(), "scroll:", body.verticalScrollBar().value(),
          "max:", body.verticalScrollBar().maximum())
    print("  doc margin :", doc.documentMargin())
    print("  layout size:", layout.documentSize())
    if block is not None:
        print("  block rect :", layout.blockBoundingRect(block))
        it = doc.begin()
        rows = []
        while it.isValid() and len(rows) < 4:
            rows.append((it.text()[:18], layout.blockBoundingRect(it)))
            it = it.next()
        print("  blocks     :", rows)
    print("  html head  :", doc.toPlainText()[:60].replace("\n", " | "))


def main() -> int:
    from praatao.ui.qt.hover import QtHoverCard

    BODY = """这是什么：Praat 的 Objects 窗口会列出你所有的物件，按类型分组，每一行是一个物件。看见它们被取出来做成新物件，你就能明白 Praat 的设计。

怎么用：Sound → Extract selected sound (preserve times) 会把选区放进清单。
"""

    app = QtWidgets.QApplication([])
    card = QtHoverCard(None, lang="zh")
    card.show("Sound 菜单", BODY, anchor=(300, 300), rect=(300, 300, 500, 330),
              source="离线知识库 / offline knowledge base", signature=("k", "s"))
    for _ in range(20):
        app.processEvents()
        time.sleep(0.02)
    dump("standalone", card)

    # Now the same card inside a real application.
    import run as praatao_run

    app2 = praatao_run.Praatao(lang="zh", use_llm=False)
    app2.card.show("Sound 菜单", BODY, anchor=(300, 300), rect=(300, 300, 500, 330),
                   source="离线知识库 / offline knowledge base", signature=("k", "s"))
    for _ in range(20):
        app2.pump()
        time.sleep(0.02)
    dump("in app", app2.card)
    app2.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
