"""Diagnostic: what happened to the --send, and can UIA click 'View & Edit'?"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import uiautomation as auto
import win32gui

ROOT = Path(__file__).resolve().parents[3]
PRAAT = ROOT / "Praat.exe"


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


def main():
    print("== current praat-ish windows ==")
    for hwnd, t, c in tops():
        print(f"   hwnd={hwnd} class={c!r} title={t!r}")

    print("\n== praat processes ==")
    subprocess.run(["tasklist", "/FI", "IMAGENAME eq Praat.exe"], check=False)

    # Try a trivial send with a short timeout.
    t1 = ROOT / "prototypes" / "v1" / "experiments" / "_ping.praat"
    t1.write_text('writeFileLine: "%s", "pong"\n' % (t1.parent / "_pong.txt").as_posix(), encoding="utf-8")
    start = time.time()
    try:
        subprocess.run([str(PRAAT), "--send", str(t1)], check=False, timeout=12,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"   trivial --send OK in {time.time()-start:.2f}s")
    except subprocess.TimeoutExpired:
        print(f"   trivial --send TIMED OUT after {time.time()-start:.2f}s")
    print("   pong exists:", (t1.parent / "_pong.txt").exists())

    # Now click 'View & Edit' via UIA Invoke.
    print("\n== clicking 'View & Edit' via UIA ==")
    obj = None
    for hwnd, t, c in tops():
        if "objects" in t.lower():
            obj = hwnd
    if obj is None:
        print("   no objects window")
        return 1
    ctrl = auto.ControlFromHandle(obj)
    found = None
    for node in auto.WalkTree(ctrl, maxDepth=5):
        try:
            if node.ControlTypeName == "ButtonControl" and node.Name == "View & Edit":
                found = node
                break
        except Exception:
            pass
    if found is None:
        print("   button not found")
        return 1
    r = found.BoundingRectangle
    print("   invoking at", (r.left, r.top, r.right, r.bottom))
    try:
        found.GetInvokePattern().Invoke()
    except Exception as exc:
        print("   invoke failed:", exc, "- trying Click")
        found.Click(simulateMove=False)
    time.sleep(4)
    print("   windows now:")
    for hwnd, t, c in tops():
        print(f"      hwnd={hwnd} class={c!r} title={t!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
