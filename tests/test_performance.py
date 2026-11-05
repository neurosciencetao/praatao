"""Tests for the performance work.

Everything that was changed to make the hover coach faster has to keep
its old answers, and the new shortcuts have to keep their promises.
The numbers in ``docs/15-performance.md`` come from
``prototypes/v1/experiments/perf_probe.py``; the tests here check the
*behaviour*, not the timings (a slow machine must not fail a test).
"""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import run as praatao_run  # noqa: E402
from praatao.sensors.praat_state import PraatStateProbe  # noqa: E402
from praatao.sensors.uia import (  # noqa: E402
    PraatUI,
    praat_available,
    praat_has_focus,
    seconds_since_last_input,
)
from praatao.tutor.kb import KnowledgeBase, KnowledgeEntry, load_default, normalize_key  # noqa: E402


# --------------------------------------------------------------------------
# the knowledge base index
# --------------------------------------------------------------------------
class KnowledgeBaseIndexTests(unittest.TestCase):
    """The index must give exactly the answers the old scan gave."""

    def _old_lookup(self, kb, label, control_type=None):
        """The implementation that was in the code before the index."""

        key = normalize_key(label)
        if not key:
            return None
        exact = kb._by_alias.get(key)
        if exact:
            return kb._choose(exact, control_type)
        best_len = 0
        best = []
        for alias_key, bucket in kb._by_alias.items():
            if len(alias_key) < 3:
                continue
            if alias_key in key and len(alias_key) > best_len:
                best_len = len(alias_key)
                best = list(bucket)
        if best:
            return kb._choose(best, control_type)
        best_score = 0
        best_kw = []
        for entry in kb._entries:
            for kw in entry.keywords:
                kw_norm = normalize_key(kw)
                if len(kw_norm) >= 2 and kw_norm in key and len(kw_norm) > best_score:
                    best_score = len(kw_norm)
                    best_kw = [entry]
                elif len(kw_norm) >= 2 and kw_norm in key and len(kw_norm) == best_score:
                    if entry not in best_kw:
                        best_kw.append(entry)
        if best_kw:
            return kb._choose(best_kw, control_type)
        return None

    def setUp(self) -> None:
        self.kb = load_default()

    def test_the_index_answers_like_the_old_scan(self) -> None:
        labels = []
        for entry in self.kb.entries():
            labels.append(entry.id)
            labels.extend(entry.aliases)
        labels.extend([
            "View & Edit", "view and edit", "Read from file...\tCtrl-O",
            "Draw", "Draw >", "1. Sound demo_vowel", "Objects:",
            "Totally Unknown Widget", "Play", "Analyse periodicity",
        ])
        for label in labels:
            for control_type in (None, "ButtonControl", "MenuItemControl"):
                old = self._old_lookup(self.kb, label, control_type)
                new = self.kb.lookup(label, control_type)
                self.assertEqual(
                    old.id if old else None,
                    new.id if new else None,
                    f"lookup({label!r}, {control_type!r}) changed",
                )

    def test_an_unknown_control_still_finds_nothing(self) -> None:
        self.assertIsNone(self.kb.lookup("Qqzzxwv"))

    def test_the_keywords_are_normalised_once(self) -> None:
        entry = KnowledgeEntry(id="x", keywords=["Play", "play"])
        self.assertEqual(entry.normalized_keywords(), ["play"])
        # The second call must not normalise again: the list is cached.
        self.assertIs(entry.normalized_keywords(), entry.normalized_keywords())

    def test_the_search_still_ranks_the_same_entries(self) -> None:
        found = [entry.id for entry in self.kb.search("view edit", limit=5)]
        self.assertIn("ow-view-and-edit", found)

    def test_a_hand_built_knowledge_base_still_works(self) -> None:
        kb = KnowledgeBase([
            KnowledgeEntry(id="play", aliases=["Play sound"], keywords=["playback"]),
            KnowledgeEntry(id="stop", aliases=["Stop"], keywords=["halt"]),
        ])
        self.assertIsNotNone(kb.lookup("Play sound"))
        self.assertIsNotNone(kb.lookup("stop"))
        self.assertIsNotNone(kb.lookup("playback"))


