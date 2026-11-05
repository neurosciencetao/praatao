"""Does ``--send`` pull Praat to the front?

The coach sends a Praat script every so often to read the semantic state.
If that makes Praat jump to the front while the student is typing
somewhere else, it is a bug of the first order.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import win32gui  # noqa: E402

from praatao.sensors.praat_state import PraatStateProbe  # noqa: E402
from praatao.sensors.uia import PraatUI  # noqa: E402


def foreground() -> str:
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return "<none>"
    return (
        f"{win32gui.GetClassName(hwnd)} "
        f"{win32gui.GetWindowText(hwnd)[:40]!r}"
    )


def praat_windows() -> list[tuple[int, str, str, bool]]:
    found: list[tuple[int, str, str, bool]] = []

    def _collect(hwnd: int, _extra: object) -> None:
        try:
            cls = win32gui.GetClassName(hwnd) or ""
            title = win32gui.GetWindowText(hwnd) or ""
            if "praat" in cls.casefold() or title.startswith("Praat"):
                found.append(
                    (hwnd, cls, title[:30], bool(win32gui.IsWindowVisible(hwnd)))
                )
        except Exception:
            return

    win32gui.EnumWindows(_collect, None)
    return found


def main() -> int:
    probe = PraatStateProbe()
    ui = PraatUI()
    print("praat windows:")
    for item in praat_windows():
        print("   ", item)

    script = 'writeFileLine: "C:/Users/rantao/AppData/Local/Temp/praatao_fg2.txt", "x"'

    print(f"foreground before : {foreground()}")
    start = time.perf_counter()
    ok = probe.send(script, timeout=8.0)
    elapsed = time.perf_counter() - start
    time.sleep(0.8)
    print(f"foreground after  : {foreground()}")
    print(f"send() ok={ok} in {elapsed:.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
