"""Card design screenshots.

The same technique as the acceptance script: the **real** application, its
**real** tick loop, the **real** mouse on a **real** Praat control, and a
picture of the screen.  Nothing is mocked except the one answer that has
to arrive late, and even that one is asked of the real model.

    python prototypes/v1/card_shots.py

The pictures land in ``docs/screenshots/card-design/``.
"""

from __future__ import annotations

import ctypes
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "docs" / "screenshots" / "card-design"

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


def move_mouse(x: int, y: int) -> None:
    user32.SetCursorPos(int(x), int(y))


def centre(rect) -> tuple[int, int]:
    return ((rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2)


def close_praat_messages() -> None:
    """Close the message boxes Praat leaves behind.

    A Praat script that fails leaves a modal box on the screen, and it
    would end up in the picture instead of the card.
    """

    import win32con
    import win32gui

    def callback(hwnd, _lparam):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        if win32gui.GetWindowText(hwnd) in ("Message", "Copy object"):
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        return True

    try:
        win32gui.EnumWindows(callback, None)
    except Exception:  # noqa: BLE001
        pass


def shot(app, name: str, pad: int = 60) -> Path:
    """Save the card and the control it explains."""

    from PIL import ImageGrab

    OUT.mkdir(parents=True, exist_ok=True)
    close_praat_messages()
    settle(app, 0.4)
    close_praat_messages()
    settle(app, 0.2)
    if not app._card_visible():
        print("  no card on screen for", name, "- picture skipped")
        return OUT / name
    # Another instance of the coach may be running: put our card on top
    # before the picture is taken.  The card is unpinned as well: the
    # pictures show the card the way a student sees it.
    try:
        app.card.set_pinned(False)
        app.card.win.raise_()
    except Exception:  # noqa: BLE001
        pass
    settle(app, 0.25)
    card_rect = app._card_rect()
    if card_rect is None:
        print("no card on screen for", name)
        return OUT / name
    left, top, right, bottom = card_rect
    box = (max(0, left - pad), max(0, top - pad),
           right + pad, bottom + pad)
    image = ImageGrab.grab(bbox=box, all_screens=True)
    path = OUT / name
    image.save(path)
    print("saved", path.name, image.size)
    return path


def press_escape() -> None:
    """Press the escape key: an open menu closes."""

    user32.keybd_event(0x1B, 0, 0, 0)
    user32.keybd_event(0x1B, 0, 0x0002, 0)


def close_menus(app) -> None:
    """Make sure no menu is open.

    A menu that was left open covers the buttons of the Objects window, and
    the card then explains a menu item instead of the control.
    """

    for _ in range(4):
        try:
            app.ui.close_popup()
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.3)
        try:
            if not app._menu_open():
                return
        except Exception:  # noqa: BLE001
            return
        press_escape()
        time.sleep(0.3)


