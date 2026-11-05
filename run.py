"""Praatao entry point.

Run it next to an open Praat::

    python run.py

Praatao watches the mouse.  When the cursor rests on a control that Praat
exposes through the Windows accessibility tree, a small card explains what
that control does, how to use it, and what it means in your current project.

The card disappears when the pointer moves away (after two seconds), a click
dismisses it, and the pin button keeps it open.  Praat's drawing areas are
explained too: locally by the knowledge base, and - if the user allows it -
by a model that actually looks at the picture.
"""

from __future__ import annotations

import argparse
import os
import queue
import sys
import threading
import time
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# The console may be cp1252 (Windows default); the banner and the tips contain
# Chinese, so make stdout/stderr lossless instead of crashing on encode.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # pragma: no cover - very old/odd streams
        pass

from praatao import paths  # noqa: E402
from praatao.settings import Settings  # noqa: E402
from praatao.tutor.kb import KnowledgeBase, load_default, normalize_key  # noqa: E402
from praatao.tutor.lessons import LessonLibrary, LessonRunner  # noqa: E402
from praatao.ui.hover import HoverCard, source_label  # noqa: E402
from praatao.ui.hotkeys import Hotkeys  # noqa: E402
from praatao.ui.overlay import cursor_pos, mouse_button_down  # noqa: E402
from praatao.ui.panel import SidePanel  # noqa: E402
from praatao.ui.spotlight import Spotlight  # noqa: E402

POLL_MS = 45
#: The mouse button is watched separately and much faster: a quick click
#: can be shorter than the main tick, and then it would be lost.
MOUSE_POLL_MS = 10
STATE_INTERVAL = 0.9
#: The deep probe runs a Praat script, and a script closes an open menu, so
#: it runs rarely and only when the user is visibly idle.
DEEP_STATE_INTERVAL = 8.0
DEEP_STATE_IDLE = 1.5
#: How long the list of open menu items is reused (a tree walk costs ~80 ms).
POPUP_CACHE_TTL = 0.3
#: How long the cursor must rest on a control before the card appears.
#:
#: This is the only deliberate delay in the hover: everything else is
#: measured (see ``docs/15-performance.md``).  It was 320 ms; the
#: measurement of the false-trigger rate showed that a card still never
#: appeared for a control the pointer passed over in 240 ms or less, so
#: the dwell was shortened to 280 ms.
DWELL_MS = 280
#: How many consecutive failed hit tests are tolerated before the card goes.
HOVER_MISS_GRACE = 4
#: How long the card survives after the pointer has left it.
AUTO_HIDE_SECONDS = 2.0
#: How long the answer to "what is under the pointer" is reused.
#:
#: A UIA hit test costs 5-9 ms and the pointer usually stands still
#: between two ticks, so the answer is kept.  The cache is thrown away
#: when the Praat state changes (the buttons under the pointer may have
#: changed with it) and at the latest after this many seconds, so that a
#: window moved under a still pointer is picked up.
HIT_CACHE_TTL = 1.0
#: A control bigger than this (in square pixels) is a pane and not a
#: button, so the hit test has to be repeated inside it.
HIT_CACHE_MAX_AREA = 60000
#: Set PRAATAO_DEBUG=1 to trace the hover loop.
DEBUG = bool(os.environ.get("PRAATAO_DEBUG"))


def _is_small_control(element) -> bool:
    """Is this a control (a button) and not a pane?

    A pane - the object list, a form - is bigger than a button, and
    inside a pane the hit test has to be repeated: the pointer can be
    over a different control of the same pane.
    """

    rect = getattr(element, "rect", None)
    if not rect:
        return False
    try:
        width = int(rect[2]) - int(rect[0])
        height = int(rect[3]) - int(rect[1])
    except Exception:  # noqa: BLE001
        return False
    if width <= 0 or height <= 0:
        return False
    return width * height <= HIT_CACHE_MAX_AREA


def _seconds_since_last_input() -> float:
    """How long ago the user last pressed a key or moved the mouse.

    The deep state probe waits for this: a Praat script must not land
    in the middle of somebody's typing.
    """

    try:
        from praatao.sensors.uia import seconds_since_last_input

        return float(seconds_since_last_input())
    except Exception:  # noqa: BLE001 - the sensor may be missing
        return 0.0


def _import_sensors():
    """Import the sensor layer, tolerating a half-built checkout."""
    try:
        from praatao.sensors.uia import PraatUI, normalize_name

        return PraatUI, normalize_name
    except Exception as exc:  # pragma: no cover
        print(f"[praatao] UI Automation sensor unavailable: {exc}", file=sys.stderr)
        return None, None


def _import_state():
    try:
        from praatao.sensors.praat_state import PraatStateProbe

        return PraatStateProbe
    except Exception as exc:  # pragma: no cover
        print(f"[praatao] state probe unavailable: {exc}", file=sys.stderr)
        return None


def _import_advisor():
    try:
        from praatao.tutor.advisor import Advisor
        from praatao.tutor.llm import LlmClient

        return Advisor, LlmClient
    except Exception as exc:  # pragma: no cover
        print(f"[praatao] advisor unavailable: {exc}", file=sys.stderr)
        return None, None


def _null_llm_client():
    """The client that answers nothing: the model is switched off."""

    try:
        from praatao.tutor.llm import NullLlmClient

        return NullLlmClient()
    except Exception:  # pragma: no cover
        return None


def _import_canvas():
    try:
        from praatao.sensors.canvas import CanvasSensor

        return CanvasSensor
    except Exception as exc:  # pragma: no cover
        print(f"[praatao] canvas sensor unavailable: {exc}", file=sys.stderr)
        return None


# --------------------------------------------------------------------------
# hosts
# --------------------------------------------------------------------------
class TkHost:
    """The Tk event loop."""

    backend = "tk"

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("Praatao")

    def after(self, ms: int, fn) -> None:
        self.root.after(ms, fn)

    def mainloop(self) -> None:
        self.root.mainloop()

    def quit(self) -> None:
        try:
            self.root.quit()
        except tk.TclError:
            pass

    def invoke(self, fn) -> None:
        """Run ``fn`` on the GUI thread (it may be called from a worker)."""

        try:
            self.root.after(0, fn)
        except tk.TclError:
            pass

    def pump(self) -> None:
        """Process pending GUI events (used by the capture scripts)."""

        try:
            self.root.update()
        except tk.TclError:
            pass

    def destroy(self) -> None:
        try:
            self.root.destroy()
        except tk.TclError:
            pass


