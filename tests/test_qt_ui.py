"""Unit tests for the Qt front-end.

PySide6 is optional, so the whole module is skipped when it is not
installed.  What is checked here is the part that is easy to break: the
conversion of a plain text body into styled HTML, and the behaviour of the
card itself (show, pin, hide).
"""

from __future__ import annotations

import time
import unittest

try:  # pragma: no cover - PySide6 is optional
    from praatao.ui.qt.host import qt_available

    QT = qt_available()
except Exception:  # noqa: BLE001
    QT = False

if QT:  # pragma: no cover - depends on the machine
    from PySide6 import QtWidgets

    import run as praatao_run
    from praatao.ui.qt.hover import QtHoverCard, body_to_html
    from praatao.ui.qt.panel import QtSidePanel
    from praatao.ui.qt.spotlight import QtSpotlight


class BodyHtmlTests(unittest.TestCase):
    """The body of the advice is plain text; the card shows it as HTML."""

    def test_section_labels_become_bold(self) -> None:
        html = body_to_html("这是什么：Praat 的按钮。", "zh")
        self.assertIn("font-weight", html)
        self.assertIn("这是什么", html)
        self.assertIn("Praat 的按钮。", html)

    def test_english_labels(self) -> None:
        html = body_to_html("What it is: a button.", "en")
        self.assertIn("What it is", html)
        self.assertIn("a button.", html)

    def test_bullets_become_list_items(self) -> None:
        html = body_to_html("常见坑：\n• first trap\n• second trap", "zh")
        self.assertIn("first trap", html)
        self.assertIn("second trap", html)
        self.assertIn("•", html)

    def test_empty_body(self) -> None:
        self.assertIsInstance(body_to_html("", "zh"), str)


