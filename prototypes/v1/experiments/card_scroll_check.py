"""Can the student read the whole card?

Two things a student does with a long card: scroll it with the wheel,
and drag the scroll bar.  Both have to work, and neither may make the
card disappear.
"""

from __future__ import annotations

import ctypes
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import uiautomation as auto  # noqa: E402
import win32gui  # noqa: E402
from PIL import ImageGrab  # noqa: E402

from praatao.sensors.uia import PraatUI  # noqa: E402

PACKAGED = ROOT / "dist" / "Praatao" / "Praatao.exe"
SHOTS = ROOT / "docs" / "screenshots"


def card_window() -> int:
    found = 0

    def cb(hwnd, _extra):
        nonlocal found
        if (win32gui.GetWindowText(hwnd) or "") == "Praatao 讲解卡":
            if win32gui.IsWindowVisible(hwnd):
                found = int(hwnd)
        return True

    win32gui.EnumWindows(cb, None)
    return found


def scrollbar_value(hwnd: int) -> int:
    """The value of the card's scroll bar, read with UI Automation."""

    control = auto.ControlFromHandle(hwnd)
    for node, _depth in auto.WalkControl(control, maxDepth=6):
        try:
            if node.ControlTypeName == "ScrollBarControl":
                pattern = node.GetScrollPattern()
                return int(pattern.VerticalScrollPercent)
        except Exception:
            continue
    return -1


def find_scroll_bar(card_rect: tuple[int, int, int, int]) -> tuple[int, int] | None:
    """Where the card's scroll bar really is, read from the pixels.

    The scroll bar is the one light-brown bar on the right of the card
    (#DCD0BC).  Qt does not expose it to UI Automation, so it is looked
    for in a screenshot of the card.  The answer is the middle of the
    handle, where a drag starts.
    """

    shot = ImageGrab.grab(bbox=card_rect, all_screens=True).convert("RGB")
    width, height = shot.size
    for x in range(width - 60, width - 5):
        rows = []
        for y in range(20, height - 20):
            r, g, b = shot.getpixel((x, y))
            if abs(r - 220) < 14 and abs(g - 208) < 14 and abs(b - 188) < 16:
                rows.append(y)
        if len(rows) > 20:
            middle = rows[len(rows) // 2]
            return (card_rect[0] + x, card_rect[1] + middle)
    return None


def main() -> int:
    import os

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    coach = subprocess.Popen([str(PACKAGED)], cwd=str(PACKAGED.parent), env=env)
    time.sleep(9.0)

    ui = PraatUI()
    objects = ui.objects_window()
    if objects is None:
        print("Praat is not running")
        return 1
    ui._activate(objects)
    time.sleep(0.6)

    # The Objects window only offers the object buttons when an object is
    # selected, so a sound has to be there.
    from praatao.sensors.praat_state import PraatStateProbe

    probe = PraatStateProbe()
    if not probe.fast().objects:
        probe.send("prototypes/v0/probes/load_demo.praat", timeout=10.0)
        time.sleep(1.5)
    ui._activate(objects)
    time.sleep(0.6)

    # The "Modify" button in the Objects window has a long card.
    modify = ui.find("Modify")
    control = ui._find_control(modify) if modify is not None else None
    if control is None:
        print("no Modify button")
        coach.terminate()
        return 1
    rect = control.BoundingRectangle
    x = (rect.left + rect.right) // 2
    y = (rect.top + rect.bottom) // 2
    ctypes.windll.user32.SetCursorPos(x, y)
    time.sleep(0.5)
    ctypes.windll.user32.SetCursorPos(x + 2, y + 1)
    time.sleep(2.5)

    hwnd = card_window()
    print("card window:", hwnd)
    if not hwnd:
        coach.terminate()
        return 1
    card_rect = win32gui.GetWindowRect(hwnd)
    print("card rect:", card_rect)
    ImageGrab.grab(all_screens=True).save(str(SHOTS / "card-scroll-01.png"))
    before = scrollbar_value(hwnd)
    print("scroll bar before:", before)

    print("1. scroll with the wheel")
    inside = (card_rect[0] + 60, card_rect[1] + 120)
    ctypes.windll.user32.SetCursorPos(*inside)
    time.sleep(0.4)
    before_pixels = ImageGrab.grab(bbox=card_rect, all_screens=True).convert("RGB")
    for _ in range(5):
        ctypes.windll.user32.mouse_event(0x0800, 0, 0, -120, 0)  # wheel down
        time.sleep(0.08)
    time.sleep(1.0)
    after_pixels = ImageGrab.grab(bbox=card_rect, all_screens=True).convert("RGB")
    changed = sum(
        1
        for a, b in zip(before_pixels.getdata(), after_pixels.getdata())
        if abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2]) > 40
    )
    print("   pixels that changed:", changed)
    print("   the card scrolled:", changed > 2000)
    ImageGrab.grab(all_screens=True).save(str(SHOTS / "card-scroll-02.png"))

    print("2. drag the scroll bar")
    found = find_scroll_bar(card_rect)
    print("   the scroll bar is at:", found)
    if found is None:
        coach.terminate()
        return 1
    bar_x, bar_y = found
    ctypes.windll.user32.SetCursorPos(bar_x, bar_y)
    time.sleep(0.3)
    ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)  # left button down
    time.sleep(0.2)
    for step in range(6):
        ctypes.windll.user32.SetCursorPos(bar_x, bar_y + 20 * step)
        time.sleep(0.15)
    ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)  # left button up
    time.sleep(1.0)
    print("   the card is still on the screen:", card_window() != 0)
    ImageGrab.grab(all_screens=True).save(str(SHOTS / "card-scroll-03.png"))

    coach.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