class QtHost:
    """The Qt event loop, with a thread bridge for model answers."""

    backend = "qt"

    def __init__(self) -> None:
        from PySide6 import QtCore, QtWidgets

        from praatao.ui.qt.host import qt_available

        if not qt_available():  # pragma: no cover
            raise RuntimeError("PySide6 is not installed")
        self.app = QtWidgets.QApplication.instance()
        if self.app is None:
            self.app = QtWidgets.QApplication([])
        self.app.setApplicationName("Praatao")
        self.root = QtWidgets.QWidget()
        self.root.setWindowTitle("Praatao")
        self._timers: dict = {}

        class _Bridge(QtCore.QObject):
            invoked = QtCore.Signal(object)

            def __init__(self) -> None:
                super().__init__()
                # The slot must be a *bound* method of this object: only then
                # does Qt know that it lives in the GUI thread and turn the
                # connection into a queued one.  A plain function would be
                # called directly, in the worker thread, and touching a
                # widget from there is undefined behaviour.
                self.invoked.connect(self._run)

            def _run(self, fn) -> None:
                try:
                    fn()
                except Exception:  # noqa: BLE001
                    pass

        self._bridge = _Bridge()

    def after(self, ms: int, fn) -> None:
        """Run *fn* every *ms* milliseconds.

        Every callback gets its own timer, so several loops can run side
        by side (the hover tick and the fast mouse poll, for instance).
        """

        from PySide6 import QtCore

        timer = self._timers.get(fn)
        if timer is None:
            timer = QtCore.QTimer()
            timer.timeout.connect(fn)
            self._timers[fn] = timer
        timer.start(max(1, int(ms)))

    def mainloop(self) -> None:
        self.app.exec()

    def quit(self) -> None:
        try:
            self.app.quit()
        except Exception:  # noqa: BLE001
            pass

    def invoke(self, fn) -> None:
        """Run ``fn`` on the GUI thread (it may be called from a worker)."""

        self._bridge.invoked.emit(fn)

    def pump(self) -> None:
        """Process pending GUI events (used by the capture scripts)."""

        try:
            self.app.processEvents()
        except Exception:  # noqa: BLE001
            pass

    def destroy(self) -> None:
        try:
            self.app.quit()
        except Exception:  # noqa: BLE001
            pass