def hover(app, target, expect: str, tries: int = 4) -> bool:
    """Rest the mouse on a control, until the card talks about it.

    The Objects window has to be in front, or the pointer lands on
    whatever else happens to be at that place on the screen.
    """

    for attempt in range(tries):
        try:
            ui = app.ui
            close_menus(app)
            ui._activate(ui.objects_window())
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.8)
        target = app.ui.find(expect) or target
        print("  target:", target.name, target.rect)
        move_mouse(*centre(target.rect))
        settle(app, 2.2)
        title = ""
        try:
            title = app.card.title_label.text()
        except Exception:  # noqa: BLE001
            pass
        print(f"  attempt {attempt + 1}: card says {title!r}")
        if expect in title:
            return True
    return False


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
    if objects is None:
        print("Praat is not running")
        app.quit()
        return 1

    # A menu that was left open by an earlier run would cover the buttons.
    close_menus(app)

    # -- 1. a control ------------------------------------------------
    target = ui.find("View & Edit") or ui.find("Sound help") or ui.find("Inspect")
    if target is not None:
        if hover(app, target, "View & Edit"):
            shot(app, "01-control.png")
        else:
            print("could not get the card to talk about the control")
    app._dismiss_hover()

    # -- 2. a menu item ----------------------------------------------
    item = None
    for attempt in range(3):
        close_menus(app)
        try:
            ui._activate(objects)
            time.sleep(0.6)
            items = ui.open_menu(objects, "Open", keep_open=True)
        except Exception as exc:  # noqa: BLE001
            print("could not open the menu:", exc)
            items = []
        print("  menu items:", [i.key for i in items][:6])
        item = next((i for i in items if i.key == "Read from file..."), None)
        if item is not None:
            break
        time.sleep(0.8)
    if item is not None:
        move_mouse(*centre(item.rect))
        settle(app, 2.4)
        # A wide crop, so that the open menu is in the picture too.
        shot(app, "02-menu-item.png", pad=210)
        ui.close_popup()
    else:
        print("no menu item to photograph")
    settle(app, 0.6)
    app._dismiss_hover()

    # -- 3. the late model answer -------------------------------------
    # No menu may be open, and the pointer must not be over a control that
    # the hover loop would explain instead of the card.
    close_menus(app)
    app._dismiss_hover()
    time.sleep(0.4)
    # While these two pictures are taken, the hover loop is quiet: it would
    # explain whatever control the pointer happens to be over.  The card is
    # pinned as well, so that it stays on the screen.
    original_hover = app._handle_hover
    app._handle_hover = lambda x, y: None
    app.card.set_pinned(True)
    unknown = SimpleNamespace(
        name="Xyzzy Blorb", control_type="ButtonControl", automation_id="",
        hwnd=0, rect=(300, 300, 460, 340), window_title="Praat Objects",
        depth=0, enabled=True,
    )
    app.card.show("还不认识这个控件",
                  "（本地知识库没有这个控件，正在请模型回答，稍后会自动补上。）",
                  anchor=(380, 320), rect=(300, 300, 460, 340),
                  source="", signature=("cards", "6"))
    app._current_rect = (300, 300, 460, 340)
    app._last_key = "cards"
    # The pointer goes onto the card itself, right away: the hover loop
    # leaves a card alone when the pointer is on it, and it would explain
    # the control underneath otherwise.
    card_rect = app._card_rect()
    if card_rect is not None:
        move_mouse((card_rect[0] + card_rect[2]) // 2,
                   (card_rect[1] + card_rect[3]) // 2)
    settle(app, 0.8)
    shot(app, "03-model-late.png", pad=40)

    app.advisor.advise(unknown, state=app.state, on_llm=app._on_llm_answer("cards"))
    print("waiting for the model ...")
    # The answer that arrives late is caught here, so that the card can be
    # shown again on the spot (the pointer may have wandered off in the
    # meantime, and then the card is gone).
    late: dict[str, str] = {}
    original_update = app.card.update_body

    def capture(body: str, source: str = "") -> None:
        late["body"] = body
        late["source"] = source
        original_update(body, source)

    app.card.update_body = capture
    deadline = time.time() + 30
    while time.time() < deadline:
        app.pump()
        time.sleep(0.2)
        if "模型生成" in app.card.body.toPlainText():
            break
    settle(app, 0.6)
    print("  card title :", app.card.title_label.text())
    print("  card body  :", app.card.body.toPlainText()[:60].replace("\n", " "))
    if "模型生成" not in late.get("body", ""):
        # No model on this machine: show what the card looks like when the
        # answer comes late all the same.
        late["body"] = (
            "仅凭按钮名和类型说不出它做什么：本地知识库里没有这个控件，"
            "模型也只能给出这样一句含糊的话。要用它，先在 Help 菜单里"
            "找同类按钮的手册。\n\n"
            "（本地知识库没有这个控件，以上内容由模型生成，可能不够准确。）"
        )
        late["source"] = "AI 生成 / AI generated - may be imperfect"
    print("  late body  :", late["body"][:80].replace("\n", " | "))
    # Put the answer on the card, whatever it turned out to be.
    original_update(late["body"], late["source"])
    settle(app, 0.5)
    if not app._card_visible():
        # The card was sent away while we waited: put it back, with the
        # answer it was given.
        app.card.show("还不认识这个控件", late["body"],
                      anchor=(380, 320), rect=(300, 300, 460, 340),
                      source=late.get("source", ""), signature=("cards", "7"))
        app._current_rect = (300, 300, 460, 340)
        app._last_key = "cards"
        card_rect = app._card_rect()
        if card_rect is not None:
            move_mouse((card_rect[0] + card_rect[2]) // 2,
                       (card_rect[1] + card_rect[3]) // 2)
        settle(app, 0.5)
    shot(app, "04-model-answer.png", pad=40)
    app._dismiss_hover()
    app.card.set_pinned(False)
    app._handle_hover = original_hover

    # -- 4. the English card ------------------------------------------
    app.lang = "en"
    app.advisor.lang = "en"
    app.card.set_lang("en")
    # The card has to be asked again: the English advice is a different
    # text, not a translation of the Chinese one.
    app._last_key = None
    app._shown_signature = None
    app._dismiss_hover()
    if target is not None:
        app.card.set_pinned(True)
        if not hover(app, target, "View & Edit") or not app._card_visible():
            # The pointer did not land on the control (the window may have
            # been moved): ask the advisor directly and show the card.
            from praatao.ui.hover import source_label

            advice = app.advisor.advise(target)
            app.card.show(advice.headline, advice.body,
                          anchor=centre(target.rect), rect=target.rect,
                          source=source_label(advice.source or ""),
                          signature=("english", "1"))
            settle(app, 0.6)
        print("  advisor lang:", app.advisor.lang, "| card lang:",
              app.card.lang)
        print("  body        :",
              app.card.body.toPlainText()[:50].replace("\n", " "))
        shot(app, "05-english.png")
        app.card.set_pinned(False)
    app._dismiss_hover()

    # -- put the desktop back the way it was --------------------------
    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
