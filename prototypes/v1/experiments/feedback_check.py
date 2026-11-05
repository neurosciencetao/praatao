"""Does the report-a-problem window really open?

The button sits in the side panel.  The check drives the real program:
it opens the panel, presses the button and looks at the screen.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import uiautomation as auto  # noqa: E402

from PIL import ImageGrab  # noqa: E402

PACKAGED = ROOT / "dist" / "Praatao" / "Praatao.exe"
SHOTS = ROOT / "docs" / "screenshots"


def find_window(title: str, timeout: float = 8.0) -> auto.WindowControl | None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            win = auto.WindowControl(searchDepth=auto.DESKTOP, SubName=title)
            if win.Exists(2):
                return win
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.4)
    return None


def find_button(name: str, timeout: float = 8.0):
    """Find a button anywhere on the screen."""

    deadline = time.time() + timeout
    while time.time() < deadline:
        for depth in range(2, 6):
            try:
                button = auto.ButtonControl(searchDepth=depth, SubName=name)
                if button.Exists(0.3):
                    return button
            except Exception:  # noqa: BLE001
                pass
        time.sleep(0.3)
    return None


def main() -> int:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    SHOTS.mkdir(parents=True, exist_ok=True)

    coach = subprocess.Popen([str(PACKAGED)], cwd=str(PACKAGED.parent), env=env)
    time.sleep(5.0)

    # 1. the greeting window has a button that opens the panel
    opened = find_button("打开侧栏", timeout=10.0)
    if opened is None:
        print("the greeting window did not show up")
        ImageGrab.grab(all_screens=True).save(str(SHOTS / "feedback-window.png"))
        coach.terminate()
        return 1
    opened.Click(simulateMove=False)
    time.sleep(3.0)

    # 2. the panel has the report button
    report = find_button("报告问题")
    if report is None:
        print("the report button was not found in the panel")
        ImageGrab.grab(all_screens=True).save(str(SHOTS / "feedback-window.png"))
        coach.terminate()
        return 1
    report.Click(simulateMove=False)
    time.sleep(2.5)

    window = find_button("在 GitHub 上提交", timeout=4.0)
    ImageGrab.grab(all_screens=True).save(str(SHOTS / "feedback-window.png"))
    print("the report window is open:", window is not None)
    ok = window is not None

    if ok:
        # The two ways out of the window have to be there.
        print("the save button is there:", find_button("只存到本地", 3.0) is not None)
        print("the cancel button is there:", find_button("取消", 3.0) is not None)

    coach.terminate()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
