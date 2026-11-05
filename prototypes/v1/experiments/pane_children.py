"""What is inside the pane that UIA reports under the cursor?"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import uiautomation as auto  # noqa: E402


def walk(node, depth=0, max_depth=4):
    yield node, depth
    if depth < max_depth:
        try:
            kids = node.GetChildren()
        except Exception:
            kids = []
        for k in kids:
            yield from walk(k, depth + 1, max_depth)


def main() -> int:
    ctrl = auto.ControlFromPoint(415, 96)
    print("hit:", ctrl.ControlTypeName, repr(ctrl.Name), ctrl.BoundingRectangle)
    print("children of the hit element:")
    for node, d in walk(ctrl, max_depth=4):
        try:
            r = node.BoundingRectangle
            rect = (r.left, r.top, r.right, r.bottom)
        except Exception:
            rect = None
        print(f"  {'  ' * d}[{node.ControlTypeName}] {node.Name!r} {rect}")

    # Also: find the button in the Objects window and check its UIA parent.
    win = auto.ControlFromHandle(3738320)
    for node, d in walk(win, max_depth=4):
        try:
            if node.Name == "View & Edit":
                print("\n'View & Edit' found at depth", d, node.BoundingRectangle)
                try:
                    parent = node.GetParentControl()
                    print("   UIA parent:", parent.ControlTypeName, repr(parent.Name),
                          parent.BoundingRectangle)
                except Exception as exc:
                    print("   no parent:", exc)
                break
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
