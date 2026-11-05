"""The beginner's entry point: one double-click has to be enough.

These tests cover the parts that can be checked without disturbing the
running Praat: the answers the launcher gives, the greeting window and
the tray icon.
"""

from __future__ import annotations

import unittest

from praatao import launcher


class PraatStartTests(unittest.TestCase):
    """What the launcher says about Praat."""

    def test_praat_running_is_a_boolean(self) -> None:
        self.assertIsInstance(launcher.praat_running(), bool)

    def test_ensure_praat_answers_with_a_dictionary(self) -> None:
        result = launcher.ensure_praat(start_if_missing=False)
        self.assertIsInstance(result, dict)
        if not result.get("failed"):
            self.assertTrue(result.get("already") or result.get("started"))

    def test_start_if_missing_false_never_starts_anything(self) -> None:
        result = launcher.ensure_praat(start_if_missing=False)
        if result.get("failed"):
            self.assertNotIn("started", result)


class ToastTests(unittest.TestCase):
    """The little window that says "it works"."""

    @classmethod
    def setUpClass(cls) -> None:
        try:
            from PySide6 import QtWidgets
        except Exception:  # pragma: no cover
            raise unittest.SkipTest("PySide6 is not installed")
        cls.qt_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_a_message_is_shown_and_can_be_hidden(self) -> None:
        toast = launcher.Toast(None, seconds=0.2)
        self.addCleanup(toast.destroy)
        toast.show_message("Praatao 助教已启动", "在 Praat 里把鼠标停在按钮上。")
        self.assertEqual(toast.title.text(), "Praatao 助教已启动")
        self.assertIn("Praat", toast.body.text())
        toast.hide()

    def test_an_empty_body_is_hidden(self) -> None:
        toast = launcher.Toast(None)
        self.addCleanup(toast.destroy)
        toast.show_message("只有标题", "")
        self.assertFalse(toast.body.isVisible())


class TrayTests(unittest.TestCase):
    """The tray icon is where a beginner finds the controls."""

    @classmethod
    def setUpClass(cls) -> None:
        try:
            from PySide6 import QtWidgets
        except Exception:  # pragma: no cover
            raise unittest.SkipTest("PySide6 is not installed")
        cls.qt_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_the_tray_offers_the_commands(self) -> None:
        seen: list[str] = []
        tray = launcher.Tray(None, on_command=seen.append, lang="zh")
        self.addCleanup(tray.destroy)
        self.assertIsNotNone(tray.icon)
        for action in (tray.panel_action, tray.settings_action, tray.quit_action):
            action.trigger()
        self.assertIn("panel", seen)
        self.assertIn("settings", seen)
        self.assertIn("quit", seen)

    def test_a_broken_callback_does_not_crash(self) -> None:
        def boom(_name: str) -> None:
            raise RuntimeError("no")

        tray = launcher.Tray(None, on_command=boom, lang="en")
        self.addCleanup(tray.destroy)
        tray.panel_action.trigger()   # must not raise


if __name__ == "__main__":
    unittest.main()
