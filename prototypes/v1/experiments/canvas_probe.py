"""What does UIA expose about Praat's drawing areas?"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from praatao.sensors import uia as U  # noqa: E402
from praatao.sensors.uia import PraatUI  # noqa: E402

import uiautomation as auto  # noqa: E402


def dump(control, depth=0, max_depth=8):
    if depth > max_depth:
        return
    try:
        name = U._text(control, "Name")
        ctype = U._text(control, "ControlTypeName")
        cls = U._text(control, "ClassName")
        rect = U._safe_rect(control)
    except Exception:
        return
    print(f"{'  ' * depth}[{ctype}] {name!r} cls={cls!r} rect={rect}")
    try:
        for child in control.GetChildren():
            dump(child, depth + 1, max_depth)
    except Exception:
        pass


def main() -> int:
    ui = PraatUI()
    print("=== all Praat windows ===")
    for w in ui.windows():
        print(" ", w)

    for w in ui.windows() + ui.editor_windows():
        print(f"\n=== tree of {w.title!r} ({w.kind}) ===")
        ctrl = auto.ControlFromHandle(w.hwnd)
        if ctrl is None:
            print("  (no control)")
            continue
        dump(ctrl)

    print("\n=== raw child classes of the Picture window ===")
    for w in ui.windows():
        if w.kind != "picture":
            continue
        ctrl = auto.ControlFromHandle(w.hwnd)
        for child in ctrl.GetChildren():
            print("  ", U._text(child, "ControlTypeName"), repr(U._text(child, "Name")),
                  repr(U._text(child, "ClassName")), U._safe_rect(child))
    return 0


if __name__ == "__main__":
    sys.exit(main())