# --------------------------------------------------------------------------
# the hit-test cache
# --------------------------------------------------------------------------
class _FakeElement:
    def __init__(self, name="Inspect", rect=(10, 10, 90, 30)):
        self.name = name
        self.control_type = "ButtonControl"
        self.automation_id = ""
        self.hwnd = 0
        self.rect = rect
        self.window_title = "Praat Objects"
        self.depth = 2
        self.enabled = True

    def contains_point(self, x, y):
        left, top, right, bottom = self.rect
        return left <= x < right and top <= y < bottom


class _FakeUI:
    """A UIA sensor that counts the hit tests."""

    def __init__(self, element=None):
        self.calls = 0
        self.element = element if element is not None else _FakeElement()

    def element_at_point(self, x, y, **kwargs):
        self.calls += 1
        return self.element

    def available(self):
        return True


class HitTestCacheTests(unittest.TestCase):
    """The hit test is expensive, so the answer is kept."""

    def make_app(self, ui):
        app = praatao_run.Praatao.__new__(praatao_run.Praatao)
        app.ui = ui
        app._hit_cache = None
        app._hit_cache_at = 0.0
        return app

    def test_a_pointer_that_does_not_move_is_not_hit_tested_again(self) -> None:
        ui = _FakeUI()
        app = self.make_app(ui)
        first = app._element_under_cursor(50, 20)
        second = app._element_under_cursor(50, 20)
        self.assertIs(first, second)
        self.assertEqual(ui.calls, 1, "the hit test was repeated")

    def test_a_pointer_that_moved_inside_the_same_button_is_not_hit_tested(self) -> None:
        ui = _FakeUI()
        app = self.make_app(ui)
        app._element_under_cursor(50, 20)
        app._element_under_cursor(55, 22)
        self.assertEqual(ui.calls, 1, "the hit test was repeated inside a button")

    def test_a_pointer_that_moved_to_another_control_is_hit_tested(self) -> None:
        ui = _FakeUI()
        app = self.make_app(ui)
        app._element_under_cursor(50, 20)
        app._element_under_cursor(500, 400)
        self.assertEqual(ui.calls, 2, "the hit test was skipped")

    def test_a_pane_is_not_treated_as_a_button(self) -> None:
        """A big container has to be hit-tested again inside it."""

        ui = _FakeUI(_FakeElement(rect=(0, 0, 800, 600)))
        app = self.make_app(ui)
        app._element_under_cursor(50, 20)
        app._element_under_cursor(60, 30)
        self.assertEqual(ui.calls, 2, "the hit test was skipped inside a pane")


# --------------------------------------------------------------------------
# the dwell
# --------------------------------------------------------------------------
class _FakeCard:
    """Just enough of the card for the dwell logic."""

    pinned = False

    def hide(self) -> None:
        pass

    def show(self, *args, **kwargs) -> None:
        pass

    def is_visible(self) -> bool:
        return False


class _FakePanel:
    def set_lesson(self, *args, **kwargs) -> None:
        pass

    def set_state(self, *args, **kwargs) -> None:
        pass


class _FakeAdvice:
    headline = "标题"
    body = "内容"
    source = "kb"


class _FakeAdvisor:
    def advise(self, element, **kwargs):
        return _FakeAdvice()


class DwellTests(unittest.TestCase):
    """The dwell starts when the pointer comes to rest, not when the tick
    happens to notice."""

    def make_app(self, advisor=None):
        app = praatao_run.Praatao.__new__(praatao_run.Praatao)
        app.advisor = advisor
        app.card = _FakeCard()
        app.spot = _FakeCard()
        app.panel = _FakePanel()
        app._last_key = None
        app._hover_since = 0.0
        app._dismissed_at = 0.0
        app._misses = 0
        app._shown_signature = None
        app._current_element = None
        app.state = None
        app._mouse_moved_at = time.monotonic() - 5.0
        return app

    def test_the_dwell_starts_at_the_moment_the_pointer_stopped(self) -> None:
        app = self.make_app(advisor=_FakeAdvisor())
        element = _FakeElement()
        # The pointer stopped moving five seconds ago: the control it is
        # on has already been rested on for five seconds.
        app._advise_element(element, 50, 20)
        self.assertAlmostEqual(app._hover_since, app._mouse_moved_at, delta=0.2)

    def test_a_dismissed_card_waits_for_the_dwell_again(self) -> None:
        app = self.make_app(advisor=_FakeAdvisor())
        app._dismissed_at = time.monotonic()
        app._mouse_moved_at = app._dismissed_at - 10.0
        app._advise_element(_FakeElement(), 50, 20)
        self.assertAlmostEqual(app._hover_since, app._dismissed_at, delta=0.2)


