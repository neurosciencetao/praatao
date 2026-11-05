"""Acceptance screenshots.

Every picture is taken while the **real** application is running its **real**
tick loop, with the **real** mouse on a real Praat control.  Nothing is
mocked except the two shots that need a control the knowledge base has never
heard of.

    python prototypes/v1/acceptance_capture.py
"""

from __future__ import annotations

import ctypes
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "docs" / "screenshots" / "acceptance"

user32 = ctypes.windll.user32


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def settle(app, seconds: float = 0.8) -> None:
    """Let the real application do its work for a while."""

    deadline = time.time() + seconds
    while time.time() < deadline:
        app.pump()
        time.sleep(0.02)


def shot(app, name: str, crop: tuple[int, int, int, int] | None = None) -> Path:
    """Save the screen, and a focused crop of the part that matters.

    The full screen shows whatever else is on the desktop; the crop is
    what the acceptance is really about.
    """

    from PIL import ImageGrab

    OUT.mkdir(parents=True, exist_ok=True)
    settle(app, 0.4)
    full = ImageGrab.grab(all_screens=True)
    path = OUT / name
    full.save(path)
    if crop is not None:
        focused = full.crop(crop)
        focused.save(OUT / ("focus-" + name))
    print("saved", path.name)
    return path


def move_mouse(x: int, y: int) -> None:
    user32.SetCursorPos(int(x), int(y))


def click(app, x: int, y: int) -> None:
    """A real click, with the application running while the button is down."""
    move_mouse(x, y)
    time.sleep(0.15)
    user32.mouse_event(0x0002, 0, 0, 0, 0)  # LEFTDOWN
    deadline = time.time() + 0.15
    while time.time() < deadline:
        app.pump()
        time.sleep(0.005)
    user32.mouse_event(0x0004, 0, 0, 0, 0)  # LEFTUP


def move_window(hwnd: int, x: int, y: int) -> tuple[int, int]:
    """Move a window and remember where it was."""

    import win32gui

    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    win32gui.MoveWindow(hwnd, x, y, right - left, bottom - top, True)
    time.sleep(0.4)
    return (left, top)


def restore_window(hwnd: int, where: tuple[int, int]) -> None:
    import win32gui

    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    win32gui.MoveWindow(hwnd, where[0], where[1], right - left, bottom - top, True)
    time.sleep(0.3)


