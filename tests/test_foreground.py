"""The coach must never pull another window to the front.

Measured facts that this file protects:

* ``Praat.exe --send`` (the deep state probe) **activates the Praat
  window**, so a script may only be sent while Praat is already in front.
* A UIA hit test over a Praat control can activate Praat as well, so the
  coach does not touch Praat at all while another program is in front.

Without those two rules the student loses the keyboard while typing: Praat
jumps to the front every few seconds.
"""

from __future__ import annotations

import time
import unittest

import win32gui

from praatao.sensors.uia import praat_available, praat_has_focus


def _foreground() -> int:
    return int(win32gui.GetForegroundWindow() or 0)


def _activate(hwnd: int) -> bool:
    """Bring a window to the front, lifting the foreground lock."""

    try:
        import win32api
        import win32process

        current = win32api.GetCurrentThreadId()
        foreground = win32gui.GetForegroundWindow()
        other = win32process.GetWindowThreadProcessId(foreground)[0]
        attached = bool(win32process.AttachThreadInput(current, other, True))
        try:
            win32gui.SetForegroundWindow(hwnd)
        finally:
            if attached:
                win32process.AttachThreadInput(current, other, False)
        time.sleep(0.4)
        return win32gui.GetForegroundWindow() == hwnd
    except Exception:
        return False


class ForegroundTests(unittest.TestCase):
    def setUp(self) -> None:
        self.before = _foreground()

    def tearDown(self) -> None:
        # Put the focus back where it was, so the other tests are not
        # affected by this one.
        if self.before:
            _activate(self.before)

    def test_praat_has_focus_is_false_for_another_window(self) -> None:
        if not praat_available():
            self.skipTest("Praat is not running")
        import tkinter

        root = tkinter.Tk()
        root.title("Praatao test")
        root.geometry("200x120+30+700")
        root.update()
        frame = int(root.wm_frame(), 16)
        try:
            if not _activate(frame):
                self.skipTest("the test window could not be brought to the front")
            self.assertFalse(praat_has_focus())
        finally:
            root.destroy()

    def test_a_script_is_not_sent_while_praat_is_in_the_background(self) -> None:
        """The deep probe may only run while Praat is the front window."""

        if not praat_available():
            self.skipTest("Praat is not running")

        import tkinter

        from praatao.sensors.praat_state import PraatStateProbe

        root = tkinter.Tk()
        root.title("Praatao test")
        root.geometry("200x120+30+700")
        root.update()
        frame = int(root.wm_frame(), 16)
        try:
            if not _activate(frame):
                self.skipTest("the test window could not be brought to the front")
            probe = PraatStateProbe()
            state = probe.snapshot(timeout=2.0, require_focus=True)
            self.assertIn("not in front", state.error or "")
        finally:
            root.destroy()

    def test_the_coach_leaves_the_foreground_alone(self) -> None:
        """With another program in front, the coach may not steal it."""

        if not praat_available():
            self.skipTest("Praat is not running")

        import tkinter

        import run as praatao_run

        root = tkinter.Tk()
        root.title("Praatao test")
        root.geometry("200x120+30+700")
        root.update()
        frame = int(root.wm_frame(), 16)
        app = praatao_run.Praatao(lang="zh", use_llm=False, ui_backend="qt")
        try:
            app.host.after(praatao_run.MOUSE_POLL_MS, app._mouse_poll)
            app.host.after(45, app._tick)
            if not _activate(frame):
                self.skipTest("the test window could not be brought to the front")
            before = _foreground()
            deadline = time.time() + 6.0
            while time.time() < deadline:
                app.pump()
                time.sleep(0.05)
            self.assertEqual(
                _foreground(),
                before,
                "the coach pulled another window to the front",
            )
        finally:
            app.quit()
            root.destroy()


if __name__ == "__main__":
    unittest.main()
