"""Check the greeting window's buttons: settings opens, quit leaves."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import uiautomation as auto  # noqa: E402

EXE = ROOT / "dist" / "Praatao" / "Praatao.exe"


def windows() -> list[tuple[str, object]]:
    found = []
    for control in auto.GetRootControl().GetChildren():
        try:
            if control.BoundingRectangle and control.Name:
                found.append((control.Name, control))
        except Exception:
            continue
    return found


def toast_button(label: str):
    for name, control in windows():
        if name != "Praatao":
            continue
        try:
            for node, _depth in auto.WalkControl(control, maxDepth=6):
                if node.ControlTypeName == "ButtonControl" and node.Name == label:
                    return node
        except Exception:
            continue
    return None


def click(node) -> None:
    r = node.BoundingRectangle
    auto.Click((r.left + r.right) // 2, (r.top + r.bottom) // 2)


def main() -> int:
    print("starting", EXE)
    subprocess.Popen([str(EXE)], cwd=str(EXE.parent))
    time.sleep(6.0)

    button = toast_button("设置")
    if button is None:
        print("FAIL: the settings button is not there")
        return 1
    click(button)
    time.sleep(2.0)
    names = [name for name, _c in windows()]
    print("windows now:", names[:12])
    settings_open = any("设置" in name or "Settings" in name for name in names)
    print("settings window open:", settings_open)

    button = toast_button("退出")
    if button is None:
        print("FAIL: the quit button is not there")
        return 1
    click(button)
    time.sleep(3.0)
    alive = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq Praatao.exe"],
        capture_output=True,
        text=True,
    ).stdout
    still_running = "Praatao.exe" in alive
    print("still running after quit:", still_running)
    return 0 if (settings_open and not still_running) else 1


if __name__ == "__main__":
    sys.exit(main())