def centre(rect) -> tuple[int, int]:
    return ((rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2)


# --------------------------------------------------------------------------
# the shots
# --------------------------------------------------------------------------
def main() -> int:
    import run as praatao_run
    from praatao.sensors.uia import PraatUI

    app = praatao_run.Praatao(lang="zh", use_llm=True)
    print("backend:", app.backend)
    print("tutor  :", app.advisor.status())

    # Start the real tick loop (the timers drive it, the way it does when
    # the program runs normally).
    app.host.after(praatao_run.MOUSE_POLL_MS, app._mouse_poll)
    app.host.after(45, app._tick)

    ui = PraatUI()
    objects = ui.objects_window()
    editors = ui.editor_windows()
    editor = editors[0] if editors else None

    # The drawing-area shot needs an editor window; open one if Praat was
    # started without one.
    if editor is None and objects is not None:
        ui._activate(objects)
        time.sleep(0.5)
        view = ui.find("View & Edit")
        if view is not None:
            control = ui._find_control(view)
            if control is not None:
                ui._click_control(control)
            time.sleep(2.0)
            editors = ui.editor_windows()
            editor = editors[0] if editors else None
            print("editor opened:", editor.title if editor else None)

    # -- 1. the drawing area ----------------------------------------
    if editor is not None:
        ui._activate(editor)
        time.sleep(0.5)
        region = app.canvas.region_at(*centre(editor.rect)) if app.canvas else None
        if region is not None:
            move_mouse(*centre(region.rect))
            settle(app, 2.2)
            shot(app, "01-drawing-area.png", crop=(60, 90, 1915, 1035))
            app._dismiss_hover()

    # -- 2. a control, with the editor out of the way ---------------
    editor_home = None
    if editor is not None and objects is not None:
        editor_home = move_window(editor.hwnd, 1400, 120)
    if objects is not None:
        ui._activate(objects)
        time.sleep(0.6)
        target = ui.find("View & Edit")
        if target is None:
            target = ui.find("Sound help")
        if target is not None:
            move_mouse(*centre(target.rect))
            settle(app, 2.2)
            shot(app, "02-hover-control.png", crop=(0, 0, 1010, 745))

    # -- 3. a menu item ----------------------------------------------
    if objects is not None:
        items = []
        for _attempt in range(3):
            try:
                items = ui.open_menu(objects, "Open", keep_open=True)
            except Exception as exc:
                print("could not open the menu:", exc)
            if items:
                break
            time.sleep(0.4)
        item = next((i for i in items if i.key == "Read from file..."), None)
        if item is not None:
            move_mouse(*centre(item.rect))
            settle(app, 2.2)
            shot(app, "03-hover-menu.png", crop=(0, 0, 960, 490))
            ui.close_popup()
        settle(app, 0.4)

    # -- 4. the card pinned ------------------------------------------
    if objects is not None:
        ui._activate(objects)
        time.sleep(0.4)
        # The dynamic row depends on what is selected: with a Sound
        # selected it is "Sound help", with a Pitch "Pitch help".  Any
        # button of that row will do.
        target = ui.find("Sound help") or ui.find("Pitch help") \
            or ui.find("View & Edit")
        if target is not None:
            move_mouse(*centre(target.rect))
            settle(app, 2.0)
            pin = app.card.pin_rect()
            if pin is not None:
                click(app, pin[0] + 6, pin[1] + 6)
                settle(app, 1.2)
                print("pinned      :", app.card.pinned)
                shot(app, "04-pinned.png", crop=(0, 0, 1010, 460))

    # -- 5. the side panel -------------------------------------------
    app.panel.show()
    app._refresh_panel()
    settle(app, 1.0)
    shot(app, "05-side-panel.png", crop=(755, 205, 1165, 795))
    app.panel.hide()
    app._dismiss_hover()

    # -- 6. a late model answer ---------------------------------------
    app.card.set_pinned(False)
    unknown = SimpleNamespace(
        name="Xyzzy Blorb", control_type="ButtonControl", automation_id="",
        hwnd=0, rect=(300, 300, 460, 340), window_title="Praat Objects",
        depth=0, enabled=True,
    )
    app.card.show("还不认识这个控件",
                  "（本地知识库没有这个控件，正在请模型回答，稍后会自动补上。）",
                  anchor=(380, 320), rect=(300, 300, 460, 340),
                  source="", signature=("acc", "6"))
    app._current_rect = (300, 300, 460, 340)
    app._last_key = "acc"
    settle(app, 0.4)
    # The reader keeps the pointer on the card, so the card stays open.
    card_rect = app._card_rect()
    if card_rect is not None:
        move_mouse((card_rect[0] + card_rect[2]) // 2,
                   (card_rect[1] + card_rect[3]) // 2)
    settle(app, 0.6)
    shot(app, "06-waiting-for-model.png", crop=(465, 225, 925, 620))
    app.advisor.advise(unknown, state=app.state, on_llm=app._on_llm_answer("acc"))
    print("waiting for the model ...")
    deadline = time.time() + 40
    while time.time() < deadline:
        app.pump()
        time.sleep(0.2)
        if "模型生成" in app.card.body.toPlainText():
            break
    settle(app, 0.5)
    shot(app, "07-late-model-answer.png", crop=(465, 225, 925, 620))

    # -- 7. a picture drawn by the image model ------------------------
    from dataclasses import replace

    from praatao.tutor.llm import LlmClient

    client = app.advisor.llm
    if client is not None:
        app.advisor.llm = LlmClient(replace(client.config, allow_imagegen=True))
    app.card.show("还不认识这个控件",
                  "（本地知识库没有这个控件，正在请模型回答，稍后会自动补上。）",
                  anchor=(380, 320), rect=(300, 300, 460, 340),
                  source="", signature=("acc", "7"))
    app._current_rect = (300, 300, 460, 340)
    app._last_key = "acc"
    card_rect = app._card_rect()
    if card_rect is not None:
        move_mouse((card_rect[0] + card_rect[2]) // 2,
                   (card_rect[1] + card_rect[3]) // 2)
    settle(app, 0.6)
    app.advisor.advise(unknown, state=app.state, on_llm=app._on_llm_answer("acc"),
                       on_image=app._on_llm_image("acc"))
    print("waiting for the picture (about 20 s) ...")
    deadline = time.time() + 120
    while time.time() < deadline:
        app.pump()
        time.sleep(0.3)
        try:
            if app.card.image_label.isVisible():
                break
        except Exception:
            pass
    settle(app, 0.8)
    shot(app, "08-generated-picture.png", crop=(465, 225, 925, 640))

    # -- put the desktop back the way it was --------------------------
    if editor is not None and editor_home is not None:
        restore_window(editor.hwnd, editor_home)
    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

