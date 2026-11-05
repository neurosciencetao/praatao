"""Why does the pin button not react to a click?"""

from __future__ import annotations

import ctypes
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

user32 = ctypes.windll.user32


def main() -> int:
    from PySide6 import QtWidgets

    import run as praatao_run

    app = praatao_run.Praatao(lang="zh", use_llm=False)
    card = app.card
    card.pin_button.clicked.connect(lambda: print("  >> clicked signal fired"))
    card.pin_button.pressed.connect(lambda: print("  >> pressed signal fired"))
    card.pin_button.released.connect(lambda: print("  >> released signal fired"))

    card.show("测试标题", "这是什么：测试内容。",
              anchor=(200, 200), rect=(200, 200, 320, 240),
              source="测试", signature=("k", "s"))
    app._current_rect = (200, 200, 320, 240)
    app.pump()

    centre = card.pin_button.rect().center()
    gx, gy = card.pin_button.mapToGlobal(centre).x(), card.pin_button.mapToGlobal(centre).y()
    print("pin button global:", gx, gy)
    print("button visible   :", card.pin_button.isVisible(),
          "enabled:", card.pin_button.isEnabled())

    hwnd = int(card.win.winId())
    print("card hwnd        :", hwnd)
    print("window at point  :", user32.WindowFromPoint.__call__ and 0)
    import win32gui

    at = win32gui.WindowFromPoint((gx, gy))
    print("WindowFromPoint  :", at, win32gui.GetClassName(at) if at else None,
          "== card hwnd:", at == hwnd)

    user32.SetCursorPos(gx, gy)
    app.pump()
    time.sleep(0.2)

    from PySide6 import QtCore

    class Spy(QtCore.QObject):
        def eventFilter(self, obj, event):
            if event.type() in (
                QtCore.QEvent.Type.MouseButtonPress,
                QtCore.QEvent.Type.MouseButtonRelease,
            ):
                print(f"  event {event.type().name} on {type(obj).__name__}")
            return False

    spy = Spy()
    card.win.installEventFilter(spy)
    card.pin_button.installEventFilter(spy)

    user32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.05)
    user32.mouse_event(0x0004, 0, 0, 0, 0)
    time.sleep(0.3)
    app.pump()

    print("pinned:", card.pinned)
    app.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