# --------------------------------------------------------------------------
# the application
# --------------------------------------------------------------------------
class Praatao:
    """The application shell: sensors -> tutor -> UI."""

    def __init__(
        self,
        lang: str = "zh",
        use_llm: bool = True,
        ui_backend: str = "auto",
        settings: "Settings | None" = None,
    ) -> None:
        self.settings = settings if settings is not None else Settings.load()
        # The command line wins over the stored settings.
        self.lang = lang or self.settings.lang
        use_llm = use_llm and self.settings.use_llm
        self.backend = self._pick_backend(ui_backend)
        self.host = QtHost() if self.backend == "qt" else TkHost()
        self.root = self.host.root

        self.kb: KnowledgeBase = load_default()
        self.lessons = LessonLibrary.load(paths.LESSONS_DIR)
        self.runner = LessonRunner(self.lessons)

        self.PraatUI, self.normalize_name = _import_sensors()
        self.ui = self.PraatUI() if self.PraatUI else None

        StateProbe = _import_state()
        self.probe = StateProbe(paths.PRAAT_EXE, paths.ensure_state_dir()) if StateProbe else None

        CanvasSensor = _import_canvas()
        self.canvas = CanvasSensor(self.ui) if (CanvasSensor and self.ui) else None

        Advisor, LlmClient = _import_advisor()
        self.llm = None
        if Advisor is not None:
            llm = None
            if use_llm and LlmClient is not None:
                try:
                    llm = LlmClient.from_env()
                except Exception:
                    llm = None
            else:
                # The model is switched off: hand the advisor the client
                # that answers nothing, so it cannot fall back to the
                # environment on its own.
                llm = _null_llm_client()
            self.advisor = Advisor(
                self.kb,
                state=self.probe,
                llm=llm,
                lang=lang,
                # The state is polled in the background.  The advisor must
                # not ask the probe for a state on its own: a probe call
                # sends a Praat script, which takes a moment, closes an
                # open menu and blocks the interface thread.
                use_probe=False,
            )
        else:
            self.advisor = None

        self.card = self._make_card()
        self.spot = self._make_spotlight()
        self.panel = self._make_panel()
        self.panel.on_command = self._panel_command
        self.panel.on_ask = self._panel_ask
        # Closing the panel is closing the coach.
        if hasattr(self.panel, "on_close"):
            self.panel.on_close = self._quit_from_tray
        self.panel.set_lessons([(l.id, l.title(lang)) for l in self.lessons.lessons()])
        self._connect_card()

        self.settings_window = self._make_settings_window()
        if hasattr(self.settings_window, "on_close"):
            self.settings_window.on_close = self._quit_from_tray
        self.toast = None
        self.tray = None

        self.hotkeys = Hotkeys()
        self.state_queue: queue.Queue = queue.Queue(maxsize=4)
        self.deep_state_queue: queue.Queue = queue.Queue(maxsize=2)
        self.state = None
        self._state_busy = False
        self._last_state_poll = 0.0
        self._deep_busy = False
        self._last_deep_poll = 0.0
        self._deep_thread: threading.Thread | None = None
        self._last_mouse_pos: tuple[int, int] | None = None
        self._mouse_moved_at = time.monotonic()
        #: The last answer of the UIA hit test: ``(x, y, element)``.
        self._hit_cache: tuple[int, int, object] | None = None
        self._hit_cache_at: float = 0.0
        self._popup_items: tuple[float, list] | None = None
        self._last_key: str | None = None
        self._hover_since = 0.0
        self._dismissed_at = 0.0
        self._misses = 0
        self._shown_signature: tuple | None = None
        self._last_mouse_down = False
        self._running = True
        self._current_rect: tuple[int, int, int, int] | None = None
        self._left_since = 0.0
        self._pending_llm_key: str | None = None

        self._print_banner()

    # -- back-end selection -----------------------------------------
    @staticmethod
    def _pick_backend(requested: str) -> str:
        if requested in ("qt", "tk"):
            return requested
        try:
            from praatao.ui.qt.host import qt_available

            return "qt" if qt_available() else "tk"
        except Exception:  # pragma: no cover
            return "tk"

    def _make_card(self):
        if self.backend == "qt":
            from praatao.ui.qt.hover import QtHoverCard

            return QtHoverCard(self.root, lang=self.lang)
        return HoverCard(self.root, lang=self.lang)

    def _make_spotlight(self):
        if self.backend == "qt":
            from praatao.ui.qt.spotlight import QtSpotlight

            return QtSpotlight(self.root)
        return Spotlight(self.root)

    def _make_panel(self):
        if self.backend == "qt":
            from praatao.ui.qt.panel import QtSidePanel

            return QtSidePanel(self.root, lang=self.lang)
        return SidePanel(self.root, lang=self.lang)

    def _make_settings_window(self):
        """The standalone Praatao settings window.

        It only exists in the Qt front-end; with the Tk fallback the
        settings can still be changed by editing the settings file.
        """

        if self.backend != "qt":
            return None
        try:
            from praatao.ui.qt.settings import QtSettingsWindow
        except Exception:  # pragma: no cover - PySide6 missing
            return None
        window = QtSettingsWindow(
            self.root, lang=self.lang, settings=self.settings,
            on_apply=self._apply_settings,
        )
        return window

    def _apply_settings(self, settings: "Settings") -> None:
        """Apply the settings the student just chose."""

        old_lang = self.lang
        self.settings = settings
        self.lang = settings.lang

        # The language model can be switched on and off while running.
        if self.advisor is not None:
            Advisor, LlmClient = _import_advisor()
            client = _null_llm_client()
            if settings.use_llm and LlmClient is not None:
                try:
                    client = LlmClient.from_env()
                except Exception:
                    client = _null_llm_client()
            try:
                self.advisor.llm = client
            except Exception:  # noqa: BLE001
                pass
            try:
                self.advisor.lang = settings.lang
            except Exception:  # noqa: BLE001
                pass

        # Privacy: a picture of the drawing area only leaves the machine
        # when the student says so.
        if settings.allow_vision:
            os.environ["PRAATAO_VISION"] = "1"
        else:
            os.environ.pop("PRAATAO_VISION", None)

        if settings.lang != old_lang:
            self._rebuild_language(settings.lang)

    def _rebuild_language(self, lang: str) -> None:
        """Switch every visible string to the new language."""

        setter = getattr(self.card, "set_lang", None)
        if callable(setter):
            try:
                setter(lang)
            except Exception:  # noqa: BLE001
                pass
        try:
            self.panel.destroy()
        except Exception:  # noqa: BLE001
            pass
        self.panel = self._make_panel()
        self.panel.on_command = self._panel_command
        self.panel.on_ask = self._panel_ask
        if hasattr(self.panel, "on_close"):
            self.panel.on_close = self._quit_from_tray
        self.panel.set_lessons(
            [(l.id, l.title(lang)) for l in self.lessons.lessons()]
        )
        self._refresh_panel()
        if self.settings_window is not None:
            try:
                self.settings_window.destroy()
            except Exception:  # noqa: BLE001
                pass
            self.settings_window = self._make_settings_window()
            if hasattr(self.settings_window, "on_close"):
                self.settings_window.on_close = self._quit_from_tray

    def _open_settings(self) -> None:
        if self.settings_window is None:
            return
        try:
            self.settings_window.show()
        except Exception:  # noqa: BLE001
            pass

    def _open_panel(self) -> None:
        """Show the side panel (the beginner's way in)."""

        try:
            self.panel.show()
            self.panel.raise_()
        except Exception:  # noqa: BLE001
            pass

    def _quit_from_tray(self) -> None:
        """Leave, from the tray, from the greeting window, or from the X.

        Closing any of the coach's windows means the student is done, so
        the whole program leaves: the tray icon, the background threads
        and the windows.  Nothing may stay behind in the background.
        """

        self.quit()
        try:
            self.host.quit()
        except Exception:  # noqa: BLE001
            pass

    def _connect_card(self) -> None:
        """Let the card tell us when the user dismissed it."""

        dismissed = getattr(self.card, "dismissed", None)
        if dismissed is not None and hasattr(dismissed, "connect"):
            dismissed.connect(self._card_dismissed)
            return
        # The Tk card has no signal: it calls back instead.
        try:
            self.card.on_click = self._card_dismissed
        except Exception:  # noqa: BLE001
            pass

    # -- banner -----------------------------------------------------
    def _print_banner(self) -> None:
        stats = self.kb.stats()
        lines: list[str] = []
        lines.append("=" * 62)
        lines.append(" Praatao  -  Praat companion coach")
        lines.append("=" * 62)
        lines.append(f" interface     : {self.backend}")
        lines.append(f" knowledge base : {stats['entries']} entries, "
                     f"{stats['aliases']} aliases, bilingual={stats['bilingual']}")
        lines.append(f" lessons        : {len(self.lessons)}")
        lines.append(f" uia sensor     : {'ok' if self.ui else 'MISSING'}")
        lines.append(f" state probe    : {'ok' if self.probe else 'MISSING'}")
        if self.canvas is not None:
            lines.append(" canvas sensor  : ok")
        if self.advisor is not None:
            try:
                lines.append(f" tutor          : {self.advisor.status()}")
            except Exception as exc:
                lines.append(f" tutor          : (status unavailable: {exc})")
        else:
            lines.append(" tutor          : MISSING")
        try:
            from praatao.tutor.llm import LlmConfig

            cfg = LlmConfig.from_env()
            if cfg.allow_vision:
                lines.append(" vision         : ON (pictures may be sent to the model)")
            else:
                lines.append(" vision         : off (set PRAATAO_VISION=1 to allow it)")
        except Exception:  # pragma: no cover
            pass
        lines.append("-" * 62)
        lines.append(" Hover a Praat button to get an explanation.")
        lines.append(" Ctrl+Alt+P  panel     Ctrl+Alt+N  next step")
        lines.append(" Ctrl+Alt+Q  ask       Ctrl+Alt+H  hide all")
        lines.append(" Ctrl+Alt+S  settings  Ctrl+Alt+X  quit")
        lines.append("=" * 62)

        for line in lines:
            print(line)
        print(flush=True)

        # When the program starts without a console window (the packaged
        # build, or pythonw.exe), the banner has to go somewhere the
        # student can still read it.
        try:
            from praatao.launcher import log_line

            for line in lines:
                log_line(line)
        except Exception:  # noqa: BLE001
            pass

    # -- state polling ---------------------------------------------
    def _poll_state(self, now: float) -> None:
        if self.probe is None or self._state_busy:
            return
        if now - self._last_state_poll < STATE_INTERVAL:
            return
        self._last_state_poll = now
        self._state_busy = True

        def worker() -> None:
            try:
                # ``fast()`` reads the window titles and the Objects window
                # through UIA.  It never sends a Praat script, because a
                # script closes whatever menu the user has open.
                snapshot = self.probe.fast()
            except Exception:
                snapshot = None
            try:
                self.state_queue.put_nowait(snapshot)
            except queue.Full:
                pass
            finally:
                self._state_busy = False

        threading.Thread(target=worker, daemon=True).start()

    def _poll_deep_state(self, now: float, mouse_idle: float) -> None:
        """Refresh the details that only a Praat script can give.

        The tier names of a TextGrid and the attributes of the selected
        Sound come from a script, and a script has two costs: it closes
        whatever menu the user has open, and **it pulls Praat to the
        front** (measured: ``Praat.exe --send`` activates the Praat
        window).  The second one is the worse of the two, because the
        student loses the keyboard while they are typing somewhere
        else.

        So the script only goes out when Praat already has the focus:
        then the "jump to the front" is invisible, and the student is
        working in Praat anyway, where the extra detail is useful.

        It also waits until the keyboard is quiet.  A student who is
        typing an annotation in Praat does not move the mouse, so the
        mouse alone cannot tell "reading" from "typing" - and a script
        that lands in the middle of a word is exactly the kind of thing
        that makes the coach feel like it is in the way.
        """

        if self.probe is None or self._deep_busy:
            return
        if now - self._last_deep_poll < DEEP_STATE_INTERVAL:
            return
        if mouse_idle < DEEP_STATE_IDLE:
            return
        if _seconds_since_last_input() < DEEP_STATE_IDLE:
            # The user is typing (or has just typed): not the moment.
            return
        try:
            from praatao.sensors.uia import _menu_popup_open

            if _menu_popup_open():
                return
        except Exception:  # noqa: BLE001
            return
        if not self._praat_has_focus():
            # Another program has the focus.  Sending a script now would
            # pull Praat over it, which is exactly the "Praat keeps
            # jumping to the front" complaint.
            return
        self._last_deep_poll = now
        self._deep_busy = True

        def worker() -> None:
            try:
                if not self._running:
                    # The coach was stopped while this probe was queued:
                    # do not send a script any more, it would close a menu
                    # long after the coach is gone.
                    return
                snapshot = self.probe.snapshot(require_focus=True)
            except Exception:
                snapshot = None
            try:
                self.deep_state_queue.put_nowait(snapshot)
            except queue.Full:
                pass
            finally:
                self._deep_busy = False

        thread = threading.Thread(target=worker, daemon=True)
        self._deep_thread = thread
        thread.start()

    def _drain_state(self) -> None:
        try:
            state = self.state_queue.get_nowait()
        except queue.Empty:
            state = None
        if state is not None:
            self.state = state
            # The buttons under the pointer may have changed with the
            # selection, so the cached hit test is not trusted any more.
            self._hit_cache = None
            if self.advisor is not None:
                try:
                    self.advisor.state = state
                except Exception:
                    pass
            self._refresh_panel()
        # The deep snapshot only adds the tier names and the attributes of
        # the selected Sound; it does not replace the fast state.
        try:
            deep = self.deep_state_queue.get_nowait()
        except queue.Empty:
            deep = None
        if deep is not None and self.state is not None:
            deep.textgrid_tiers = list(deep.textgrid_tiers or [])
            deep.objects = list(self.state.objects or deep.objects or [])
            deep.selected = list(self.state.selected or deep.selected or [])
            deep.editor_open = self.state.editor_open
            deep.editor_object = self.state.editor_object
            self.state = deep
            if self.advisor is not None:
                try:
                    self.advisor.state = deep
                except Exception:
                    pass
            self._refresh_panel()

    # -- panel ------------------------------------------------------
    def _panel_command(self, name: str) -> None:
        if name.startswith("select:"):
            lesson_id = name.split(":", 1)[1]
            self.runner.start(lesson_id)
        elif name == "panel":
            # The tray's "open the panel": the student clicked the icon and
            # expects the coach to come forward.
            self._open_panel()
        elif name == "ask":
            self._open_panel()
            try:
                self.panel.ask_entry.setFocus()
            except Exception:  # noqa: BLE001
                pass
        elif name == "next":
            self.runner.advance()
        elif name == "prev":
            if self.runner.step_index > 0:
                self.runner.step_index -= 1
        elif name == "restart":
            if self.runner.lesson:
                self.runner.start(self.runner.lesson.id)
        elif name == "hide":
            self.card.hide()
            self.spot.hide()
        elif name == "settings":
            self._open_settings()
        elif name == "quit":
            self.quit()
            try:
                self.host.quit()
            except Exception:  # noqa: BLE001
                pass
        self._refresh_panel()

    def _panel_ask(self, question: str) -> str | None:
        """Answer a question without blocking the interface."""

        if self.advisor is None:
            return "advisor unavailable"
        element = self._current_element

        def worker() -> None:
            try:
                advice = self.advisor.ask(question, element=element, state=self.state)
                answer = advice.body if advice else ""
            except Exception as exc:
                answer = f"error: {exc}"
            self.host.invoke(lambda: self.panel.set_answer(answer))

        threading.Thread(target=worker, daemon=True).start()
        return None

    def _refresh_panel(self) -> None:
        lang = self.lang
        state = self.state
        if state is not None:
            names = ", ".join(o.name for o in (state.selected or [])) or "-"
            self.panel.set_state(
                f"{len(state.objects or [])} obj | sel: {names}"
                f"{' | editor' if state.editor_open else ''}"
            )
            if state.error:
                self.panel.set_notice(
                    "Praat 被一个对话框卡住了（多半是脚本报错）。"
                    "关掉那个 Message 框即可恢复。\n"
                    "Praat is stuck behind a modal dialog; dismiss it to recover."
                )
            else:
                self.panel.set_notice("")
        elif self.ui is not None and not self.ui.available():
            self.panel.set_notice(
                "没有检测到 Praat。请先启动 Praat.exe，然后按 Ctrl+Alt+P 回到这里。\n"
                "Praat not detected. Start Praat.exe first."
            )
        lesson = self.runner.lesson
        if lesson is None:
            self.panel.set_lesson(
                "未开始课程 / No lesson" if lang == "zh" else "No lesson running",
                "在下方选一个课程开始。\n\nPick a lesson below to start.",
                (0, 0),
            )
            return
        step = self.runner.next_step()
        if step is None:
            self.panel.set_lesson(
                lesson.title(lang),
                ("课程完成！" if lang == "zh" else "Lesson complete!"),
                self.runner.progress(),
            )
            return
        body = step.tip(lang)
        detail = step.detail(lang)
        if detail:
            body += "\n\n" + detail
        self.panel.set_lesson(lesson.title(lang), body, self.runner.progress())

    # -- hover ------------------------------------------------------
    _current_element = None

    def _element_under_cursor(self, x: int, y: int):
        """The control under the pointer, with the hit test kept.

        A UIA hit test costs 5-9 ms, and the pointer usually stands
        still between two ticks, so the answer is kept and the same
        question is only asked again when the pointer went somewhere
        else.  Without this the coach spent a tenth of a second of
        every second on hit tests that could not have a different
        answer.

        Two rules keep the answer honest:

        * the cache is thrown away when the Praat state changes (the
          buttons under the pointer may have changed with it) and at the
          latest after :data:`HIT_CACHE_TTL` seconds, so a window that
          was moved under a still pointer is picked up;
        * the pointer may only keep the answer while it stays over the
          *same small control*.  A pane (the object list, for instance)
          is bigger than :data:`HIT_CACHE_MAX_AREA`, and inside a pane
          the hit test has to be repeated.
        """

        if self.ui is None:
            return None
        cached = self._hit_cache
        if cached is not None:
            cx, cy, element = cached
            if cx == x and cy == y:
                return element
            if (
                element is not None
                and _is_small_control(element)
                and element.contains_point(x, y)
                and (time.monotonic() - self._hit_cache_at) < HIT_CACHE_TTL
            ):
                # The pointer moved, but it is still over the same
                # button: no hit test needed.
                self._hit_cache = (x, y, element)
                return element
        try:
            element = self.ui.element_at_point(x, y)
        except Exception:
            element = None
        self._hit_cache = (x, y, element)
        self._hit_cache_at = time.monotonic()
        return element

    def _canvas_under_cursor(self, x: int, y: int):
        """The drawing area under the pointer, unless something is on top.

        A modal dialog (Praat's "Formant settings", for instance) sits on
        top of the picture, and the student is asking about the dialog,
        not about the waveform behind it.  So the canvas only counts when
        the window on top of the pointer really is the canvas' own window.
        """
        if self.canvas is None:
            return None
        try:
            region = self.canvas.region_at(x, y)
        except Exception:
            return None
        if region is None:
            return None
        try:
            from praatao.sensors.uia import top_window_at

            top = top_window_at(x, y)
        except Exception:  # noqa: BLE001
            return region
        if not top:
            return region
        own = int(getattr(region, "hwnd", 0) or 0)
        canvas = int(getattr(region, "canvas_hwnd", 0) or 0)
        if top not in (own, canvas) and own and canvas:
            # Something else (a dialog) is on top of the drawing area.
            return None
        return region

    def _handle_hover(self, x: int, y: int) -> None:
        if self._card_visible() and self._pointer_on_card(x, y):
            # The pointer is on our own card - which is where the pin and
            # the close button live.  The card is still about the same
            # subject, so it stays; without this the card would dismiss
            # itself the moment the pointer moved onto it, and the pin
            # button could never be reached.
            self._misses = 0
            return

        if not self._praat_has_focus():
            # The student is working in another program.  Nothing of Praat
            # is touched at all: a UIA hit test can activate the Praat
            # window (measured), and that would pull Praat over the
            # program the student is typing in.
            self._misses = 0
            # And nothing is explained either: the card is about Praat,
            # so it has to go when the student leaves Praat.
            if self._card_visible() and not self.card.pinned:
                self._dismiss_hover()
            return

        # A menu is open: the UIA hit test would close it (a hit test over
        # the menu bar of an open menu dismisses that menu), so the
        # element is taken from the popup's own item list instead.
        if self._menu_open():
            popup_item = self._popup_item_under_cursor(x, y)
            if popup_item is not None:
                self._advise_element(popup_item, x, y)
            else:
                # The pointer is on the menu bar, not on an item: leave
                # the menu alone and keep whatever the card shows.
                self._misses = 0
            return

        region = self._canvas_under_cursor(x, y)
        if region is not None:
            self._handle_canvas_hover(region, x, y)
            return

        element = self._element_under_cursor(x, y)
        if element is None or not (element.name or "").strip():
            # UIA hit tests fail intermittently.  Give the overlay a few
            # frames of grace before it dismisses the card, so a single
            # unlucky COM call does not make the card flicker.
            self._misses += 1
            if DEBUG:
                print(f"[debug] miss #{self._misses} at ({x},{y}) "
                      f"el={element!r}")
            if self._misses <= HOVER_MISS_GRACE:
                return
            self._dismiss_hover()
            return
        self._advise_element(element, x, y)

    def _menu_open(self) -> bool:
        """Is a Praat menu popup on screen?"""

        try:
            from praatao.sensors.uia import _menu_popup_open

            return bool(_menu_popup_open())
        except Exception:  # noqa: BLE001
            return False

    def _praat_has_focus(self) -> bool:
        """Does Praat own the foreground window right now?

        A Praat script activates the Praat window, so the coach only
        sends one while Praat is already in front.
        """

        try:
            from praatao.sensors.uia import praat_has_focus

            return bool(praat_has_focus())
        except Exception:  # noqa: BLE001
            return False

    def _popup_item_under_cursor(self, x: int, y: int):
        """The menu item under the cursor, if a menu is open.

        The items come from the popup's own tree, not from a hit test: a
        UIA hit test over the menu bar dismisses the menu that is open.
        """

        if self.ui is None:
            return None
        now = time.monotonic()
        cached = self._popup_items
        if cached is None or (now - cached[0]) > POPUP_CACHE_TTL:
            try:
                items = self.ui.open_popup_items()
            except Exception:  # noqa: BLE001
                items = []
            self._popup_items = (now, items)
        else:
            items = cached[1]
        for item in items:
            rect = item.rect
            if not rect:
                continue
            if rect[0] <= x < rect[2] and rect[1] <= y < rect[3]:
                return item
        return None

    def _advise_element(self, element, x: int, y: int) -> None:
        """Explain the control under the cursor."""

        self._current_element = element
        self._misses = 0

        raw_name = (element.name or "").strip()

        key = normalize_key(raw_name)
        stamp = self._state_stamp()

        if key != self._last_key:
            # A new control under the cursor: restart the dwell timer.
            if DEBUG:
                print(f"[debug] new key {key!r} (was {self._last_key!r})")
            self._last_key = key
            # The pointer has been resting on the new control since it
            # stopped moving, not since this tick noticed it.  The mouse
            # is watched every 10 ms, so that moment is known to within
            # 10 ms instead of a whole tick, and the card does not have
            # to wait for the tick to find out that the pointer is still.
            # A card that was sent away on purpose still has to wait for
            # the dwell, so the later of the two moments is used.
            self._hover_since = max(self._mouse_moved_at, self._dismissed_at)
            self._shown_signature = None
        else:
            signature = (key, stamp)
            if signature == self._shown_signature and self._card_visible():
                return

        if self.advisor is None:
            self._dismiss_hover()
            return

        # Dwell: the cursor must rest on the control for a moment, otherwise
        # the card flickers while the user sweeps across the window.
        waited = time.monotonic() - self._hover_since
        if waited < DWELL_MS / 1000.0:
            if DEBUG:
                print(f"[debug] dwell {waited:.3f}")
            return

        try:
            advice = self.advisor.advise(
                element,
                state=self.state,
                on_llm=self._on_llm_answer(key),
                on_image=self._on_llm_image(key),
            )
        except Exception as exc:
            print(f"[praatao] advise failed: {exc}", file=sys.stderr)
            self._dismiss_hover()
            return

        if not advice or not advice.body:
            if DEBUG:
                print("[debug] empty advice -> dismiss")
            self._dismiss_hover()
            return
        if DEBUG:
            print(f"[debug] showing {advice.headline!r}")

        source = ""
        if advice.source:
            source = source_label(advice.source)

        body = advice.body
        if not getattr(element, "enabled", True):
            body = (
                "（这个按钮现在是灰的：Praat 把它禁用了。通常是选中条件没满足。）\n"
                "(This button is greyed out right now: Praat has disabled it, "
                "usually because the selection does not qualify.)\n\n" + body
            )

        self.card.show(
            advice.headline,
            body,
            anchor=(x, y),
            rect=element.rect,
            source=source,
            signature=(key, stamp),
        )
        self._shown_signature = (key, stamp)
        self._current_rect = element.rect
        self._left_since = 0.0
        if element.rect:
            self.spot.show(element.rect)
        else:
            self.spot.hide()
        # The spotlight is a separate window and can overlap the card, so the
        # card has to be put on top of it again.
        self._raise_card()

    def _hide_panel_over(self, region) -> bool:
        """Hide the side panel while it stands in front of the canvas.

        The panel is put back right after the grab.  Hiding it for the
        fraction of a second it takes is cheaper than showing the student a
        picture of their own side panel.
        """

        checker = getattr(self.panel, "is_visible", None)
        if checker is None:
            return False
        try:
            if not checker():
                return False
            rect = region.rect
            hole = self.panel.geometry()
        except Exception:  # noqa: BLE001
            return False
        if not hole or len(hole) != 4:
            return False
        if hole[2] <= rect[0] or hole[0] >= rect[2] or hole[3] <= rect[1] or hole[1] >= rect[3]:
            return False
        try:
            self.panel.hide()
            self.pump()
            # The compositor needs a moment to take the window off the screen.
            time.sleep(0.06)
        except Exception:  # noqa: BLE001
            return False
        return True

    def _capture_rect(self, region) -> tuple[int, int, int, int]:
        """The part of the canvas worth photographing.

        The grab reads the screen, so our own side panel would end up in the
        picture.  The panel is cut out: the largest remaining band is used.
        """

        rect = region.rect
        panel = getattr(self.panel, "geometry", None)
        if panel is None:
            return rect
        try:
            hole = panel()
        except Exception:  # noqa: BLE001
            return rect
        if not hole or len(hole) != 4:
            return rect
        left, top, right, bottom = rect
        hx0, hy0, hx1, hy1 = hole
        if hx1 <= left or hx0 >= right or hy1 <= top or hy0 >= bottom:
            return rect  # no overlap

        candidates = [
            (left, top, right, min(bottom, hy0)),
            (left, max(top, hy1), right, bottom),
            (left, max(top, hy0), min(right, hx0), min(bottom, hy1)),
            (max(left, hx1), max(top, hy0), right, min(bottom, hy1)),
        ]
        best = rect
        best_area = 0
        for candidate in candidates:
            area = max(0, candidate[2] - candidate[0]) * max(0, candidate[3] - candidate[1])
            if area > best_area:
                best, best_area = candidate, area
        return best if best_area > 4000 else rect

    def _handle_canvas_hover(self, region, x: int, y: int) -> None:
        """Explain Praat's drawing area."""

        self._current_element = None
        if self.advisor is None:
            return
        key = f"canvas:{region.window_title}:{region.rect}"
        stamp = self._state_stamp()
        if key == self._last_key and (key, stamp) == self._shown_signature \
                and self._card_visible():
            return
        if key != self._last_key:
            self._last_key = key
            # The pointer has been resting on the drawing area since it
            # stopped moving, not since this tick noticed it.
            self._hover_since = max(self._mouse_moved_at, self._dismissed_at)
            self._shown_signature = None

        waited = time.monotonic() - self._hover_since
        if waited < DWELL_MS / 1000.0:
            return

        image = None
        guess = None
        try:
            if self.canvas is not None and self.canvas.is_visible(region) \
                    and self._praat_has_focus():
                # The grab reads the screen, so our own windows would end up
                # in the picture.  The card is hidden, and so is the side
                # panel when it stands in the way.
                #
                # The grab is only done while Praat is the application in
                # front: otherwise the picture would show whatever window
                # happens to cover the drawing area.
                if self._card_visible():
                    self.card.hide()
                    self.pump()
                panel_hidden = self._hide_panel_over(region)
                rect = region.rect if panel_hidden else self._capture_rect(region)
                image = self.canvas.capture(region, rect=rect)
                if panel_hidden:
                    self.panel.show()
                guess = self.canvas.classify(image)
        except Exception:
            image = None

        kind = guess.kind if guess is not None else "unknown"
        try:
            advice = self.advisor.advise_canvas(
                window_title=region.window_title,
                object_name=region.object_name,
                kind=kind,
                confidence=guess.confidence if guess else 0.0,
                image=image,
                state=self.state,
                on_llm=self._on_llm_answer(key),
            )
        except Exception as exc:
            print(f"[praatao] canvas advice failed: {exc}", file=sys.stderr)
            return
        if not advice or not advice.body:
            return
        if DEBUG:
            print(f"[debug] showing canvas {advice.headline!r} ({kind})")

        self.card.show(
            advice.headline,
            advice.body,
            anchor=(x, y),
            rect=region.rect,
            source=source_label(advice.source),
            signature=(key, stamp),
            image=image,
        )
        self._shown_signature = (key, stamp)
        self._current_rect = region.rect
        self._left_since = 0.0
        self.spot.show(region.rect)
        self._raise_card()

    def _raise_card(self) -> None:
        """Keep the card above the spotlight, the panel and every overlay."""

        # The panel first, then the card: both are always-on-top windows,
        # and the card has to end up above the panel.
        panel_raiser = getattr(self.panel, "raise_", None)
        if panel_raiser is not None:
            try:
                panel_raiser()
            except Exception:  # noqa: BLE001
                pass
        raiser = getattr(self.card, "raise_", None)
        if raiser is None:
            return
        try:
            raiser()
        except Exception:  # noqa: BLE001
            pass

    def _on_llm_answer(self, key: str):
        """Build the callback that delivers a late model answer."""

        def deliver(advice) -> None:
            def apply() -> None:
                if self._last_key != key:
                    return
                if not self._card_visible():
                    return
                body = getattr(advice, "body", "") or ""
                if not body:
                    return
                updater = getattr(self.card, "update_body", None)
                if updater is None:
                    return
                updater(body, source_label(getattr(advice, "source", "") or ""))

            self.host.invoke(apply)

        return deliver

    def _on_llm_image(self, key: str):
        """Build the callback that delivers a drawn teaching picture."""

        def deliver(data: bytes) -> None:
            def apply() -> None:
                if self._last_key != key:
                    return
                if not self._card_visible():
                    return
                setter = getattr(self.card, "set_image", None)
                if setter is None:
                    return
                setter(data)

            self.host.invoke(apply)

        return deliver

    def _handle_click(self, x: int, y: int) -> None:
        """What a mouse press means.

        The application owns this, rather than the card, because Windows
        gives the first click on an inactive window to activating it: a pin
        button inside a tool window would otherwise swallow its first click.
        The application polls the mouse anyway, so it can answer for itself.
        """

        if self._pointer_on_card(x, y):
            for name in ("pin_rect", "close_rect"):
                getter = getattr(self.card, name, None)
                if getter is None:
                    continue
                try:
                    rect = getter()
                except Exception:  # noqa: BLE001
                    rect = None
                if rect and rect[0] <= x < rect[2] and rect[1] <= y < rect[3]:
                    if name == "pin_rect":
                        self.card.set_pinned(not self.card.pinned)
                    else:
                        self._dismiss_hover()
                    return
            # A click on the card itself dismisses it.
            if not self.card.pinned:
                self._dismiss_hover()
            return

        # A click anywhere else means the user is working in Praat.
        if not self.card.pinned:
            self._dismiss_hover()

    def _pointer_on_card(self, x: int, y: int) -> bool:
        """Is the cursor on the card itself?"""

        rect = self._card_rect()
        if rect is None:
            return False
        return (rect[0] <= x < rect[2]) and (rect[1] <= y < rect[3])

    def _card_visible(self) -> bool:
        checker = getattr(self.card, "is_visible", None)
        if checker is not None:
            try:
                return bool(checker())
            except Exception:  # noqa: BLE001
                return False
        try:
            return bool(self.card.win.winfo_viewable())
        except Exception:  # noqa: BLE001
            return False

    def _card_rect(self) -> tuple[int, int, int, int] | None:
        getter = getattr(self.card, "geometry", None)
        if getter is None:
            return None
        try:
            return getter()
        except Exception:  # noqa: BLE001
            return None

    def _card_dismissed(self) -> None:
        """The user clicked the card: close it unless it is pinned."""

        if self.card.pinned:
            return
        self._dismiss_hover()

    def _state_stamp(self) -> tuple:
        """A cheap fingerprint of the Praat state, so the card refreshes when
        the selection changes rather than going stale."""
        state = self.state
        if state is None:
            return ()
        try:
            selected = tuple(o.name for o in (state.selected or []))
        except Exception:
            selected = ()
        return (selected, bool(getattr(state, "editor_open", False)))

    def _dismiss_hover(self) -> None:
        self._last_key = None
        self._hover_since = 0.0
        self._misses = 0
        self._shown_signature = None
        self._current_rect = None
        # The card was sent away on purpose, so the next one has to wait
        # for the dwell again - even when the pointer did not move.
        self._dismissed_at = time.monotonic()
        self._left_since = 0.0
        self.card.hide()
        self.spot.hide()

    # -- auto-hide --------------------------------------------------
    def _update_auto_hide(self, x: int, y: int) -> None:
        """Hide the card two seconds after the pointer has left it."""

        if not self._card_visible() or self.card.pinned:
            self._left_since = 0.0
            return
        over_card = False
        rect = self._card_rect()
        if rect is not None:
            over_card = (rect[0] <= x < rect[2]) and (rect[1] <= y < rect[3])
        over_target = False
        if self._current_rect is not None:
            left, top, right, bottom = self._current_rect
            over_target = (left - 8) <= x <= (right + 8) and (top - 8) <= y <= (bottom + 8)
        if over_card or over_target:
            self._left_since = 0.0
            return
        now = time.monotonic()
        if self._left_since == 0.0:
            self._left_since = now
            return
        if now - self._left_since >= AUTO_HIDE_SECONDS:
            self._dismiss_hover()

    # -- main loop --------------------------------------------------
    def _tick(self) -> None:
        if not self._running:
            return
        now = time.time()
        x, y = cursor_pos()
        if self._last_mouse_pos != (x, y):
            self._last_mouse_pos = (x, y)
            self._mouse_moved_at = time.monotonic()
        mouse_idle = time.monotonic() - self._mouse_moved_at

        self._poll_state(now)
        self._poll_deep_state(now, mouse_idle)
        self._drain_state()

        for hot in self.hotkeys.poll():
            self._handle_hotkey(hot)

        self._handle_hover(x, y)
        self._update_auto_hide(x, y)

        if self.runner.lesson is not None:
            step = self.runner.sync(self.state)
            if step is not None:
                self._refresh_panel()

        self.host.after(POLL_MS, self._tick)

    def _handle_hotkey(self, hot: str) -> None:
        if hot == "panel":
            self.panel.toggle()
        elif hot == "next":
            self.runner.advance()
            self._refresh_panel()
        elif hot == "restart":
            if self.runner.lesson:
                self.runner.start(self.runner.lesson.id)
            self._refresh_panel()
        elif hot == "hide":
            self._dismiss_hover()
            self.spot.hide()
        elif hot == "ask":
            self.panel.show()
            try:
                self.panel.ask_entry.setFocus()
            except Exception:  # noqa: BLE001
                pass
        elif hot == "settings":
            self._open_settings()
        elif hot == "pin":
            self.card.set_pinned(not self.card.pinned)
        elif hot == "escape":
            self.card.set_pinned(False)
            self._dismiss_hover()
        elif hot == "quit":
            # Stop the coach without hunting for its console window.
            self.quit()
            try:
                self.host.quit()
            except Exception:  # noqa: BLE001
                pass

    # -- lifecycle --------------------------------------------------
    def pump(self) -> None:
        """Process pending GUI events (used by the capture scripts)."""

        pump = getattr(self.host, "pump", None)
        if pump is not None:
            pump()

    def run(self) -> None:
        self.host.after(MOUSE_POLL_MS, self._mouse_poll)
        self.host.after(POLL_MS, self._tick)
        self.host.mainloop()

    def _mouse_poll(self) -> None:
        """Watch the mouse button, fast.

        The main tick runs every 45 ms, and a quick click can be shorter
        than that - then the button is already up again when the tick
        looks, and the click is lost.  The button state is read here
        every 10 ms instead; reading it is a single API call, so this
        costs almost nothing.

        The position is read here as well.  This loop runs ten times
        more often than the main tick, so the moment the pointer comes
        to rest is known to within 10 ms, and the card does not have to
        wait for the next tick to find out that the pointer is still.
        """

        if not self._running:
            return
        x, y = cursor_pos()
        if self._last_mouse_pos != (x, y):
            self._last_mouse_pos = (x, y)
            self._mouse_moved_at = time.monotonic()
        down = mouse_button_down(1)
        if down and not self._last_mouse_down:
            self._handle_click(x, y)
        self._last_mouse_down = down
        self.host.after(MOUSE_POLL_MS, self._mouse_poll)

    def quit(self) -> None:
        if getattr(self, "_quitting", False):
            return
        self._quitting = True
        self._running = False
        # A probe that is still in flight would send its script a moment
        # later, and Praat closes an open menu when a script runs.  Wait
        # for it, so nothing is left over after the coach is gone.
        thread = self._deep_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=3.0)
        try:
            self.card.destroy()
            self.spot.destroy()
            self.panel.destroy()
            self.host.destroy()
        except Exception:  # noqa: BLE001
            pass
        for extra in ("settings_window", "toast", "tray"):
            widget = getattr(self, extra, None)
            if widget is None:
                continue
            try:
                widget.destroy()
            except Exception:  # noqa: BLE001
                pass
        # Let Qt really take the windows off the screen: a leftover card
        # would sit on top of the next thing the user opens.
        for _ in range(3):
            try:
                self.host.pump()
            except Exception:  # noqa: BLE001
                break
            time.sleep(0.05)