@unittest.skipUnless(QT, "PySide6 is not installed")
class CardTests(unittest.TestCase):
    """The card itself."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def make_card(self) -> "QtHoverCard":
        card = QtHoverCard(None, lang="zh")
        self.addCleanup(card.destroy)
        return card

    def test_show_and_hide(self) -> None:
        card = self.make_card()
        self.assertFalse(card.is_visible())
        card.show("标题", "这是什么：内容。", anchor=(100, 100),
                  rect=(100, 100, 200, 130), source="知识库", signature=("k", "s"))
        self.assertTrue(card.is_visible())
        card.hide()
        self.assertFalse(card.is_visible())

    def test_pin_marks_the_card(self) -> None:
        card = self.make_card()
        self.assertFalse(card.pinned)
        card.set_pinned(True)
        self.assertTrue(card.pinned)
        card.set_pinned(False)
        self.assertFalse(card.pinned)

    def test_body_can_be_replaced(self) -> None:
        card = self.make_card()
        card.show("标题", "旧内容", anchor=(10, 10), rect=(10, 10, 60, 40),
                  signature=("k", "s"))
        card.update_body("新内容", "来源")
        self.assertIn("新内容", card.body.toPlainText())
        self.assertIn("来源", card.source_label.text())

    def test_geometry_is_a_rectangle(self) -> None:
        card = self.make_card()
        card.show("标题", "内容", anchor=(10, 10), rect=(10, 10, 60, 40),
                  signature=("k", "s"))
        left, top, right, bottom = card.geometry()
        self.assertLess(left, right)
        self.assertLess(top, bottom)

    def test_button_rects_are_inside_the_card(self) -> None:
        card = self.make_card()
        card.show("标题", "内容", anchor=(10, 10), rect=(10, 10, 60, 40),
                  signature=("k", "s"))
        left, top, right, bottom = card.geometry()
        for getter in ("pin_rect", "close_rect"):
            rect = getattr(card, getter)()
            self.assertIsNotNone(rect)
            self.assertGreaterEqual(rect[0], left - 4)
            self.assertLessEqual(rect[2], right + 4)
            self.assertGreaterEqual(rect[1], top - 4)
            self.assertLessEqual(rect[3], bottom + 4)

    def test_pin_and_close_do_not_overlap(self) -> None:
        card = self.make_card()
        card.show("标题", "内容", anchor=(10, 10), rect=(10, 10, 60, 40),
                  signature=("k", "s"))
        pin = card.pin_rect()
        close = card.close_rect()
        self.assertLess(pin[2], close[0] + 1)

    def test_panel_and_spotlight_exist(self) -> None:
        panel = QtSidePanel(None, lang="zh")
        self.addCleanup(panel.destroy)
        panel.set_lessons([("01-first-sound", "你的第一个声音")])
        panel.set_lesson("标题", "正文", (0, 1))
        panel.set_state("3 obj")
        panel.set_notice("注意")
        panel.set_answer("答案")
        panel.show()
        self.assertTrue(panel.is_visible())
        panel.hide()
        self.assertFalse(panel.is_visible())

        spot = QtSpotlight(None)
        self.addCleanup(spot.destroy)
        spot.show((10, 10, 200, 100))
        self.assertTrue(spot.is_visible())
        spot.hide()
        self.assertFalse(spot.is_visible())


@unittest.skipUnless(QT, "PySide6 is not installed")
class ClickTests(unittest.TestCase):
    """The application owns the mouse, so that the pin button works.

    Windows gives the first click on an inactive window to activating it,
    so a button inside a tool window would never see its first click.  The
    application polls the mouse anyway, and decides there.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def make_app(self, show_card: bool = True):
        import run as praatao_run

        app = praatao_run.Praatao(lang="zh", use_llm=False, ui_backend="qt")
        self.addCleanup(app.quit)
        if show_card:
            app.card.show("标题", "内容", anchor=(200, 200),
                          rect=(200, 200, 320, 240),
                          source="测试", signature=("k", "s"))
            app._current_rect = (200, 200, 320, 240)
            app.pump()
        return app

    def test_click_on_the_pin_pins_the_card(self) -> None:
        app = self.make_app()
        pin = app.card.pin_rect()
        app._handle_click(pin[0] + 2, pin[1] + 2)
        app.pump()
        self.assertTrue(app.card.pinned)
        self.assertTrue(app._card_visible())

    def test_a_pinned_card_survives_a_click(self) -> None:
        app = self.make_app()
        app.card.set_pinned(True)
        app._handle_click(1800, 1000)
        app.pump()
        self.assertTrue(app._card_visible())

    def test_click_on_the_body_dismisses_the_card(self) -> None:
        app = self.make_app()
        left, top, _, _ = app._card_rect()
        app._handle_click(left + 60, top + 60)
        app.pump()
        self.assertFalse(app._card_visible())

    def test_click_on_the_close_button_dismisses_the_card(self) -> None:
        app = self.make_app()
        close = app.card.close_rect()
        app._handle_click(close[0] + 2, close[1] + 2)
        app.pump()
        self.assertFalse(app._card_visible())

    def test_click_away_dismisses_the_card(self) -> None:
        app = self.make_app()
        app._handle_click(1800, 1000)
        app.pump()
        self.assertFalse(app._card_visible())

    def test_the_card_disappears_two_seconds_after_the_pointer_leaves(self) -> None:
        import time

        app = self.make_app()
        app._update_auto_hide(1800, 1000)
        self.assertTrue(app._card_visible())
        time.sleep(2.4)
        app._update_auto_hide(1800, 1000)
        app.pump()
        self.assertFalse(app._card_visible())

    def test_the_pointer_on_the_card_keeps_the_card(self) -> None:
        """The pin button lives on the card.

        If the hover logic treated "the pointer is on our own card" as
        "the pointer left Praat", the card would dismiss itself before
        the user could reach the pin.
        """

        app = self.make_app()
        left, top, _, _ = app._card_rect()
        app._handle_hover(left + 60, top + 60)
        app.pump()
        self.assertTrue(app._card_visible())

    def test_a_click_shorter_than_the_tick_is_still_seen(self) -> None:
        """The mouse button is watched faster than the main tick.

        A quick click can be over before the 45 ms tick comes round; the
        separate 10 ms poll catches it.
        """

        app = self.make_app()
        seen: list[tuple[int, int]] = []
        original = app._handle_click

        def record(x: int, y: int) -> None:
            seen.append((x, y))
            original(x, y)

        app._handle_click = record
        app._last_mouse_down = False
        # Simulate the button being down for a moment.
        original_down = praatao_run.mouse_button_down
        praatao_run.mouse_button_down = lambda button=1: True
        try:
            app._mouse_poll()
        finally:
            praatao_run.mouse_button_down = original_down
        self.assertTrue(seen, "the click was not seen at all")

    def test_an_open_menu_survives_the_coach(self) -> None:
        """A menu the user opened must stay open.

        Two things close a menu by accident: running a Praat script (the
        state probe must not do that) and a UIA hit test over the menu
        bar (the coach must not do that either while a menu is open).
        """

        from praatao.sensors import uia as uia_module
        from praatao.sensors.uia import PraatUI

        ui = PraatUI()
        objects = ui.objects_window()
        if objects is None:
            self.skipTest("Praat is not running")

        def open_menus() -> int:
            control = ui._control_from_window(objects)
            if control is None:
                return 0
            return len([
                node for node, _depth in ui._iter_controls(control)
                if uia_module._text(node, "ControlTypeName") == "MenuControl"
            ])

        app = self.make_app()
        app.host.after(praatao_run.MOUSE_POLL_MS, app._mouse_poll)
        app.host.after(45, app._tick)
        trace: list[str] = []
        original_hover = app._handle_hover

        def traced_hover(x: int, y: int) -> None:
            original_hover(x, y)
            trace.append(f"hover menu_open={app._menu_open()}")

        app._handle_hover = traced_hover
        items: list = []
        for _attempt in range(3):
            try:
                items = ui.open_menu(objects, "Open", keep_open=True)
            except Exception:  # noqa: BLE001
                self.skipTest("could not open the menu")
            if items:
                break
            time.sleep(0.4)
        self.assertTrue(items)
        self.assertEqual(open_menus(), 1)

        deadline = time.time() + 3.0
        while time.time() < deadline:
            app.pump()
            time.sleep(0.02)
        if open_menus() != 1:
            self.fail(f"the coach closed the open menu; trace={trace[-12:]}")
        ui.close_popup()

    def test_a_menu_item_is_explained_without_closing_the_menu(self) -> None:
        """The pointer may rest on a menu item: explain it, keep the menu."""

        import ctypes

        from praatao.sensors import uia as uia_module
        from praatao.sensors.uia import PraatUI

        ui = PraatUI()
        objects = ui.objects_window()
        if objects is None:
            self.skipTest("Praat is not running")

        def open_menus() -> int:
            control = ui._control_from_window(objects)
            if control is None:
                return 0
            return len([
                node for node, _depth in ui._iter_controls(control)
                if uia_module._text(node, "ControlTypeName") == "MenuControl"
            ])

        app = self.make_app(show_card=False)
        app.host.after(praatao_run.MOUSE_POLL_MS, app._mouse_poll)
        app.host.after(45, app._tick)
        items: list = []
        for _attempt in range(3):
            try:
                items = ui.open_menu(objects, "Open", keep_open=True)
            except Exception:  # noqa: BLE001
                self.skipTest("could not open the menu")
            if items:
                break
            time.sleep(0.4)
        item = next((i for i in items if i.key == "Read from file..."), None)
        if item is None:
            ui.close_popup()
            self.skipTest("the menu has no 'Read from file...' item")
        ctypes.windll.user32.SetCursorPos(
            (item.rect[0] + item.rect[2]) // 2,
            (item.rect[1] + item.rect[3]) // 2,
        )
        deadline = time.time() + 2.5
        while time.time() < deadline:
            app.pump()
            time.sleep(0.02)
        self.assertEqual(open_menus(), 1, "the coach closed the open menu")
        self.assertTrue(app._card_visible(), "the menu item was not explained")
        ui.close_popup()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
