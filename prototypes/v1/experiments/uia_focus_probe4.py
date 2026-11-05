"""Does a UIA hit test activate the window it hits?

This is the mechanism behind "Praat keeps jumping to the front while I
am typing": the coach hit tests the point under the cursor, and if the
hit test activates the window, every hover over Praat pulls Praat to the
front.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import tkinter  # noqa: E402

import win32gui  # noqa: E402

from praatao.sensors import uia as uia_module  # noqa: E402
from praatao.sensors.uia import PraatUI  # noqa: E402


def foreground() -> str:
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return "<none>"
    return f"{win32gui.GetClassName(hwnd)} {win32gui.GetWindowText(hwnd)[:26]!r}"


def main() -> int:
    ui = PraatUI()
    windows = ui.windows()
    if not windows:
        print("Praat is not running")
        return 1

    root = tkinter.Tk()
    root.title("Praatao probe")
    root.geometry("300x120+40+700")
    root.update()

    praat = next((w for w in windows if w.title == "Praat Objects"), windows[0])
    point = (praat.rect[0] + 30, praat.rect[1] + 30)
    print("praat rect:", praat.rect, "point:", point)

    def fresh_front():
        try:
            win32gui.SetForegroundWindow(int(root.wm_frame(), 16))
        except Exception:
            pass
        time.sleep(0.5)

    fresh_front()
    print(f"before the hit test : {foreground()}")
    control = uia_module.auto.ControlFromPoint(*point)
    time.sleep(0.4)
    print(f"after the hit test  : {foreground()}")
    print("   hit:", getattr(control, "Name", "?"), getattr(control, "ControlTypeName", "?"))

    fresh_front()
    print(f"before a tree walk  : {foreground()}")
    ctrl = ui._control_from_window(praat)
    nodes = list(ui._iter_controls(ctrl, max_depth=4))
    time.sleep(0.4)
    print(f"after a tree walk ({len(nodes)} nodes) : {foreground()}")

    fresh_front()
    print(f"before ui.find     : {foreground()}")
    found = ui.find("Inspect")
    time.sleep(0.4)
    print(f"after ui.find ({found.name if found else None}) : {foreground()}")

    from praatao.sensors.praat_state import PraatStateProbe, praat_available

    fresh_front()
    print(f"before praat_available() : {foreground()}")
    praat_available()
    time.sleep(0.4)
    print(f"after praat_available()  : {foreground()}")

    probe = PraatStateProbe()
    fresh_front()
    print(f"before probe.fast() : {foreground()}")
    probe.fast()
    time.sleep(0.4)
    print(f"after probe.fast()  : {foreground()}")

    fresh_front()
    print(f"before probe.quick() : {foreground()}")
    probe.quick()
    time.sleep(0.4)
    print(f"after probe.quick()  : {foreground()}")

    root.destroy()
    return 0


if __name__ == "__main__":
    sys.exit(main())