def _ensure_qt_application() -> None:
    """Create the Qt application early.

    Qt's local socket (used to talk to an already running coach) needs
    a QApplication to exist, and the host reuses the one that is there.
    """

    try:
        from praatao.ui.qt.host import qt_available

        if not qt_available():
            return
        from PySide6 import QtWidgets

        if QtWidgets.QApplication.instance() is None:
            QtWidgets.QApplication([])
    except Exception:  # noqa: BLE001
        pass


def main(argv: list[str] | None = None) -> int:
    if getattr(sys, "frozen", False):
        # The packaged executable has no console window; the prints go
        # nowhere, so send them to the void instead of crashing.
        try:
            from praatao.launcher import no_console

            no_console()
        except Exception:  # noqa: BLE001
            pass

    parser = argparse.ArgumentParser(description="Praatao - a Praat companion coach")
    parser.add_argument("--lang", choices=("zh", "en"), default=None,
                        help="language for tips (default: the one saved in the "
                             "settings window)")
    parser.add_argument("--no-llm", action="store_true",
                        help="never contact a language model")
    parser.add_argument("--vision", action="store_true",
                        help="allow sending Praat pictures to the model "
                             "(a picture can show a participant's voice)")
    parser.add_argument("--ui", choices=("auto", "qt", "tk"), default="auto",
                        help="which front-end to use")
    parser.add_argument("--selftest", action="store_true",
                        help="report what the sensors can see and exit")
    parser.add_argument("--no-praat", action="store_true",
                        help="do not start Praat when it is not running")
    parser.add_argument("--quiet", action="store_true",
                        help="no greeting window, no tray icon")
    args = parser.parse_args(argv)

    settings = Settings.load()
    if args.vision or settings.allow_vision:
        os.environ["PRAATAO_VISION"] = "1"

    lang = args.lang or settings.lang
    if args.selftest:
        return selftest(lang)

    # The Qt application has to exist before the single-instance check.
    _ensure_qt_application()

    # Only one coach at a time.  A second double-click does not start a
    # second coach: it brings the running one forward and leaves.
    holder: dict[str, object] = {}

    def _bring_forward() -> None:
        app = holder.get("app")
        if app is not None:
            try:
                app._open_panel()
            except Exception:  # noqa: BLE001
                pass

    instance = None
    try:
        from praatao.launcher import SingleInstance

        instance = SingleInstance(_bring_forward)
        if not instance.acquire():
            print("Praatao is already running; the running one was brought forward.")
            return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[Praatao] the single-instance check failed: {exc}")

    if not args.no_praat:
        _start_praat_if_needed(lang)

    app = Praatao(lang=lang, use_llm=not args.no_llm, ui_backend=args.ui,
                   settings=settings)
    holder["app"] = app
    if not args.quiet:
        _greet(app, lang)
    try:
        app.run()
    except KeyboardInterrupt:
        app.quit()
    finally:
        if instance is not None:
            try:
                instance.release()
            except Exception:  # noqa: BLE001
                pass
    return 0


