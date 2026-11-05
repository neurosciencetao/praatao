"""Tests for :mod:`praatao.sensors.uia`.

The normalisation tests run everywhere.  The live tests are skipped unless
a Praat window is actually open (see :func:`praatao.sensors.uia.praat_available`).
"""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import win32con  # noqa: E402
import win32gui  # noqa: E402

from praatao.sensors import uia as uia_module  # noqa: E402
from praatao.sensors.uia import (  # noqa: E402
    Element,
    PraatUI,
    UiaWindow,
    classify_window,
    normalize_name,
    praat_available,
)

PRAAT_RUNNING = praat_available()


def _praat_modal_dialog() -> bool:
    """True when a modal dialog blocks the Praat main window.

    Other teammates probe Praat with ``Praat.exe --send`` scripts; a failing
    formula leaves a modal ``Message`` box behind.  While such a box is up,
    the Objects window is frozen (no action buttons, menu clicks go to the
    dialog), so the live tests have to stand down.
    """
    try:
        import win32gui
        import win32process
    except Exception:  # pragma: no cover - pywin32 missing
        return False

    pids: set[int] = set()

    def _own(hwnd: int) -> int:
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            return int(pid)
        except Exception:
            return 0

    def _find_praat(hwnd: int, _extra: object) -> None:
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return
            cls = win32gui.GetClassName(hwnd) or ""
            title = win32gui.GetWindowText(hwnd) or ""
        except Exception:
            return
        if cls.lower().startswith("praat") or title == "Praat Objects":
            pids.add(_own(hwnd))

    win32gui.EnumWindows(_find_praat, None)
    if not pids:
        return False

    blocked: list[int] = []

    def _find_dialog(hwnd: int, _extra: object) -> None:
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return
            cls = win32gui.GetClassName(hwnd) or ""
            if cls not in ("#32770", "#32768"):
                return
        except Exception:
            return
        if _own(hwnd) in pids:
            blocked.append(hwnd)

    win32gui.EnumWindows(_find_dialog, None)
    return bool(blocked)



def _cursor_can_be_moved() -> bool:
    """Can this process move the mouse cursor?

    Praat's menu bar items have no HWND, so they can only be opened with a
    real mouse click - and a real click needs the cursor to move.  Some
    sessions (a remote desktop, a locked input desktop, a machine where
    another application holds the pointer) refuse ``SetCursorPos``.  The
    tests that need it skip themselves instead of failing.
    """

    import ctypes

    class _POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    def _pos() -> tuple[int, int]:
        point = _POINT()
        try:
            ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
        except Exception:
            return (0, 0)
        return (int(point.x), int(point.y))

    before = _pos()
    try:
        ctypes.windll.user32.SetCursorPos(before[0] + 3, before[1] + 3)
    except Exception:
        return False
    time.sleep(0.05)
    after = _pos()
    # Put it back, so that the rest of the suite is not disturbed.
    try:
        ctypes.windll.user32.SetCursorPos(before[0], before[1])
    except Exception:
        pass
    return after != before


def _close_stray_popups() -> None:
    """Close menu popups that a previous test (or script) left open.

    A leftover ``#32768`` popup makes the live tests skip, because the popup
    blocks Praat's menu bar.  ESC is posted straight to the popup window: a
    real ESC keystroke would land on the Objects window and clear Praat's
    object selection.
    """
    victims: list[int] = []

    def _find(hwnd: int, _extra: object) -> None:
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return
            if win32gui.GetClassName(hwnd) == "#32768":
                victims.append(hwnd)
        except Exception:
            return

    win32gui.EnumWindows(_find, None)
    for hwnd in victims:
        try:
            win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0)
            win32gui.PostMessage(hwnd, win32con.WM_KEYUP, win32con.VK_ESCAPE, 0)
        except Exception:
            continue
    if victims:
        time.sleep(0.4)


