"""Which UIA call activates Praat?

Everything the coach does while the student is working in another program
must leave the foreground alone.  This checks every call the coach makes.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import win32gui  # noqa: E402

from praatao.sensors.praat_state import PraatStateProbe  # noqa: E402
from praatao.sensors.uia import PraatUI, praat_has_focus  # noqa: E402


def foreground() -> str:
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return "<none>"
    return f"{win32gui.GetClassName(hwnd)} {win32gui.GetWindowText(hwnd)[:28]!r}"


def activate_our_own(hwnd: int) -> None:
    """Bring our own window to the front (always allowed)."""

    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass
    time.sleep(0.4)


def main() -> int:
    ui = PraatUI()
    probe = PraatStateProbe()
    windows = ui.windows()
    if not windows:
        print("Praat is not running")
        return 1

    # Our own window stands in for "another application in front".
    import tkinter

    root = tkinter.Tk()
    root.title("Praatao probe")
    root.geometry("300x120+50+600")
    root.update()
    own = int(root.frame(), 16) if False else None
    hwnd = int(root.winfo_id())
    root.attributes("-topmost", True)
    root.update()

    praat = next((w for w in windows if w.title == "Praat Objects"), windows[0])
    target = (praat.rect[0] + 30, praat.rect[1] + 30)

    checks = [
        ("praat_has_focus()", lambda: praat_has_focus()),
        ("ui.windows()", lambda: ui.windows()),
        ("ui._control_from_window()", lambda: ui._control_from_window(praat)),
        ("ui.find('Inspect')", lambda: ui.find("Inspect")),
        ("ui.open_popup_items()", lambda: ui.open_popup_items()),
        ("probe.fast()", lambda: probe.fast()),
        ("element_at_point() over Praat",
         lambda: ui.element_at_point(*target, praat_only=False)),
        ("element_at_point() praat_only",
         lambda: ui.element_at_point(*target, praat_only=True)),
    ]

    for label, action in checks:
        activate_our_own(hwnd)
        before = foreground()
        try:
            action()
        except Exception as exc:  # noqa: BLE001
            print(f"  {label}: raised {exc}")
            continue
        time.sleep(0.25)
        after = foreground()
        mark = "  *** ACTIVATED PRAAT ***" if "praat" in after.casefold() \
            and "praat" not in before.casefold() else ""
        print(f"{label:38s} {before[:34]:36s} -> {after[:34]}{mark}")

    root.destroy()
    return 0


if __name__ == "__main__":
    sys.exit(main())
