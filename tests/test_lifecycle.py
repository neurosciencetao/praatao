"""Three things the student noticed.

1. Closing the coach must leave nothing behind.
2. Starting the coach twice must not leave two coaches behind.
3. The row under the pointer decides what the drawing area is called.
"""

from __future__ import annotations

import unittest

from praatao.sensors.canvas import CanvasSensor


def _picture() -> "object":
    """A picture that looks like Praat's sound editor.

    From the top: the waveform (blue-green), then the formants (red
    dots), then the pitch curve (blue), then the axes.
    """

    from PIL import Image, ImageDraw

    image = Image.new("RGB", (400, 400), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    # The waveform: a filled blue-green band in the top quarter.
    draw.rectangle((0, 40, 400, 120), fill=(0, 110, 130))
    # The formants: red dots in the middle.
    for x in range(10, 400, 20):
        draw.point((x, 200), fill=(220, 0, 0))
        draw.point((x, 215), fill=(220, 0, 0))
    # The pitch curve: a blue line lower down.
    draw.line((0, 300, 400, 300), fill=(0, 0, 230), width=2)
    return image


class CanvasRowTests(unittest.TestCase):
    """The pointer says which row of the picture is meant."""

    def setUp(self) -> None:
        self.sensor = CanvasSensor()
        self.picture = _picture()

    def _kind_at(self, y: int) -> str:
        guess = self.sensor.classify_at(self.picture, y / 400.0)
        return guess.kind

    def test_the_waveform_row(self) -> None:
        self.assertEqual(self._kind_at(80), "waveform")

    def test_the_formant_row(self) -> None:
        self.assertEqual(self._kind_at(207), "formants")

    def test_the_pitch_row(self) -> None:
        self.assertEqual(self._kind_at(300), "pitch")

    def test_an_empty_row_says_nothing(self) -> None:
        self.assertEqual(self._kind_at(370), "unknown")

    def test_the_whole_picture_is_still_guessed(self) -> None:
        # The old way has to keep working: the picture as a whole.
        guess = self.sensor.classify(self.picture)
        self.assertIn(guess.kind, ("waveform", "pitch", "spectrogram", "unknown"))


class SingleInstanceTests(unittest.TestCase):
    """Only one coach at a time."""

    def test_the_second_copy_stands_down(self) -> None:
        from praatao.launcher import SingleInstance

        calls: list[str] = []
        first = SingleInstance(lambda: calls.append("show"))
        self.assertTrue(first.acquire(), "the first copy is the coach")
        second = SingleInstance(lambda: calls.append("show"))
        self.assertFalse(second.acquire(), "the second copy stands down")
        first.release()

    def test_the_mutex_is_released_again(self) -> None:
        from praatao.launcher import SingleInstance

        first = SingleInstance()
        self.assertTrue(first.acquire())
        first.release()
        second = SingleInstance()
        self.assertTrue(second.acquire(), "after the first one left")
        second.release()


class CardScrollTests(unittest.TestCase):
    """A long card has to be readable.

    The wheel scrolls it and the scroll bar can be dragged; neither may
    make the card disappear.
    """

    def setUp(self) -> None:
        try:
            from PySide6 import QtWidgets
        except Exception:  # pragma: no cover - no Qt
            self.skipTest("PySide6 is not installed")
        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_the_card_has_a_scroll_bar_and_knows_where_it_is(self) -> None:
        from praatao.ui.qt.hover import QtHoverCard

        card = QtHoverCard(None, lang="zh")
        self.addCleanup(card.destroy)
        body = "现在 已选中 Sound demo_vowel\n" + (
            "这是一段很长的说明文字，用来把卡片撑出滚动条。" * 12
        )
        card.show("测试标题", body, anchor=(100, 100), rect=(0, 0, 800, 600))
        self.app.processEvents()
        bar = card.body.verticalScrollBar()
        self.assertTrue(bar.isVisible(), "the card should have a scroll bar")
        rect = card.scroll_rect()
        self.assertIsNotNone(rect, "the card should know where its scroll bar is")
        self.assertGreater(rect[2] - rect[0], 0)

    def test_the_body_keeps_its_mouse_events(self) -> None:
        # The body has to get the wheel, so it may not be transparent for
        # the mouse.
        from PySide6 import QtCore

        from praatao.ui.qt.hover import QtHoverCard

        card = QtHoverCard(None, lang="zh")
        self.addCleanup(card.destroy)
        transparent = card.body.testAttribute(
            QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )
        self.assertFalse(transparent, "the body has to receive the wheel")


class ClosingTheWindowTests(unittest.TestCase):

    def setUp(self) -> None:
        try:
            from PySide6 import QtWidgets
        except Exception:  # pragma: no cover - no Qt
            self.skipTest("PySide6 is not installed")
        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_closing_the_panel_calls_the_callback(self) -> None:
        from praatao.ui.qt.panel import QtSidePanel

        panel = QtSidePanel(None, lang="zh")
        self.addCleanup(panel.destroy)
        calls: list[str] = []
        panel.on_close = lambda: calls.append("closed")
        panel.win.close()
        self.app.processEvents()
        self.assertEqual(calls, ["closed"])

    def test_closing_the_settings_window_calls_the_callback(self) -> None:
        from praatao.ui.qt.settings import QtSettingsWindow

        window = QtSettingsWindow(None, lang="zh")
        self.addCleanup(window.destroy)
        calls: list[str] = []
        window.on_close = lambda: calls.append("closed")
        window.win.close()
        self.app.processEvents()
        self.assertEqual(calls, ["closed"])

    def test_the_greeting_window_calls_the_callback(self) -> None:
        from praatao.launcher import Toast

        toast = Toast(None, seconds=30)
        self.addCleanup(toast.destroy)
        calls: list[str] = []
        toast.on_close = lambda: calls.append("closed")
        toast.win.close()
        self.app.processEvents()
        self.assertEqual(calls, ["closed"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
