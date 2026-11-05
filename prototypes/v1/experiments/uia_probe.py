"""Experiment: can Windows UI Automation see Praat's controls by name?

Run with Praat running (or it will be launched by the caller).
Dumps the UIA tree of every top-level Praat window, then hit-tests a point.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import uiautomation as auto

ROOT = Path(__file__).resolve().parents[3]
PRAAT = ROOT / "Praat.exe"


def dump_tree(control, max_depth=6, max_nodes=400):
    """Walk the UIA tree, returning flat records."""
    out = []
    stack = [(control, 0)]
    seen = 0
    while stack and seen < max_nodes:
        node, depth = stack.pop(0)
        seen += 1
        try:
            rect = node.BoundingRectangle
            rect_t = (rect.left, rect.top, rect.right, rect.bottom)
        except Exception:
            rect_t = None
        try:
            name = node.Name
        except Exception:
            name = None
        try:
            ctype = node.ControlTypeName
        except Exception:
            ctype = None
        try:
            aid = node.AutomationId
        except Exception:
            aid = None
        try:
            hwnd = node.NativeWindowHandle
        except Exception:
            hwnd = 0
        out.append(
            {
                "depth": depth,
                "type": ctype,
                "name": name,
                "automation_id": aid,
                "hwnd": hwnd,
                "rect": rect_t,
                "offscreen": bool(getattr(node, "IsOffscreen", False)),
            }
        )
        if depth < max_depth:
            try:
                children = node.GetChildren()
            except Exception:
                children = []
            for c in reversed(children):
                stack.insert(0, (c, depth + 1))
    return out


def main() -> int:
    import win32gui
    import win32process

    # Locate Praat top-level windows.
    tops = []

    def cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
        except Exception:
            pid = 0
        cls = win32gui.GetClassName(hwnd)
        tops.append({"hwnd": hwnd, "title": title, "class": cls, "pid": pid})

    win32gui.EnumWindows(cb, None)
    praat_tops = [t for t in tops if "praat" in t["title"].lower()]
    print("== top-level windows ==")
    for t in tops:
        print("  ", t)

    if not praat_tops:
        print("NO PRAAT WINDOW FOUND")
        return 1

    report = {"tops": tops, "trees": {}}
    for t in praat_tops:
        print(f"\n== tree for hwnd={t['hwnd']} class={t['class']} title={t['title']!r} ==")
        try:
            ctrl = auto.ControlFromHandle(t["hwnd"])
        except Exception as exc:
            print("   ControlFromHandle failed:", exc)
            continue
        recs = dump_tree(ctrl)
        report["trees"][str(t["hwnd"])] = recs
        for r in recs:
            if r["name"] or (r["type"] not in ("Pane", "Custom", "Group", "Window", "ToolBar", "TitleBar")):
                print(
                    f"   {'  ' * r['depth']}[{r['type']}] name={r['name']!r} "
                    f"aid={r['automation_id']!r} hwnd={r['hwnd']} rect={r['rect']}"
                )

    # Hit test at the centre of the Objects window.
    for t in praat_tops:
        if "objects" not in t["title"].lower():
            continue
        rect = win32gui.GetWindowRect(t["hwnd"])
        cx = (rect[0] + rect[2]) // 2
        cy = (rect[1] + rect[3]) // 2
        print(f"\n== hit test at ({cx},{cy}) ==")
        try:
            el = auto.ControlFromPoint(cx, cy)
            print("   ->", el.ControlTypeName, repr(el.Name), el.BoundingRectangle)
        except Exception as exc:
            print("   hit test failed:", exc)

    out = Path(__file__).resolve().parent / "uia_probe_output.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
