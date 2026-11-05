"""Diagnostic 4: recursion-based tree walk, menu popup contents, View & Edit click."""

from __future__ import annotations

import sys
import time

import uiautomation as auto
import win32gui


def tops():
    out = []

    def cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            t = win32gui.GetWindowText(hwnd)
            c = win32gui.GetClassName(hwnd)
            if "praat" in t.lower() or "praat" in c.lower() or t.lower().startswith("sound "):
                out.append((hwnd, t, c))

    win32gui.EnumWindows(cb, None)
    return out


def walk(ctrl, max_depth=8):
    """Yield (node, depth) via GetChildren recursion."""
    stack = [(ctrl, 0)]
    while stack:
        node, d = stack.pop(0)
        yield node, d
        if d < max_depth:
            try:
                kids = node.GetChildren()
            except Exception:
                kids = []
            for k in kids:
                stack.append((k, d + 1))


def main():
    obj = None
    for hwnd, t, c in tops():
        if "objects" in t.lower():
            obj = hwnd
    if obj is None:
        print("no objects window")
        return 1
    ctrl = auto.ControlFromHandle(obj)

    print("== full named-control inventory of Praat Objects ==")
    buttons = []
    for node, d in walk(ctrl):
        try:
            n = node.Name
            ct = node.ControlTypeName
        except Exception:
            continue
        if not n:
            continue
        try:
            r = node.BoundingRectangle
            rect = (r.left, r.top, r.right, r.bottom)
        except Exception:
            rect = None
        print(f"  d={d} [{ct}] {n!r} rect={rect}")
        if ct == "ButtonControl":
            buttons.append(node)

    print("\n== try expanding menu item 'Open' ==")
    for node, d in walk(ctrl):
        try:
            if node.ControlTypeName == "MenuItemControl" and node.Name == "Open":
                break
        except Exception:
            node = None
    else:
        node = None
    if node is None:
        print("  'Open' menu item not found")
    else:
        for method in ("Expand", "Click"):
            try:
                print(f"  trying {method}()")
                getattr(node, method)()
                time.sleep(1.0)
                # enumerate popup windows
                for hwnd, t, c in tops():
                    print(f"    popup candidate: {hwnd} {c!r} {t!r}")
                    try:
                        pc = auto.ControlFromHandle(hwnd)
                        for k, kd in walk(pc, max_depth=4):
                            kn = k.Name
                            if kn:
                                print(f"       [{k.ControlTypeName}] {kn!r}")
                    except Exception as exc:
                        print("       (dump failed)", exc)
                auto.SendKeys("{ESC}")
                time.sleep(0.4)
                break
            except Exception as exc:
                print(f"  {method} failed: {exc}")

    print("\n== click 'View & Edit' ==")
    target = None
    for node, d in walk(ctrl):
        try:
            if node.ControlTypeName == "ButtonControl" and node.Name == "View & Edit":
                target = node
                break
        except Exception:
            pass
    if target is None:
        print("  not found")
    else:
        try:
            target.GetInvokePattern().Invoke()
            print("  invoked")
        except Exception as exc:
            print("  invoke failed:", exc)
            try:
                target.Click(simulateMove=False)
                print("  clicked")
            except Exception as exc2:
                print("  click failed:", exc2)
    time.sleep(4)

    print("\n== windows after ==")
    for hwnd, t, c in tops():
        print(f"   {hwnd} {c!r} {t!r}")
        if t.lower().startswith("sound "):
            try:
                ec = auto.ControlFromHandle(hwnd)
                print("   --- editor tree (named only) ---")
                for node, d in walk(ec, max_depth=8):
                    try:
                        n = node.Name
                        ct = node.ControlTypeName
                    except Exception:
                        continue
                    if n:
                        try:
                            r = node.BoundingRectangle
                            rect = (r.left, r.top, r.right, r.bottom)
                        except Exception:
                            rect = None
                        print(f"     d={d} [{ct}] {n!r} rect={rect}")
            except Exception as exc:
                print("   dump failed:", exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
