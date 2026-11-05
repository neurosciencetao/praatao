"""Two rules the student pointed out.

1. A modal dialog has to be recognised: the controls inside it are what
   the student is asking about, not the picture behind the dialog.
2. Praat in the background means no help: the coach explains Praat only
   while the student is working in Praat.
"""

from __future__ import annotations

import unittest

from praatao.sensors import uia as uia_module
from praatao.sensors.uia import Element
from praatao.tutor.advisor import Advisor
from praatao.tutor.kb import load_default


class _FakeWin32:
    """Just enough of ``win32gui`` to describe a foreign window."""

    def __init__(self, hwnd: int = 4242, class_name: str = "SomeClass",
                 title: str = "", root: int = 0) -> None:
        self.hwnd = hwnd
        self.class_name = class_name
        self.title = title
        self.root = root

    def GetForegroundWindow(self) -> int:
        return self.hwnd

    def GetClassName(self, _hwnd: int) -> str:
        return self.class_name

    def GetWindowText(self, _hwnd: int) -> str:
        return self.title

    def GetAncestor(self, _hwnd: int, _ga: int) -> int:
        return self.root


class FocusGuardTests(unittest.TestCase):
    """``praat_has_focus`` must not be fooled by another program."""

    def setUp(self) -> None:
        self._win32 = uia_module.win32gui
        self._process = uia_module._process_is_praat

    def tearDown(self) -> None:
        uia_module.win32gui = self._win32
        uia_module._process_is_praat = self._process

    def test_a_foreign_window_titled_praat_is_not_praat(self) -> None:
        # A browser whose tab is called "Praat ..." must not make the
        # coach believe the student is working in Praat.
        uia_module.win32gui = _FakeWin32(
            class_name="Chrome_WidgetWin_1",
            title="Praat 友好界面与智能辅助 - DeepSeek Harness",
        )
        uia_module._process_is_praat = lambda _hwnd: False
        self.assertFalse(uia_module.praat_has_focus())

    def test_a_praat_window_is_praat(self) -> None:
        uia_module.win32gui = _FakeWin32(
            class_name="PraatShell1 Praat", title="Praat Objects"
        )
        uia_module._process_is_praat = lambda _hwnd: True
        self.assertTrue(uia_module.praat_has_focus())

    def test_a_praat_child_window_counts(self) -> None:
        # The picture window is a child of the editor.
        uia_module.win32gui = _FakeWin32(
            class_name="PraatChildWindow1 Praat",
            title="Praat Picture",
            root=99,
        )
        uia_module._process_is_praat = lambda _hwnd: False
        self.assertTrue(uia_module.praat_has_focus())


class DialogEntryTests(unittest.TestCase):
    """A control inside a modal dialog is explained by the dialog."""

    def setUp(self) -> None:
        self.advisor = Advisor(load_default(), lang="zh")

    @staticmethod
    def _element(name: str, window_title: str) -> Element:
        return Element(
            name=name,
            control_type="TextControl",
            automation_id="",
            hwnd=0,
            rect=(10, 20, 200, 60),
            window_title=window_title,
            depth=2,
            enabled=True,
        )

    def test_a_field_of_a_dialog_is_explained_by_the_dialog(self) -> None:
        advice = self.advisor.advise(
            self._element("Formant ceiling (Hz):", "Formant settings")
        )
        self.assertEqual(advice.entries[0].id, "formant-settings")

    def test_a_control_with_its_own_entry_keeps_it(self) -> None:
        advice = self.advisor.advise(
            self._element("Help", "Formant settings")
        )
        self.assertNotEqual(advice.entries[0].id, "formant-settings")

    def test_the_objects_window_title_is_never_used(self) -> None:
        entry = self.advisor._lookup_dialog_entry(
            self._element("Something", "Praat Objects")
        )
        self.assertIsNone(entry)

    def test_the_picture_window_title_is_never_used(self) -> None:
        entry = self.advisor._lookup_dialog_entry(
            self._element("Something", "Praat Picture")
        )
        self.assertIsNone(entry)


class CanvasBehindDialogTests(unittest.TestCase):
    """The drawing area must not win while a dialog is on top of it."""

    def test_the_canvas_is_skipped_when_another_window_is_on_top(self) -> None:
        import run as praatao_run

        app = praatao_run.Praatao.__new__(praatao_run.Praatao)

        class _Region:
            hwnd = 1000
            canvas_hwnd = 1001
            rect = (0, 0, 800, 600)

        class _Canvas:
            def region_at(self, _x: int, _y: int):
                return _Region()

        app.canvas = _Canvas()
        original = uia_module.top_window_at
        uia_module.top_window_at = lambda _x, _y: 2000   # the dialog
        try:
            self.assertIsNone(app._canvas_under_cursor(10, 10))
        finally:
            uia_module.top_window_at = original

    def test_the_canvas_is_used_when_it_is_the_window_on_top(self) -> None:
        import run as praatao_run

        app = praatao_run.Praatao.__new__(praatao_run.Praatao)

        class _Region:
            hwnd = 1000
            canvas_hwnd = 1001
            rect = (0, 0, 800, 600)

        class _Canvas:
            def region_at(self, _x: int, _y: int):
                return _Region()

        app.canvas = _Canvas()
        original = uia_module.top_window_at
        uia_module.top_window_at = lambda _x, _y: 1000   # the canvas' own window
        try:
            self.assertIsNotNone(app._canvas_under_cursor(10, 10))
        finally:
            uia_module.top_window_at = original


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
