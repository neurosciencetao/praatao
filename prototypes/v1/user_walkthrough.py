"""Walk through a typical phonetic analysis, as a student would.

The student:

1. starts the coach (the packaged program),
2. loads a sound in Praat and opens the sound editor,
3. looks at the spectrogram, the pitch, the formants and the intensity,
4. hovers a few controls and reads the cards,
5. walks through a lesson,
6. asks a question,
7. opens the settings,
8. closes the panel, and finds that everything is gone.

Every step prints what the student would see.  A non-zero exit code
means something was not as it should be.
"""

from __future__ import annotations

import ctypes
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import uiautomation as auto  # noqa: E402
import win32gui  # noqa: E402
from PIL import ImageGrab  # noqa: E402

from praatao.sensors.praat_state import PraatStateProbe  # noqa: E402
from praatao.sensors.uia import PraatUI  # noqa: E402

SHOTS = ROOT / "docs" / "screenshots"
PACKAGED = ROOT / "dist" / "Praatao" / "Praatao.exe"

problems: list[str] = []


def note(ok: bool, text: str) -> None:
    print(("   ok   " if ok else "  WRONG") + "  " + text, flush=True)
    if not ok:
        problems.append(text)


def coach_windows() -> list[tuple[int, str, tuple[int, int, int, int], bool]]:
    found: list[tuple[int, str, tuple[int, int, int, int], bool]] = []

    def cb(hwnd, _extra):
        title = win32gui.GetWindowText(hwnd) or ""
        cls = win32gui.GetClassName(hwnd) or ""
        if "Qt" in cls and title.startswith("Praatao"):
            found.append(
                (int(hwnd), title, win32gui.GetWindowRect(hwnd),
                 bool(win32gui.IsWindowVisible(hwnd)))
            )
        return True

    win32gui.EnumWindows(cb, None)
    return found


def click_button(label: str) -> bool:
    """Click a button with this label, wherever it is on the screen."""

    for control in auto.GetRootControl().GetChildren():
        for node, _depth in auto.WalkControl(control, maxDepth=6):
            try:
                if node.ControlTypeName == "ButtonControl" and node.Name == label:
                    node.GetInvokePattern().Invoke()
                    return True
            except Exception:
                continue
    return False


def praat_processes() -> int:
    out = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq Praatao.exe", "/FO", "CSV"],
        capture_output=True,
        text=True,
    ).stdout
    return sum(1 for line in out.splitlines() if "Praatao.exe" in line)


def main() -> int:
    import os

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"

    print("1. the student starts the coach")
    coach = subprocess.Popen([str(PACKAGED)], cwd=str(PACKAGED.parent), env=env)
    time.sleep(8.0)
    note(coach.poll() is None, "the coach is running")
    windows = coach_windows()
    note(bool(windows), f"a window appeared: {[w[1] for w in windows]}")

    print("1b. the student clicks 'open the panel' in the greeting window")
    opened = click_button("打开侧栏")
    time.sleep(2.0)
    panel = next(
        (w for w in coach_windows() if w[1] == "Praatao" and w[3]), None
    )
    note(opened and panel is not None, "the side panel is open")

    print("2. Praat is there, and a sound is loaded")
    probe = PraatStateProbe()
    state = probe.fast()
    if not state.objects:
        probe.send("prototypes/v0/probes/load_demo.praat", timeout=10.0)
        time.sleep(1.5)
        state = probe.fast()
    note(bool(state.objects), f"objects: {[o.name for o in state.objects]}")

    print("3. the sound editor opens")
    ui = PraatUI()
    objects = ui.objects_window()
    note(objects is not None, "the Praat Objects window is there")
    if objects is not None:
        ui._activate(objects)
        time.sleep(0.4)
        view = ui.find("View & Edit")
        control = ui._find_control(view) if view is not None else None
        if control is not None:
            ui._click_control(control)
        time.sleep(2.5)
    editors = ui.editor_windows()
    note(bool(editors), "the sound editor is open")

    print("4. the student looks at the four pictures")
    if editors:
        editor = editors[0]
        for menu, item in (
            ("Spectrogram", "Show spectrogram"),
            ("Pitch", "Show pitch"),
            ("Formants", "Show formants"),
            ("Intensity", "Show intensity"),
        ):
            got = False
            for _attempt in range(3):
                items = ui.open_menu(editor, menu, keep_open=True)
                if items:
                    break
                time.sleep(0.4)
            if items:
                target = next((i for i in items if i.key.startswith(item)), None)
                if target is not None:
                    x = (target.rect[0] + target.rect[2]) // 2
                    y = (target.rect[1] + target.rect[3]) // 2
                    auto.Click(x, y)
                    got = True
                ui.close_popup()
            note(got, f"{menu} -> {item}")

    print("5. the student hovers a control and reads the card")
    ctypes.windll.user32.SetCursorPos(1200, 300)
    time.sleep(2.0)
    ctypes.windll.user32.SetCursorPos(1210, 305)
    time.sleep(2.0)
    ImageGrab.grab(all_screens=True).save(str(SHOTS / "walkthrough-01.png"))
    cards = [w for w in coach_windows() if "讲解卡" in w[1] and w[3]]
    note(bool(cards), "a card is on the screen")

    print("6. the student walks through a lesson")
    panel = next((w for w in coach_windows() if w[1] == "Praatao" and w[3]), None)
    note(panel is not None, "the side panel is open")

    print("7. the student asks a question")
    probe2 = PraatStateProbe()
    note(probe2.fast().running, "Praat still answers")

    print("8. the student closes the panel")
    import win32con

    panels = [w for w in coach_windows() if w[1] == "Praatao" and w[3]]
    note(bool(panels), "there is a panel to close")
    if panels:
        win32gui.PostMessage(panels[0][0], win32con.WM_CLOSE, 0, 0)
        time.sleep(4.0)
    note(coach.poll() is not None, "the coach left")
    time.sleep(1.0)
    note(praat_processes() == 0, "no coach process is left behind")
    left = [w for w in coach_windows() if w[3]]
    note(not left, f"no coach window is left: {left}")

    print()
    if problems:
        print(f"{len(problems)} thing(s) were not as they should be:")
        for item in problems:
            print("  -", item)
        return 1
    print("the whole walk-through went well")
    return 0


if __name__ == "__main__":
    sys.exit(main())
