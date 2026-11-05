"""Who steals the foreground window?

The coach must never pull Praat (or anything else) to the front while the
student works.  This measures it: the foreground window is recorded
before and after each action the coach can take.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import win32gui  # noqa: E402

SCRIPT = ROOT / "prototypes" / "v1" / "experiments" / "_fg_probe.praat"


def foreground() -> str:
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return "<none>"
    return (
        f"{win32gui.GetClassName(hwnd)} "
        f"{win32gui.GetWindowText(hwnd)[:40]!r}"
    )


def main() -> int:
    exe = ROOT / "Praat.exe"
    SCRIPT.write_text(
        'writeFileLine: "C:/Users/rantao/AppData/Local/Temp/praatao_fg.txt", "x"\n',
        encoding="ascii",
    )

    print(f"before            : {foreground()}")

    # 1. a console Praat for the version string
    start = time.perf_counter()
    result = subprocess.run(
        [str(exe), "--version"],
        timeout=10.0,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    time.sleep(0.4)
    print(f"after --version   : {foreground()}  ({time.perf_counter() - start:.1f} s)")
    print(f"   raw output      : {(result.stdout or b'')[:60]!r}")

    # 2. a script sent to the running instance
    before = foreground()
    start = time.perf_counter()
    try:
        subprocess.run(
            [str(exe), "--send", str(SCRIPT)],
            timeout=8.0,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        note = ""
    except subprocess.TimeoutExpired:
        note = " (TIMED OUT: the console stays alive!)"
    time.sleep(0.8)
    after = foreground()
    print(f"after --send      : {after}  ({time.perf_counter() - start:.1f} s){note}")
    print(f"   foreground moved: {after != before}")
    SCRIPT.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
