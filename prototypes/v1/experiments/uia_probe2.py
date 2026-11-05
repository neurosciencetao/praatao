"""Experiment 2: dynamic buttons after selecting a Sound, menus, and the editor window."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import uiautomation as auto
import win32gui

ROOT = Path(__file__).resolve().parents[3]
PRAAT = ROOT / "Praat.exe"
DEMO = ROOT / "prototypes" / "v0" / "assets" / "demo_vowel.wav"

LOAD = ROOT / "prototypes" / "v1" / "experiments" / "_load_demo.praat"


def make_load_script():
    LOAD.write_text(
        'Read from file: "%s"\n' % DEMO.as_posix(),
        encoding="utf-8",
    )


def find_window(substr: str):
    hit = []

    def cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            t = win32gui.GetWindowText(hwnd)
            if substr.lower() in t.lower():
                hit.append(hwnd)

    win32gui.EnumWindows(cb, None)
    return hit[0] if hit else None


def dump(hwnd, label, max_depth=5):
    print(f"\n===== {label} (hwnd={hwnd}) =====")
    ctrl = auto.ControlFromHandle(hwnd)
    stack = [(ctrl, 0)]
    while stack:
        node, d = stack.pop(0)
        try:
            r = node.BoundingRectangle
            rect = (r.left, r.top, r.right, r.bottom)
        except Exception:
            rect = None
        try:
            name = node.Name
        except Exception:
            name = None
        try:
            ctype = node.ControlTypeName
        except Exception:
            ctype = "?"
        if name or ctype not in ("Pane", "Custom", "Group", "Window"):
            print(f"  {'  ' * d}[{ctype}] {name!r} rect={rect}")
        if d < max_depth:
            try:
                for c in node.GetChildren():
                    stack.append((c, d + 1))
            except Exception:
                pass


def main():
    make_load_script()
    subprocess.run([str(PRAAT), "--send", str(LOAD)], check=False, timeout=30)
    time.sleep(3)

    obj_hwnd = find_window("Praat Objects")
    if not obj_hwnd:
        print("no objects window")
        return 1
    dump(obj_hwnd, "Objects window AFTER loading a Sound")

    # List every named ButtonControl in the Objects window.
    print("\n--- all named controls in Objects ---")
    ctrl = auto.ControlFromHandle(obj_hwnd)
    for c in ctrl.GetChildren():
        try:
            ch = c.GetChildren()
        except Exception:
            ch = []
        for g in ch:
            try:
                kids = g.GetChildren()
            except Exception:
                kids = []
            for k in kids:
                try:
                    if k.ControlTypeName == "ButtonControl" and k.Name:
                        r = k.BoundingRectangle
                        print(f"   BUTTON {k.Name!r} rect=({r.left},{r.top},{r.right},{r.bottom})")
                except Exception:
                    pass

    # Expand the Open menu and list its items.
    print("\n--- expanding 'Open' menu ---")
    try:
        menubar = ctrl.MenuBar()
        print("   menubar:", menubar)
        for mi in menubar.GetChildren():
            print("   menu:", repr(mi.Name), mi.ControlTypeName)
            if mi.Name == "Open":
                mi.GetInvokePattern().Invoke()
                time.sleep(1.2)
                # The popup is a separate top-level window.
                for hwnd in list(_enum_all()):
                    t = win32gui.GetWindowText(hwnd)
                    if not t:
                        continue
                    if win32gui.GetClassName(hwnd).startswith("Praat"):
                        print("   popup window:", repr(t), win32gui.GetClassName(hwnd))
                        c2 = auto.ControlFromHandle(hwnd)
                        for k in c2.GetChildren():
                            try:
                                print("      item:", repr(k.Name), k.ControlTypeName)
                                for g2 in k.GetChildren():
                                    print("         sub:", repr(g2.Name), g2.ControlTypeName)
                            except Exception as exc:
                                print("      err", exc)
                # close popup
                auto.SendKeys("{ESC}")
                time.sleep(0.5)
    except Exception as exc:
        print("   menu expansion failed:", exc)

    # Open View & Edit via script and dump the editor window.
    print("\n--- opening View & Edit via script ---")
    EDIT = ROOT / "prototypes" / "v1" / "experiments" / "_open_editor.praat"
    EDIT.write_text(
        'Read from file: "%s"\n'
        "Object: \"Sound demo_vowel\"\n"
        "View & Edit\n" % DEMO.as_posix(),
        encoding="utf-8",
    )
    subprocess.run([str(PRAAT), "--send", str(EDIT)], check=False, timeout=30)
    time.sleep(4)

    for hwnd in _enum_all():
        t = win32gui.GetWindowText(hwnd)
        if t.lower().startswith("sound "):
            dump(hwnd, f"EDITOR window {t!r}")

    return 0


def _enum_all():
    out = []

    def cb(hwnd, _):
        out.append(hwnd)

    win32gui.EnumWindows(cb, None)
    return out


if __name__ == "__main__":
    sys.exit(main())
