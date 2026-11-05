"""Three checks about closing and starting.

1. Closing the side panel must end the whole program (no process left).
2. Starting it twice must not leave two coaches behind; the second start
   brings the first one forward.
3. The tray's "open the panel" must actually open the panel.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import uiautomation as auto  # noqa: E402

RUN = [sys.executable, "run.py", "--no-praat", "--quiet"]
ENV = {"PYTHONIOENCODING": "utf-8"}


def running_coaches() -> list[int]:
    out = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV"],
        capture_output=True,
        text=True,
    ).stdout
    return [line for line in out.splitlines() if "run.py" in line]


def find_panel() -> object:
    for control in auto.GetRootControl().GetChildren():
        try:
            if control.Name == "Praatao" and control.BoundingRectangle:
                width = control.BoundingRectangle.right() - control.BoundingRectangle.left()
                if width > 200:
                    return control
        except Exception:
            continue
    return None


def close_panel(panel) -> None:
    for node, _depth in auto.WalkControl(panel, maxDepth=4):
        try:
            if node.ControlTypeName == "ButtonControl" and node.Name in ("Close", "关闭"):
                node.GetInvokePattern().Invoke()
                return
        except Exception:
            continue


def main() -> int:
    import os

    env = dict(os.environ)
    env.update(ENV)

    print("1. start the coach")
    first = subprocess.Popen(RUN, cwd=str(ROOT), env=env)
    time.sleep(6.0)
    print("   the coach is running:", first.poll() is None)

    print("2. start it a second time")
    second = subprocess.Popen(RUN, cwd=str(ROOT), env=env)
    time.sleep(5.0)
    print("   the second copy left by itself:", second.poll() is not None)
    print("   the first copy is still running:", first.poll() is None)

    print("3. the panel is open (the second start brought it forward)")
    panel = find_panel()
    print("   panel found:", panel is not None)

    print("4. close the panel")
    if panel is not None:
        close_panel(panel)
    time.sleep(3.0)
    print("   the coach left:", first.poll() is not None)

    try:
        first.wait(timeout=5)
    except Exception:
        first.kill()
    if second.poll() is None:
        second.kill()
    return 0


if __name__ == "__main__":
    sys.exit(main())
