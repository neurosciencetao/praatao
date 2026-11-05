"""End-to-end tests against a live Praat.

These are skipped automatically when Praat is not running.  They exercise the
whole chain: UIA hit test -> knowledge base -> advisor -> advice text.
"""

from __future__ import annotations

import unittest

from praatao.sensors.uia import PraatUI, normalize_name, praat_available
from praatao.tutor.advisor import Advisor
from praatao.tutor.kb import load_default


def _praat_in_front(ui: PraatUI, window) -> bool:
    """Is the Praat window really the frontmost thing on the desktop?

    The coach only explains Praat, and that rule is enforced by looking at
    the frontmost window: when another application covers Praat, a hit
    test over the Praat rectangle would (correctly) return nothing.
    """

    import win32gui

    rect = window.rect
    hwnd = win32gui.WindowFromPoint(
        ((rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2)
    )
    class_name = (win32gui.GetClassName(hwnd) or "").casefold()
    return "praat" in class_name or class_name == "#32768"


@unittest.skipUnless(praat_available(), "Praat is not running")
class LivePipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui = PraatUI()
        cls.kb = load_default()
        cls.advisor = Advisor(cls.kb, lang="zh")

    def setUp(self):
        window = self.ui.objects_window()
        if window is None:
            self.skipTest("Praat is not running")
        # Bring Praat forward: a hit test only reports Praat when Praat
        # is the frontmost window at that point.
        self.ui._activate(window)

    def test_element_at_point_returns_something(self):
        window = self.ui.objects_window()
        self.assertIsNotNone(window)
        if not _praat_in_front(self.ui, window):
            self.skipTest("Praat could not be brought to the front")
        left, top, right, bottom = window.rect
        element = self.ui.element_at_point((left + right) // 2, (top + bottom) // 2)
        self.assertIsNotNone(element)
        self.assertTrue(element.name)

    def test_objects_window_is_found(self):
        window = self.ui.objects_window()
        self.assertIsNotNone(window)
        self.assertEqual(window.title, "Praat Objects")

    def test_known_controls_are_found_by_name(self):
        # The fixed buttons are always there; the dynamic row only appears
        # when an object is selected, so it is checked against the tree.
        for name in ("Inspect", "Info", "Remove", "Rename...", "Copy..."):
            self.assertIsNotNone(self.ui.find(name), f"{name} not found")

        window = self.ui.objects_window()
        visible = {normalize_name(e.name) for e in self.ui.tree(window, max_depth=4)
                   if e.name}
        if "View & Edit" in visible:
            self.assertIsNotNone(self.ui.find("View & Edit"))

    def test_element_at_point_returns_something(self):
        window = self.ui.objects_window()
        self.assertIsNotNone(window)
        if not _praat_in_front(self.ui, window):
            self.skipTest("Praat could not be brought to the front")
        left, top, right, bottom = window.rect
        element = self.ui.element_at_point((left + right) // 2, (top + bottom) // 2)
        self.assertIsNotNone(element)
        self.assertTrue(element.name)

    def test_kb_has_content(self):
        self.assertGreater(len(self.kb), 20, "knowledge base looks empty")

    def test_kb_covers_the_real_controls(self):
        """Every named control Praat shows should ideally be explainable."""
        window = self.ui.objects_window()
        self.assertIsNotNone(window)
        names = [normalize_name(e.name) for e in self.ui.tree(window, max_depth=4) if e.name]
        hit = [n for n in names if self.kb.lookup(n) is not None]
        self.assertGreater(len(hit), 3, f"KB only matched {hit}")

    def test_advisor_produces_text_for_a_known_control(self):
        element = self.ui.find("View & Edit")
        if element is None:
            self.skipTest("no Sound selected, so no View & Edit button")
        advice = self.advisor.advise(element)
        self.assertTrue(advice.headline)
        self.assertTrue(advice.body)
        self.assertIn(advice.source, ("kb", "llm", "kb+llm"))

    def test_advisor_never_raises_for_unknown_controls(self):
        class Fake:
            name = "Totally Unknown Widget"
            control_type = "ButtonControl"
            automation_id = ""
            hwnd = 0
            rect = (0, 0, 10, 10)
            window_title = "Praat Objects"
            depth = 2

        advice = self.advisor.advise(Fake())
        self.assertTrue(advice.body)


class OfflineTests(unittest.TestCase):
    """These must pass with Praat closed."""

    def test_kb_loads(self):
        kb = load_default()
        self.assertGreater(len(kb), 0)

    def test_normalize_name_is_shared(self):
        from praatao.tutor.kb import normalize_key

        for raw in ("\u202f\u202f   Draw  >", "Read from file...\tCtrl-O",
                    "1. Sound demo_vowel", "Objects:"):
            self.assertEqual(normalize_key(raw), normalize_name(raw).casefold())


if __name__ == "__main__":
    unittest.main()