def _start_praat_if_needed(lang: str = "zh") -> None:
    """Make sure there is something to explain.

    A beginner who double-clicks the icon expects Praat to be there.  If
    it is not running yet, it is started and brought to the front.
    """

    try:
        from praatao.launcher import ensure_praat

        result = ensure_praat(start_if_missing=True)
    except Exception:  # noqa: BLE001
        return
    if not result.get("failed"):
        return
    message = (
        "Praat 没有找到：请手动打开它，然后双击 Praatao 助教。"
        if lang == "zh" else
        "Praat was not found: open it by hand, then start Praatao again."
    )
    print(f"[Praatao] {message}")


def _greet(app: "Praatao", lang: str = "zh") -> None:
    """Say hello: a small window, and an icon in the system tray."""

    try:
        from praatao.launcher import Toast, Tray

        toast = Toast(app.root)
        app.toast = toast
        # Closing the greeting window is closing the coach.
        if hasattr(toast, "on_close"):
            toast.on_close = app._quit_from_tray
        if lang == "zh":
            toast.show_message(
                "Praatao 助教已启动",
                "在 Praat 里把鼠标停在任何按钮上，就会出现讲解。\n"
                "托盘里那个橙色的 P 图标里，有侧栏、设置和退出。",
                actions=[
                    ("打开侧栏", app._open_panel),
                    ("设置", app._open_settings),
                    ("退出", app._quit_from_tray),
                ],
            )
        else:
            toast.show_message(
                "Praatao is running",
                "Rest the pointer on any Praat button and an explanation "
                "appears.\nThe orange P in the tray holds the panel, the "
                "settings and the way out.",
                actions=[
                    ("Open the panel", app._open_panel),
                    ("Settings", app._open_settings),
                    ("Quit", app._quit_from_tray),
                ],
            )
        tray = Tray(app.root, on_command=app._panel_command, lang=lang)
        app.tray = tray
        tray.show()
    except Exception as exc:  # noqa: BLE001
        print(f"[Praatao] the greeting failed: {exc}")


def selftest(lang: str = "zh") -> int:
    """Print what the sensors can currently see.  No mouse, no windows."""
    from praatao.sensors.praat_state import PraatStateProbe, praat_available
    from praatao.sensors.uia import PraatUI, normalize_name

    ui = PraatUI()
    print("praat available:", praat_available())
    for window in ui.windows():
        print(f"window: {window.kind:8s} {window.title!r} {window.rect}")
        for element in ui.tree(window, max_depth=3):
            if element.name:
                print(f"    [{element.control_type:16s}] {normalize_name(element.name)!r} {element.rect}")
    probe = PraatStateProbe(paths.PRAAT_EXE, paths.ensure_state_dir())
    state = probe.snapshot()
    print("state:", state)
    kb = load_default()
    print("kb entries:", len(kb))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
