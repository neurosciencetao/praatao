"""Exploration: dump the live UIA structure of the Praat windows.

Read-only probe used while designing praatao.sensors.uia.
Run:  python prototypes/v1/experiments/uia_explore.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import uiautomation as auto
import win32gui

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def top_windows():
    out = []

    def cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            cls = win32gui.GetClassName(hwnd)
            title = win32gui.GetWindowText(hwnd)
            if "praat" in cls.lower():
                out.append((hwnd, cls, title))

    win32gui.EnumWindows(cb, None)
    return out


def walk(ctrl, max_depth=10, max_nodes=600):
    stack = [(ctrl, 0)]
    seen = 0
    while stack and seen < max_nodes:
        node, d = stack.pop(0)
        seen += 1
        try:
            name = node.Name
        except Exception:
            name = None
        try:
            ctype = node.ControlTypeName
        except Exception:
            ctype = "?"
        try:
            r = node.BoundingRectangle
            rect = (r.left, r.top, r.right, r.bottom)
        except Exception:
            rect = None
        try:
            hwnd = node.NativeWindowHandle
        except Exception:
            hwnd = 0
        try:
            cls = node.ClassName
        except Exception:
            cls = ""
        try:
            aid = node.AutomationId
        except Exception:
            aid = ""
        yield node, d, name, ctype, rect, hwnd, cls, aid
        if d < max_depth:
            try:
                kids = node.GetChildren()
            except Exception:
                kids = []
            for k in kids:
                stack.append((k, d + 1))


def main():
    print("== top-level Praat windows ==")
    tops = top_windows()
    for hwnd, cls, title in tops:
        print(f"   hwnd={hwnd} class={cls!r} title={title!r}")
    if not tops:
        print("   NONE")
        return 1

    obj = next((t for t in tops if t[2] == "Praat Objects"), None)
    if obj is None:
        print("no objects window")
        return 1
    obj_hwnd = obj[0]
    ctrl = auto.ControlFromHandle(obj_hwnd)

    print("\n== Objects window tree (named nodes only) ==")
    for node, d, name, ctype, rect, hwnd, cls, aid in walk(ctrl):
        if name:
            print(f"   d={d} [{ctype}] {name!r} rect={rect} hwnd={hwnd} cls={cls!r} aid={aid!r}")

    print("\n== Objects window tree (ALL nodes, shallow) ==")
    for node, d, name, ctype, rect, hwnd, cls, aid in walk(ctrl, max_depth=3):
        print(f"   d={d} [{ctype}] name={name!r} cls={cls!r} aid={aid!r} rect={rect}")

    print("\n== ControlFromPoint over the list area ==")
    # The object list is a ListItemControl named '1. Sound demo_vowel'.
    list_items = []
    for node, d, name, ctype, rect, hwnd, cls, aid in walk(ctrl):
        if ctype == "ListItemControl" and name:
            list_items.append((name, rect))
    print("   list items:", list_items)
    for name, rect in list_items:
        if not rect:
            continue
        cx = (rect[0] + rect[2]) // 2
        cy = (rect[1] + rect[3]) // 2
        try:
            el = auto.ControlFromPoint(cx, cy)
            print(f"   point({cx},{cy}) -> [{el.ControlTypeName}] {el.Name!r}")
            # parent chain
            p = el.GetParentControl()
            chain = []
            while p is not None and len(chain) < 8:
                chain.append((p.ControlTypeName, p.Name))
                p = p.GetParentControl()
            print("        parents:", chain)
        except Exception as exc:
            print(f"   point({cx},{cy}) -> ERROR {exc}")

    print("\n== open the 'Open' menu ==")
    menu_item = None
    for node, d, name, ctype, rect, hwnd, cls, aid in walk(ctrl):
        if ctype == "MenuItemControl" and name == "Open":
            menu_item = node
            break
    if menu_item is None:
        print("   'Open' menu item not found")
    else:
        print("   clicking 'Open'")
        try:
            menu_item.Click(simulateMove=False)
        except Exception as exc:
            print("   click failed:", exc)
        time.sleep(1.0)
        print("   windows now:")
        for hwnd, cls, title in top_windows():
            print(f"      hwnd={hwnd} class={cls!r} title={title!r}")
        print("   full enum of visible windows while popup open:")
        allw = []

        def cb2(h, _):
            if win32gui.IsWindowVisible(h):
                allw.append((h, win32gui.GetClassName(h), win32gui.GetWindowText(h)))

        win32gui.EnumWindows(cb2, None)
        for h, c, t in allw:
            print(f"      hwnd={h} class={c!r} title={t!r}")

        print("   objects-window tree with popup open:")
        ctrl2 = auto.ControlFromHandle(obj_hwnd)
        for node, d, name, ctype, rect, hwnd, cls, aid in walk(ctrl2, max_depth=8):
            if name:
                print(f"      d={d} [{ctype}] {name!r} rect={rect} hwnd={hwnd}")

        print("   hit test over a popup item:")
        for node, d, name, ctype, rect, hwnd, cls, aid in walk(ctrl2, max_depth=8):
            if ctype == "MenuItemControl" and name and "Read from file" in name and rect:
                cx = (rect[0] + rect[2]) // 2
                cy = (rect[1] + rect[3]) // 2
                try:
                    el = auto.ControlFromPoint(cx, cy)
                    print(f"      point({cx},{cy}) -> [{el.ControlTypeName}] {el.Name!r}")
                except Exception as exc:
                    print("      hit test error:", exc)
                break

        print("   closing popup with ESC")
        auto.SendKeys("{ESC}")
        time.sleep(0.5)

    return 0


if __name__ == "__main__":
    sys.exit(main())
