"""The settings the student can change in the Praatao settings window."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from praatao.settings import LANG_EN, LANG_ZH, Settings


class SettingsTests(unittest.TestCase):
    def test_defaults_are_offline_friendly(self) -> None:
        settings = Settings()
        self.assertEqual(settings.lang, LANG_ZH)
        self.assertTrue(settings.use_llm)
        self.assertFalse(settings.allow_vision)

    def test_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            settings = Settings(lang=LANG_EN, use_llm=False, allow_vision=True)
            self.assertTrue(settings.save(path))
            again = Settings.load(path)
            self.assertEqual(again.lang, LANG_EN)
            self.assertFalse(again.use_llm)
            self.assertTrue(again.allow_vision)

    def test_a_broken_file_gives_the_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            path.write_text("{not json", encoding="utf-8")
            settings = Settings.load(path)
            self.assertEqual(settings.lang, LANG_ZH)
            self.assertTrue(settings.use_llm)

    def test_an_unknown_language_falls_back(self) -> None:
        settings = Settings(lang="kl")
        self.assertEqual(settings.lang, LANG_ZH)

    def test_the_file_is_human_readable(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            Settings(lang=LANG_ZH).save(path)
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["lang"], "zh")
            self.assertIn("use_llm", data)


class SettingsWindowTests(unittest.TestCase):
    """The standalone window (only with the Qt front-end)."""

    def setUp(self) -> None:
        try:
            from PySide6 import QtWidgets

            from praatao.ui.qt.host import qt_available
        except Exception:  # pragma: no cover
            self.skipTest("PySide6 is not installed")
        if not qt_available():
            self.skipTest("PySide6 is not installed")
        self.qt_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_the_window_offers_language_and_model_switches(self) -> None:
        from praatao.ui.qt.settings import QtSettingsWindow

        window = QtSettingsWindow(None, lang="zh", settings=Settings())
        values = window.values()
        self.assertEqual(values["lang"], "zh")
        self.assertTrue(values["use_llm"])
        self.assertFalse(values["allow_vision"])

        window.language_box.setCurrentIndex(
            window.language_box.findData("en")
        )
        window.llm_box.setChecked(False)
        self.assertEqual(window.values()["lang"], "en")
        self.assertFalse(window.values()["use_llm"])


class ModelSwitchTests(unittest.TestCase):
    """The model really is off when the student says so.

    The advisor falls back to an environment-configured client when it
    gets ``None``, so "off" has to be handed over as the client that
    answers nothing.
    """

    @classmethod
    def setUpClass(cls) -> None:
        try:
            from PySide6 import QtWidgets
        except Exception:  # pragma: no cover
            raise unittest.SkipTest("PySide6 is not installed")
        cls.qt_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def make_app(self, use_llm: bool):
        import run as praatao_run

        app = praatao_run.Praatao(lang="zh", use_llm=use_llm, ui_backend="qt")
        self.addCleanup(app.quit)
        return app

    def test_no_llm_keeps_the_model_off(self) -> None:
        app = self.make_app(use_llm=False)
        self.assertFalse(app.advisor.llm.available())

    def test_switching_the_model_off_in_the_window_works(self) -> None:
        app = self.make_app(use_llm=True)
        from praatao.settings import Settings

        app._apply_settings(Settings(lang="zh", use_llm=False))
        self.assertFalse(app.advisor.llm.available())

    def test_switching_the_model_on_works(self) -> None:
        app = self.make_app(use_llm=False)
        from praatao.settings import Settings

        app._apply_settings(Settings(lang="zh", use_llm=True))
        # The credentials of this machine are read from the environment;
        # whether they exist is not the point here.
        self.assertIsNotNone(app.advisor.llm)


if __name__ == "__main__":
    unittest.main()
