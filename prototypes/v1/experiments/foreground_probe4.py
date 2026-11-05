"""Does ``--send`` pull Praat to the front while another app has it?

This is the case that matters: the student is typing in another program
(the chat, a paper, a mail client) and the coach sends its probe script.
If Praat jumps to the front, the student loses their focus.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import win32gui  # noqa: E402

from praatao.sensors.praat_state import PraatStateProbe  # noqa: E402


def foreground() -> str:
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return "<none>"
    return f"{win32gui.GetClassName(hwnd)} {win32gui.GetWindowText(hwnd)[:36]!r}"


def a_non_praat_window() -> int:
    """A visible window that is not Praat and not one of ours."""

    found = 0

    def _collect(hwnd: int, _extra: object) -> None:
        nonlocal found
        if found:
            return
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return
            cls = (win32gui.GetClassName(hwnd) or "").casefold()
            title = win32gui.GetWindowText(hwnd) or ""
            if "praat" in cls or title.startswith("Praatao"):
                return
            if cls in ("consolewindowclass", "progman", "shell_traywnd"):
                return
            found = hwnd
        except Exception:
            return

    win32gui.EnumWindows(_collect, None)
    return found


def main() -> int:
    probe = PraatStateProbe()
    target = a_non_praat_window()
    if not target:
        print("no other window to test with")
        return 1
    print("using:", win32gui.GetClassName(target), win32gui.GetWindowText(target)[:40])

    # Make that window the foreground one.
    win32gui.SetForegroundWindow(target)
    time.sleep(0.8)
    print(f"foreground before : {foreground()}")

    script = 'writeFileLine: "C:/TEMP/praatao_fg3.txt", "x"'
    start = time.perf_counter()
    ok = probe.send(script, timeout=8.0)
    time.sleep(1.0)
    print(f"foreground after  : {foreground()}  ({time.perf_counter() - start:.1f} s, ok={ok})")
    print("foreground moved  :", foreground() != f"{win32gui.GetClassName(target)} "
          f"{win32gui.GetWindowText(target)[:36]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
