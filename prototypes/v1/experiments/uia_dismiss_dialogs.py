"""Utility: dismiss stale modal Praat dialogs.

Other teammates probe Praat with ``Praat.exe --send`` scripts; a failing
formula leaves a modal ``Message`` box behind, and a modal box freezes the
Objects window (no action buttons, no menu clicks).  This script clicks
``OK`` on every modal dialog that belongs to the Praat process.

Run:  python prototypes/v1/experiments/uia_dismiss_dialogs.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import uiautomation as auto  # noqa: E402
import win32gui  # noqa: E402
import win32process  # noqa: E402


def praat_pids() -> set[int]:
    pids: set[int] = set()

    def cb(hwnd, _):
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return
            cls = win32gui.GetClassName(hwnd) or ""
            title = win32gui.GetWindowText(hwnd) or ""
        except Exception:
            return
        if cls.lower().startswith("praat") or title == "Praat Objects":
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            pids.add(int(pid))

    win32gui.EnumWindows(cb, None)
    return pids


def dialogs(pids: set[int]) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []

    def cb(hwnd, _):
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return
            cls = win32gui.GetClassName(hwnd) or ""
            if cls not in ("#32770", "#32768"):
                return
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
        except Exception:
            return
        if int(pid) in pids:
            out.append((int(hwnd), win32gui.GetWindowText(hwnd)))

    win32gui.EnumWindows(cb, None)
    return out


def dismiss(hwnd: int) -> bool:
    try:
        ctrl = auto.ControlFromHandle(hwnd)
    except Exception:
        return False
    stack = [ctrl]
    while stack:
        node = stack.pop()
        try:
            if node.ControlTypeName == "ButtonControl" and node.Name.strip().upper() in (
                "OK",
                "&OK",
                "CLOSE",
                "&CLOSE",
            ):
                node.GetInvokePattern().Invoke()
                return True
        except Exception:
            pass
        try:
            stack.extend(node.GetChildren())
        except Exception:
            pass
    return False


def main() -> int:
    pids = praat_pids()
    print("praat pids:", pids)
    found = dialogs(pids)
    print("modal windows:", found)
    for hwnd, title in found:
        print(f"   dismissing {hwnd} {title!r} ->", dismiss(hwnd))
        time.sleep(0.4)
    time.sleep(0.5)
    print("remaining:", dialogs(pids))
    return 0


if __name__ == "__main__":
    sys.exit(main())
