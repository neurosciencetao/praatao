"""Menus must survive while the coach is running.

A Praat script closes every menu that is open, and the coach sends one
every few seconds to read the deeper state.  So the coach has to notice
that a menu is open - including a *submenu*, which is owned by the menu
above it and not by the Praat window.
"""

from __future__ import annotations

import unittest

from praatao.sensors import uia as uia_module
from praatao.sensors.uia import _praat_owned_popup


class _FakeWin32:
    """Just enough of ``win32gui`` to describe a menu chain."""

    def __init__(self, owners: dict[int, int], classes: dict[int, str]) -> None:
        self.owners = owners
        self.classes = classes

    def IsWindowVisible(self, hwnd: int) -> bool:
        return True

    def GetWindow(self, hwnd: int, _flag: int) -> int:
        return int(self.owners.get(hwnd, 0) or 0)

    def GetClassName(self, hwnd: int) -> str:
        return self.classes.get(hwnd, "")


class SubmenuTests(unittest.TestCase):
    def setUp(self) -> None:
        self._win32 = uia_module.win32gui
        self.praat = 100
        self.menu = 200
        self.submenu = 300
        self.other = 400
        uia_module.win32gui = _FakeWin32(
            owners={
                self.menu: self.praat,
                self.submenu: self.menu,
                self.other: 500,
            },
            classes={
                self.praat: "PraatShell1 Praat",
                self.menu: "#32768",
                self.submenu: "#32768",
                self.other: "#32768",
                500: "SomeOtherApplication",
            },
        )

    def tearDown(self) -> None:
        uia_module.win32gui = self._win32

    def test_a_menu_of_praat_is_praat(self) -> None:
        self.assertTrue(_praat_owned_popup(self.menu))

    def test_a_submenu_of_a_praat_menu_is_praat(self) -> None:
        # The submenu is owned by the menu, not by the Praat window: the
        # owner chain has to be walked.
        self.assertTrue(_praat_owned_popup(self.submenu))

    def test_a_menu_of_another_program_is_not_praat(self) -> None:
        self.assertFalse(_praat_owned_popup(self.other))

    def test_a_menu_without_an_owner_is_not_praat(self) -> None:
        self.assertFalse(_praat_owned_popup(999))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