# --------------------------------------------------------------------------
# the sensors
# --------------------------------------------------------------------------
class SensorShortcutTests(unittest.TestCase):
    def test_an_empty_script_is_never_sent_to_praat(self) -> None:
        """An empty script used to be handed to Praat as the current
        directory, and Praat answered that with a modal Message box."""

        probe = PraatStateProbe()
        path, temporary = probe._materialise("")
        self.assertIsNone(path)
        self.assertFalse(temporary)

    def test_a_directory_is_never_sent_to_praat(self) -> None:
        probe = PraatStateProbe()
        path, temporary = probe._materialise(str(ROOT))
        self.assertIsNone(path)
        self.assertFalse(temporary)

    def test_a_real_script_is_still_found(self) -> None:
        probe = PraatStateProbe()
        script = Path(ROOT / "praatao" / "probes" / "snapshot.praat")
        path, temporary = probe._materialise(str(script))
        self.assertIsNotNone(path)
        self.assertFalse(temporary)


@unittest.skipUnless(praat_available(), "Praat is not running")
class LiveSensorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ui = PraatUI()
        objects = self.ui.objects_window()
        if objects is None:
            self.skipTest("Praat is not running")

    def test_the_fast_probe_reads_the_objects_window(self) -> None:
        probe = PraatStateProbe()
        state = probe.fast()
        self.assertTrue(state.objects, "no objects found")
        self.assertIn("Sound", [obj.type for obj in state.objects])

    def test_the_fast_probe_is_much_faster_than_a_tree_walk(self) -> None:
        probe = PraatStateProbe()
        probe.fast()
        start = time.perf_counter()
        probe.fast()
        elapsed = (time.perf_counter() - start) * 1000.0
        self.assertLess(elapsed, 200.0, f"fast() took {elapsed:.1f} ms")

    def test_the_canvas_regions_match_the_accessibility_tree(self) -> None:
        from praatao.sensors.canvas import CanvasSensor

        canvas = CanvasSensor(self.ui)
        fast = canvas._regions_via_win32()
        slow = canvas._regions_via_uia()
        self.assertEqual(
            sorted(region.rect for region in fast),
            sorted(region.rect for region in slow),
        )

    def test_the_open_menu_items_are_read_from_the_popup(self) -> None:
        objects = self.ui.objects_window()
        try:
            items = self.ui.open_menu(objects, "Open", keep_open=True)
        except Exception:  # noqa: BLE001
            self.skipTest("could not open the menu")
        self.assertTrue(items)
        try:
            read = self.ui.open_popup_items()
            self.assertTrue(read, "the popup items were not read")
            names = {item.key.lower() for item in read}
            self.assertTrue(
                any("read from file" in name for name in names),
                f"unexpected popup items: {sorted(names)}",
            )
        finally:
            self.ui.close_popup(objects)

    def test_the_menu_check_finds_an_open_praat_menu(self) -> None:
        from praatao.sensors.uia import _menu_popup_open

        objects = self.ui.objects_window()
        if _menu_popup_open():
            self.skipTest("a menu is open (left over from another test)")
        try:
            self.ui.open_menu(objects, "Open", keep_open=True)
        except Exception:  # noqa: BLE001
            self.skipTest("could not open the menu")
        try:
            self.assertTrue(_menu_popup_open(), "the open menu was not noticed")
        finally:
            self.ui.close_popup(objects)
        deadline = time.time() + 2.0
        while time.time() < deadline and _menu_popup_open():
            time.sleep(0.1)
        self.assertFalse(_menu_popup_open(), "a closed menu is still noticed")

    def test_the_time_since_the_last_input_is_reported(self) -> None:
        idle = seconds_since_last_input()
        self.assertIsInstance(idle, float)
        self.assertGreaterEqual(idle, 0.0)


if __name__ == "__main__":
    unittest.main()