class NormalizeNameTests(unittest.TestCase):

    def test_empty(self) -> None:
        self.assertEqual(normalize_name(""), "")
        self.assertEqual(normalize_name(None), "")  # type: ignore[arg-type]

    def test_leading_narrow_nbsp_and_trailing_arrow(self) -> None:
        raw = "\u202f\u202f   Draw  >"
        self.assertEqual(normalize_name(raw), "Draw")

    def test_other_dynamic_buttons(self) -> None:
        for label in (
            "Query",
            "Modify",
            "Annotate",
            "Analyse periodicity",
            "Analyse spectrum",
            "Manipulate",
            "Convert",
            "Filter",
            "Combine",
        ):
            raw = f"\u202f\u202f   {label}  >"
            self.assertEqual(normalize_name(raw), label)

    def test_plain_spaces_and_arrow(self) -> None:
        self.assertEqual(normalize_name("     Draw  >"), "Draw")
        self.assertEqual(normalize_name("Draw >"), "Draw")
        self.assertEqual(normalize_name("Draw>"), "Draw")

    def test_nbsp_becomes_space(self) -> None:
        self.assertEqual(normalize_name("View\u00a0& Edit"), "View & Edit")
        self.assertEqual(normalize_name("a\u202fb"), "a b")

    def test_whitespace_runs_collapse(self) -> None:
        self.assertEqual(normalize_name("  multiple   spaces  "), "multiple spaces")
        self.assertEqual(normalize_name("a\nb"), "a b")
        self.assertEqual(normalize_name("a\r\n b"), "a b")
        self.assertEqual(normalize_name("a\u00a0\u00a0b"), "a b")

    def test_accelerator_suffix_beats_whitespace_collapsing(self) -> None:
        # The tab cut happens first, so everything behind the tab is gone.
        self.assertEqual(normalize_name("a\t\tb"), "a")

    def test_accelerator_suffix_is_cut(self) -> None:
        self.assertEqual(normalize_name("Read from file...\tCtrl-O"), "Read from file...")
        self.assertEqual(normalize_name("Open long sound file...\tCtrl-L"), "Open long sound file...")

    def test_ellipsis_is_kept(self) -> None:
        self.assertEqual(normalize_name("Rename..."), "Rename...")
        self.assertEqual(normalize_name("Copy..."), "Copy...")
        self.assertEqual(normalize_name("To Intensity..."), "To Intensity...")

    def test_trailing_colon_is_stripped(self) -> None:
        self.assertEqual(normalize_name("Objects:"), "Objects")
        self.assertEqual(normalize_name("Sound :"), "Sound")
        self.assertEqual(normalize_name("Sound > :"), "Sound")

    def test_list_index_prefix_is_stripped(self) -> None:
        self.assertEqual(normalize_name("1. Sound demo_vowel"), "Sound demo_vowel")
        self.assertEqual(normalize_name("2. Sound demo_vowel"), "Sound demo_vowel")
        self.assertEqual(normalize_name("12.  TextGrid demo"), "TextGrid demo")

    def test_index_prefix_needs_whitespace(self) -> None:
        # '1.5' must not be mistaken for an index prefix.
        self.assertEqual(normalize_name("1.5 s"), "1.5 s")

    def test_known_button_names_are_stable(self) -> None:
        for name in ("Rename...", "Copy...", "Inspect", "Info", "Remove",
                     "Sound help", "View & Edit", "Play", "To Intensity..."):
            self.assertEqual(normalize_name(name), name)

    def test_menu_bar_names_are_stable(self) -> None:
        for name in ("Praat", "New", "Open", "Save", "Help"):
            self.assertEqual(normalize_name(name), name)


class ClassifyWindowTests(unittest.TestCase):
    """Unit tests for :func:`classify_window` (no Praat needed)."""

    def test_objects(self) -> None:
        self.assertEqual(classify_window("Praat Objects", "PraatShell1 Praat"), "objects")

    def test_picture(self) -> None:
        self.assertEqual(classify_window("Praat Picture", "PraatChildWindow1 Praat"), "picture")

    def test_editor_with_index(self) -> None:
        self.assertEqual(classify_window("2. Sound demo_vowel", "PraatChildWindow1 Praat"), "editor")

    def test_editor_without_index(self) -> None:
        self.assertEqual(classify_window("Sound demo_vowel", "PraatChildWindow1 Praat"), "editor")

    def test_foreign_window(self) -> None:
        self.assertEqual(classify_window("Notepad", "Notepad"), "other")


class ElementTests(unittest.TestCase):
    """Unit tests for the plain-data classes (no Praat needed)."""

    def test_key_is_the_normalised_name(self) -> None:
        element = Element(
            name="\u202f\u202f   Draw  >",
            control_type="ButtonControl",
            automation_id="1",
            hwnd=0,
            rect=(1, 2, 3, 4),
            window_title="Praat Objects",
        )
        self.assertEqual(element.key, "Draw")

    def test_contains_point(self) -> None:
        element = Element(
            name="Play",
            control_type="ButtonControl",
            automation_id="1",
            hwnd=0,
            rect=(10, 20, 30, 40),
            window_title="Praat Objects",
        )
        self.assertTrue(element.contains_point(10, 20))
        self.assertTrue(element.contains_point(29, 39))
        self.assertFalse(element.contains_point(30, 39))
        self.assertFalse(element.contains_point(9, 20))
        self.assertFalse(element.contains_point(15, 40))

    def test_contains_point_without_rect(self) -> None:
        element = Element(
            name="Play",
            control_type="ButtonControl",
            automation_id="",
            hwnd=0,
            rect=None,
            window_title="",
        )
        self.assertFalse(element.contains_point(0, 0))


@unittest.skipUnless(PRAAT_RUNNING, "Praat not running")
class LiveObjectsWindowTests(unittest.TestCase):
    """Live checks against the running Praat."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.ui = PraatUI()
        _close_stray_popups()

    @classmethod
    def tearDownClass(cls) -> None:
        _close_stray_popups()

    def setUp(self) -> None:
        if not praat_available():
            self.skipTest("Praat is not running")
        if _praat_modal_dialog():
            self.skipTest("Praat is blocked by a modal dialog")
        # The tests below click on Praat, and a click only reaches Praat when
        # Praat is the foreground window.  Bring it forward, or the test
        # depends on whatever else happens to have the focus.
        window = self.ui.objects_window()
        if window is not None:
            for _attempt in range(3):
                if self.ui._activate(window):
                    break
                time.sleep(0.2)
            else:
                self.skipTest("Praat could not be brought to the front")
            time.sleep(0.25)

    def test_objects_window_is_found(self) -> None:
        window = self.ui.objects_window()
        self.assertIsNotNone(window)
        assert window is not None
        self.assertEqual(window.title, "Praat Objects")
        self.assertEqual(window.kind, "objects")
        self.assertEqual(window.class_name, "PraatShell1 Praat")
        self.assertGreater(window.hwnd, 0)

    def test_praat_available(self) -> None:
        self.assertTrue(praat_available())
        self.assertTrue(self.ui.available())

    def test_view_and_edit_button_is_found(self) -> None:
        window = self.ui.objects_window()
        self.assertIsNotNone(window)
        assert window is not None
        button = self.ui.find("View & Edit", window=window)
        if button is None:
            # Nothing is selected in Praat: select the first Sound and retry.
            items = self.ui.find_all(window=window, control_type="ListItemControl")
            sound = next((item for item in items if "Sound" in item.name), None)
            if sound is None:
                self.skipTest("no Sound object in the list")
            self.ui.invoke(sound)
            time.sleep(0.6)
            button = self.ui.find("View & Edit", window=window)
        if button is None:
            self.skipTest(
                "Praat does not expose the Sound action buttons at the moment"
            )
        assert button is not None
        self.assertEqual(button.control_type, "ButtonControl")
        self.assertEqual(button.key, "View & Edit")
        self.assertEqual(button.window_title, "Praat Objects")

    def test_list_items_lose_their_index(self) -> None:
        window = self.ui.objects_window()
        assert window is not None
        items = self.ui.find_all(window=window, control_type="ListItemControl")
        self.assertTrue(items)
        for item in items:
            self.assertFalse(item.key[:1].isdigit())
            self.assertNotIn(".", item.key.split(" ")[0])

    def test_element_at_point_over_the_object_list(self) -> None:
        window = self.ui.objects_window()
        assert window is not None
        items = [
            item
            for item in self.ui.find_all(window=window, control_type="ListItemControl")
            if item.rect is not None
        ]
        self.assertTrue(items, "no list item with a bounding rectangle")
        hits = []
        for item in items:
            assert item.rect is not None
            x = (item.rect[0] + item.rect[2]) // 2
            y = (item.rect[1] + item.rect[3]) // 2
            hit = self.ui.element_at_point(x, y)
            if hit is None and _cursor_can_be_moved():
                # A coach that is running at the same time may have its
                # own card on top of the list.  Move the pointer away,
                # give the card time to go, and try again.
                import ctypes

                ctypes.windll.user32.SetCursorPos(20, 700)
                time.sleep(2.5)
                hit = self.ui.element_at_point(x, y)
            if hit is not None:
                hits.append(hit)
        self.assertTrue(hits, "element_at_point returned nothing over the object list")
        self.assertTrue(any(hit.control_type == "ListItemControl" for hit in hits))

    def test_open_menu_returns_read_from_file(self) -> None:
        if not _cursor_can_be_moved():
            self.skipTest("this session does not let the process move the mouse")
        window = self.ui.objects_window()
        assert window is not None
        items: list = []
        for _attempt in range(3):
            items = self.ui.open_menu(window, "Open")
            if items:
                break
            time.sleep(0.4)
        keys = [item.key for item in items]
        self.assertIn("Read from file...", keys)
        self.assertTrue(all(item.control_type == "MenuItemControl" for item in items))

    def test_open_menu_closes_the_popup_again(self) -> None:
        if not _cursor_can_be_moved():
            self.skipTest("this session does not let the process move the mouse")
        window = self.ui.objects_window()
        assert window is not None
        self.ui.open_menu(window, "Open")
        # The popup is gone: the tree must not contain a MenuControl any more.
        controls = [
            element
            for element in self.ui.find_all(window=window, control_type="MenuControl")
        ]
        self.assertEqual(controls, [])

    def test_editor_window_title_is_classified(self) -> None:
        editors = self.ui.editor_windows()
        for window in editors:
            self.assertEqual(window.kind, "editor")
            self.assertNotEqual(window.title, "Praat Objects")
            self.assertNotEqual(window.title, "Praat Picture")

    def test_window_at_point(self) -> None:
        window = self.ui.objects_window()
        assert window is not None
        assert window.rect is not None
        x = (window.rect[0] + window.rect[2]) // 2
        y = (window.rect[1] + window.rect[3]) // 2
        found = self.ui.window_at_point(x, y)
        self.assertIsNotNone(found)

    def test_only_praat_is_explained(self) -> None:
        """The coach must stay quiet when another application is in front.

        The geometric fallback ("is the point inside a Praat rectangle?")
        is not enough: another window can cover that rectangle, and then
        the control under the cursor belongs to that other window.
        """

        import win32gui

        window = self.ui.objects_window()
        assert window is not None
        assert window.rect is not None

        # A point inside the Praat rectangle where another window is the
        # frontmost thing: that is the case the coach has to ignore.
        left, top, right, bottom = window.rect
        covered = None
        for y in range(top + 4, bottom - 4, 17):
            for x in range(left + 4, right - 4, 23):
                hwnd = win32gui.WindowFromPoint((x, y))
                if not hwnd:
                    continue
                class_name = (win32gui.GetClassName(hwnd) or "").casefold()
                if "praat" in class_name or class_name == "#32768":
                    continue
                if win32gui.GetAncestor(hwnd, 2) == window.hwnd:
                    continue
                covered = (x, y, class_name)
                break
            if covered:
                break
        if covered is None:
            self.skipTest("no other window covers the Praat window")

        x, y, class_name = covered
        element = self.ui.element_at_point(x, y)
        self.assertIsNone(
            element,
            f"the coach would explain a control of '{class_name}': {element}",
        )

    def test_element_at_point_over_a_menu_popup(self) -> None:
        """The cursor may sit on a popup menu; UIA must still resolve it."""
        if not _cursor_can_be_moved():
            self.skipTest("this session does not let the process move the mouse")
        window = self.ui.objects_window()
        assert window is not None
        popup = None
        try:
            # White box: open the popup and keep it open for the hit test.
            control = self.ui._control_from_window(window)
            self.assertIsNotNone(control)
            menu_item = None
            for node, _depth in self.ui._iter_controls(control):
                if (
                    uia_module._text(node, "ControlTypeName") == "MenuItemControl"
                    and uia_module._text(node, "Name") == "Open"
                ):
                    menu_item = node
                    break
            self.assertIsNotNone(menu_item)
            self.ui._click_control(menu_item)
            popup = self.ui._wait_for_popup(window, "Open", 3.0)
            self.assertIsNotNone(popup)
            assert popup is not None
            targets = [
                child
                for child in self.ui._children(popup)
                if uia_module._text(child, "ControlTypeName") == "MenuItemControl"
            ]
            self.assertTrue(targets)
            hit = None
            for child in targets:
                rect = uia_module._safe_rect(child)
                if rect is None:
                    continue
                x = (rect[0] + rect[2]) // 2
                y = (rect[1] + rect[3]) // 2
                hit = self.ui.element_at_point(x, y)
                if hit is not None and hit.control_type == "MenuItemControl":
                    break
                hit = None
            self.assertIsNotNone(hit, "no menu item found under the cursor")
            assert hit is not None
            self.assertEqual(hit.control_type, "MenuItemControl")
            self.assertEqual(hit.window_title, "Praat Objects")
        finally:
            self.ui._close_popup(window, popup)


if __name__ == "__main__":
    unittest.main()
