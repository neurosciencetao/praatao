"""UI Automation sensor for Praat (Windows).

This module answers the question the overlay asks on every mouse move:
*what is under the cursor right now?*  It talks to Windows UI Automation
through the `uiautomation` package (yinkaisheng) and never raises when Praat
is not running: every public method degrades to an empty result instead.

Nothing in here imports from :mod:`praatao.tutor` or :mod:`praatao.ui`; the
module only produces plain data (``Element`` / ``UiaWindow`` dataclasses).

Ground truth observed on this machine (Praat 6.x, Windows)
-----------------------------------------------------------
* Objects window: class ``PraatShell1 Praat``, title ``Praat Objects``.
* Picture window: class ``PraatChildWindow1 Praat``, title ``Praat Picture``.
* Editor window: class ``PraatChildWindow1 Praat``, title is the **list label**
  (``2. Sound demo_vowel``), *not* ``Sound demo_vowel``.
* Buttons are exposed with exact names: ``Rename...``, ``Copy...``,
  ``Inspect``, ``Info``, ``Remove``, ``Sound help``, ``View & Edit``,
  ``Play``, ``To Intensity...``.
* Dynamic action buttons (a Sound is selected) carry leading U+202F and a
  trailing ``>``: ``'\\u202f\\u202f   Draw  >'``.
* Object list items are ``ListItemControl`` named ``1. Sound demo_vowel``.
* Menu bar items: ``Praat``, ``New``, ``Open``, ``Save``, ``Help``.
* A menu popup shows up as a ``MenuControl`` (a separate ``#32768`` window)
  that UIA nevertheless exposes **as a child of the Objects window**; its
  items are ``MenuItemControl`` children such as ``Read from file...\\tCtrl-O``.

Performance notes / 性能说明
---------------------------
``element_at_point`` is the hot path (called on every mouse move).  It uses
``uiautomation.ControlFromPoint`` for the hit test and only walks *up* the
parent chain, so it never rebuilds the whole tree.  Window handles are cached
for :data:`PraatUI.WINDOW_CACHE_TTL` seconds.  ``tree()`` / ``find()`` are
allowed to be slow.
"""

from __future__ import annotations

import re
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

try:  # pragma: no cover - import guard, uiautomation is Windows only
    import uiautomation as auto
except Exception:  # pragma: no cover
    auto = None  # type: ignore[assignment]

try:  # pragma: no cover - pywin32 is optional but present on this machine
    import win32gui
except Exception:  # pragma: no cover
    win32gui = None  # type: ignore[assignment]

try:  # pragma: no cover - used to lift the foreground lock
    import win32api
    import win32process
except Exception:  # pragma: no cover
    win32api = None  # type: ignore[assignment]
    win32process = None  # type: ignore[assignment]

# Win32 message constants (hard coded so win32con is not a hard dependency).
_WM_CANCELMODE = 0x001F
_WM_KEYDOWN = 0x0100
_WM_KEYUP = 0x0101
_VK_ESCAPE = 0x1B
#: Win32 class of the standard menu popup window.
_MENU_WINDOW_CLASS = "#32768"
#: ``GetWindow(hwnd, GW_OWNER)``: the window a popup menu belongs to.
_GW_OWNER = 4
#: UIA control type of a menu separator (no name, cannot be activated).
_SEPARATOR_CONTROL = "SeparatorControl"

__all__ = [
    "Element",
    "UiaWindow",
    "PraatUI",
    "normalize_name",
    "classify_window",
    "praat_available",
    "seconds_since_last_input",
]


# --------------------------------------------------------------------------
# Name normalisation
# --------------------------------------------------------------------------

#: U+202F NARROW NO-BREAK SPACE, Praat uses it to indent dynamic buttons.
_NARROW_NBSP = "\u202f"
#: U+00A0 NO-BREAK SPACE.
_NBSP = "\u00a0"

_WS_RUN = re.compile(r"\s+")
_TRAILING_ARROW = re.compile(r"\s*>\s*$")
_TRAILING_COLON = re.compile(r"\s*:\s*$")
_INDEX_PREFIX = re.compile(r"^\d+\.\s+")
#: Known Praat dialogs that are *not* editor windows.
_NON_EDITOR_TITLE = re.compile(r"^about\b", re.IGNORECASE)


def normalize_name(raw: str) -> str:
    """Normalise a raw UIA name into a stable lookup key.

    Exact rules, applied in this order:

    1. ``None``/empty input -> ``''``.
    2. Cut a tab-separated accelerator suffix: the part after the first
       ``\\t`` is dropped, so ``'Read from file...\\tCtrl-O'`` becomes
       ``'Read from file...'``.
    3. U+202F (narrow no-break space) and U+00A0 (no-break space) become
       ordinary spaces.
    4. Every run of whitespace collapses into a single space, and the result
       is trimmed.
    5. A trailing ``'>'`` (plus the whitespace around it) is removed:
       ``'\\u202f\\u202f   Draw  >'`` becomes ``'Draw'``.
    6. A trailing ``':'`` is removed: ``'Objects:'`` becomes ``'Objects'``.
       Rules 5 and 6 are applied twice, so ``'Sound > :'`` becomes ``'Sound'``.
    7. A leading list index ``'N. '`` is removed:
       ``'1. Sound demo_vowel'`` becomes ``'Sound demo_vowel'``.

    The trailing ellipsis ``'...'`` is **kept**: it is meaningful in Praat
    (a button with ``...`` opens a dialog).

    >>> normalize_name('\\u202f\\u202f   Draw  >')
    'Draw'
    >>> normalize_name('Read from file...\\tCtrl-O')
    'Read from file...'
    >>> normalize_name('1. Sound demo_vowel')
    'Sound demo_vowel'
    """
    if not raw:
        return ""
    text = str(raw)
    # 2. accelerator suffix
    text = text.split("\t", 1)[0]
    # 3. exotic spaces
    text = text.replace(_NARROW_NBSP, " ").replace(_NBSP, " ")
    # 4. collapse whitespace runs
    text = _WS_RUN.sub(" ", text).strip()
    # 5. trailing '>' and 6. trailing ':' (two passes, so 'Sound > :' works)
    for _ in range(2):
        text = _TRAILING_ARROW.sub("", text)
        text = _TRAILING_COLON.sub("", text)
    # 7. leading list index
    text = _INDEX_PREFIX.sub("", text)
    return text.strip()


def classify_window(title: str, class_name: str = "") -> str:
    """Classify a Praat top-level window.

    Returns one of ``'objects'``, ``'picture'``, ``'editor'`` or ``'other'``.

    * ``Praat Objects`` -> ``'objects'`` (the shell).
    * ``Praat Picture`` -> ``'picture'`` (the picture window).
    * Any other Praat window whose title looks like an object label
      (``'2. Sound demo_vowel'`` or a bare ``'Sound demo_vowel'``) ->
      ``'editor'``.
    * Everything else -> ``'other'``.
    """
    t = (title or "").strip()
    cls = (class_name or "").strip()
    if t == "Praat Objects":
        return "objects"
    if t == "Praat Picture":
        return "picture"
    if not cls.lower().startswith("praat"):
        return "other"
    if _NON_EDITOR_TITLE.match(t):
        return "other"
    if _INDEX_PREFIX.match(t):
        return "editor"
    if t and not t.lower().startswith("praat"):
        return "editor"
    return "other"


# --------------------------------------------------------------------------
# Plain data
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Element:
    """One UIA element inside a Praat window."""

    name: str  # raw UIA name (may contain U+202F and '>' suffixes)
    control_type: str  # 'ButtonControl', 'MenuItemControl', 'ListItemControl', ...
    automation_id: str
    hwnd: int
    rect: tuple[int, int, int, int] | None  # (left, top, right, bottom) screen px
    window_title: str
    depth: int = 0
    enabled: bool = True

    @property
    def key(self) -> str:
        """Normalised lookup key, see :func:`normalize_name`."""
        return normalize_name(self.name)

    def contains_point(self, x: int, y: int) -> bool:
        """True when the screen point ``(x, y)`` falls inside the element."""
        if self.rect is None:
            return False
        left, top, right, bottom = self.rect
        return left <= x < right and top <= y < bottom


@dataclass(frozen=True)
class UiaWindow:
    """One Praat top-level window."""

    hwnd: int
    title: str
    class_name: str
    rect: tuple[int, int, int, int]
    kind: str  # 'objects' | 'picture' | 'editor' | 'other'


# --------------------------------------------------------------------------
# Small safe helpers (UIA raises on stale elements)
# --------------------------------------------------------------------------


def _prop(obj: Any, name: str, default: Any = None) -> Any:
    """Read a UIA property without ever raising.

    UIA properties are read through COM, so they blow up with a COMError
    when the element disappears between the tree walk and the property read.
    """
    try:
        return getattr(obj, name)
    except Exception:
        return default


def _text(obj: Any, name: str) -> str:
    """Read a UIA property as a string ('' when unavailable)."""
    value = _prop(obj, name, "")
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _number(obj: Any, name: str) -> int:
    """Read a UIA property as an int (0 when unavailable)."""
    value = _prop(obj, name, 0)
    try:
        return int(value)
    except Exception:
        return 0


def _safe_rect(control: Any) -> tuple[int, int, int, int] | None:
    try:
        rect = control.BoundingRectangle
    except Exception:
        return None
    if rect is None:
        return None
    try:
        return (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))
    except Exception:
        return None


def _rect_contains(
    rect: tuple[int, int, int, int] | None, x: int, y: int
) -> bool:
    if rect is None:
        return False
    left, top, right, bottom = rect
    return left <= x < right and top <= y < bottom


#: Window classes / titles that identify a tooltip rather than a real
#: control.  Praat calls its object-list tooltip a "pip": its UIA name is
#: ``PipWindow``, its Win32 window class is ``MouseInc`` and its window text
#: is ``PipWindow``.  It pops up over the row under the cursor and can even
#: become the foreground window, which then swallows clicks.
_TOOLTIP_CLASSES = ("pipwindow", "tooltips_class32", "tooltipwindow",
                    "bosa_sdm_msftedit", "mouseinc")


def _is_tooltip(control: Any) -> bool:
    """Is this control a tooltip / "pip" window rather than a real control?"""
    name = _text(control, "Name").strip().casefold()
    if name in ("pipwindow", "tooltip", "tooltips_class32"):
        return True
    class_name = _text(control, "ClassName").strip().casefold()
    if any(marker in class_name for marker in _TOOLTIP_CLASSES):
        return True
    return False


def _tooltip_windows() -> list[int]:
    """Visible tooltip / "pip" windows on this desktop."""
    if win32gui is None:
        return []
    found: list[int] = []

    def _find(hwnd: int, _extra: object) -> None:
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return
            class_name = (win32gui.GetClassName(hwnd) or "").casefold()
            title = (win32gui.GetWindowText(hwnd) or "").casefold()
        except Exception:
            return
        if class_name in _TOOLTIP_CLASSES or title in ("pipwindow", "tooltip"):
            found.append(hwnd)

    try:
        win32gui.EnumWindows(_find, None)
    except Exception:
        return []
    return found


def _menu_popup_windows() -> list[int]:
    """Every Win32 menu popup (class ``#32768``) on the desktop.

    ``FindWindowEx`` walks the chain of windows of that class directly.
    Enumerating every top-level window instead costs 0.36 ms on this
    machine (there are about 800 of them), and the hover loop asks this
    question twenty times a second.
    """

    if win32gui is None:
        return []
    found: list[int] = []
    hwnd = 0
    while True:
        try:
            hwnd = int(win32gui.FindWindowEx(0, hwnd, _MENU_WINDOW_CLASS, None) or 0)
        except Exception:
            break
        if not hwnd:
            break
        found.append(hwnd)
    return found


def _praat_owned_popup(hwnd: int) -> bool:
    """Is this menu popup a visible one that belongs to Praat?"""

    try:
        if not win32gui.IsWindowVisible(hwnd):
            return False
        owner = win32gui.GetWindow(hwnd, _GW_OWNER)
        if not owner:
            return False
        owner_class = (win32gui.GetClassName(owner) or "")
    except Exception:
        return False
    return "praat" in owner_class.casefold()


def _menu_popup_open() -> bool:
    """Is a **Praat** menu popup on screen?

    Praat's menus are standard Win32 popups: their window class is
    ``#32768``.  That class is not unique - every application on the
    desktop uses it - so the owner window is checked as well, and only a
    popup owned by a Praat window counts.

    This matters because running a Praat script (the state probe does that
    every second) makes Praat close whatever menu is open.  The probe
    therefore has to stand down while the student is choosing something
    from a menu.
    """

    for hwnd in _menu_popup_windows():
        if _praat_owned_popup(hwnd):
            return True
    return False


def seconds_since_last_input() -> float:
    """How long ago the user last pressed a key or moved the mouse.

    Windows keeps the time of the last input event, so one API call
    answers the question "is somebody typing right now?".  The deep
    state probe uses it: a Praat script must not run while the student
    is typing in Praat.  Returns 0.0 when the answer is not available.
    """

    try:
        import win32api

        raw = win32api.GetLastInputInfo()
        if isinstance(raw, dict):
            last = int(raw.get("Time", 0))
        else:
            last = int(raw)
        now = int(win32api.GetTickCount())
    except Exception:  # pragma: no cover - pywin32 missing
        return 0.0
    if now < last:
        return 0.0
    return (now - last) / 1000.0


def top_window_at(x: int, y: int) -> int:
    """The top-level window that is on screen at a point.

    ``WindowFromPoint`` gives the deepest window there; its root is the
    window the student actually sees.  A modal dialog (Praat's "Formant
    settings", for instance) is such a root, and it sits **on top of**
    the drawing area - which is why the coach has to ask this question
    before it explains a picture.
    """

    if win32gui is None:
        return 0
    try:
        hwnd = win32gui.WindowFromPoint((int(x), int(y)))
        if not hwnd:
            return 0
        root = win32gui.GetAncestor(hwnd, 2)  # GA_ROOT
        return int(root or hwnd)
    except Exception:  # noqa: BLE001
        return 0


def _process_is_praat(hwnd: int) -> bool:
    """Does the window belong to the Praat process?

    The window *class* is not enough: other programs can be called
    "Praat" in their title (a browser tab, for instance), and the class
    of a foreign window can contain the word by accident.  The process
    is the thing that cannot lie.
    """

    if win32gui is None or win32process is None:
        return False
    try:
        import ctypes

        import win32api
        import win32con

        _thread, pid = win32process.GetWindowThreadProcessId(hwnd)
        handle = win32api.OpenProcess(
            win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid
        )
        if not handle:
            return False
        try:
            size = ctypes.c_ulong(260)
            buffer = ctypes.create_unicode_buffer(260)
            ok = ctypes.windll.kernel32.QueryFullProcessImageNameW(
                handle, 0, buffer, ctypes.byref(size)
            )
        finally:
            try:
                win32api.CloseHandle(handle)
            except Exception:  # noqa: BLE001
                pass
        if not ok:
            return False
        return buffer.value.casefold().endswith("\\praat.exe")
    except Exception:  # noqa: BLE001
        return False


def praat_has_focus() -> bool:
    """Does a Praat window own the foreground right now?

    This is the guard around every Praat script the coach sends.  Running
    ``Praat.exe --send`` **activates the Praat window** (measured), so a
    script sent while the student is typing in another program would pull
    Praat over it and swallow the keystrokes.  The script therefore only
    goes out while Praat is already the frontmost window.

    The same guard decides whether the coach explains anything at all: the
    student only wants help while they are working *in Praat*.

    Praat's windows are the Objects window, the editors, the picture and
    the modal dialogs; they all belong to ``Praat.exe`` and their class
    name contains "Praat".  The **title** is not used: another program
    (a browser showing a page about Praat, for instance) may well be
    called "Praat something", and that must not count as "the student is
    working in Praat".
    """

    if win32gui is None:
        return False
    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return False
        if _process_is_praat(hwnd):
            return True
        class_name = (win32gui.GetClassName(hwnd) or "").casefold()
        if "praat" in class_name:
            return True
        # A child window (the picture, a button) may be in front.
        root = win32gui.GetAncestor(hwnd, 2)  # GA_ROOT
        if root and root != hwnd:
            root_class = (win32gui.GetClassName(root) or "").casefold()
            return "praat" in root_class
    except Exception:
        return False
    return False


def _close_stray_dialogs() -> int:
    """Close the modal dialogs a stray click may have opened.

    Clicking a menu item can open a file dialog ("Read from file...").
    Such a dialog is modal: it blocks Praat and it swallows the next
    click, so the coach closes it again instead of leaving the student
    with a frozen Praat.
    """

    if win32gui is None:
        return 0
    closed = 0
    try:
        import win32api
        import win32con
    except Exception:  # pragma: no cover - pywin32 missing
        return 0

    handles: list[int] = []

    def _collect(hwnd: int, _extra: Any) -> None:
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return
            if win32gui.GetClassName(hwnd) == "#32770":
                handles.append(int(hwnd))
        except Exception:
            return

    try:
        win32gui.EnumWindows(_collect, None)
    except Exception:
        return 0

    for hwnd in handles:
        try:
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.1)
            win32api.keybd_event(win32con.VK_ESCAPE, 0, 0, 0)
            win32api.keybd_event(win32con.VK_ESCAPE, 0, win32con.KEYEVENTF_KEYUP, 0)
            closed += 1
            time.sleep(0.15)
        except Exception:
            continue
    return closed


def _dismiss_tooltips() -> int:
    """Close Praat's tooltip ("pip") windows.

    ESC is posted straight to the pip window.  A *real* ESC keystroke would
    land on the Objects window and clear Praat's object selection, so the
    message is posted to the tooltip itself.
    """
    if win32gui is None:
        return 0
    try:
        import win32con
    except Exception:  # pragma: no cover - pywin32 missing
        return 0
    count = 0
    for hwnd in _tooltip_windows():
        try:
            win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0)
            win32gui.PostMessage(hwnd, win32con.WM_KEYUP, win32con.VK_ESCAPE, 0)
            count += 1
        except Exception:
            continue
    if count:
        time.sleep(0.15)
    return count


def _raw_click(x: int, y: int) -> bool:
    """A real left click at screen position ``(x, y)``.

    Used for controls that UIA cannot activate (Praat's menu bar items have no
    HWND, so the Invoke pattern is a no-op for them).

    Praat shows a tooltip ("pip") over the object list after the cursor has
    rested there for a moment, and that little window can still be on top of
    the target when we arrive.  So after moving the cursor we wait for the
    tooltip to get out of the way before pressing the button.
    """
    try:
        import win32api
        import win32con
    except Exception:  # pragma: no cover - pywin32 missing
        return False
    try:
        win32api.SetCursorPos((int(x), int(y)))
        # A "pip" that is already on screen may still be on top of the target
        # (and may even be the foreground window, in which case it swallows
        # the click entirely).  Get rid of it before pressing the button.
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and (_tooltip_covering(x, y)
                                                or _tooltip_windows()):
            _dismiss_tooltips()
            time.sleep(0.05)
        time.sleep(0.08)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.08)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        return True
    except Exception:
        return False


def _tooltip_covering(x: int, y: int) -> bool:
    """Is a tooltip / "pip" window sitting on top of the screen point?"""
    if win32gui is None:
        return False
    hit: list[bool] = []

    def _find(hwnd: int, _extra: object) -> None:
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return
            class_name = (win32gui.GetClassName(hwnd) or "").casefold()
            title = (win32gui.GetWindowText(hwnd) or "").casefold()
            if class_name not in _TOOLTIP_CLASSES and title not in ("pipwindow", "tooltip"):
                return
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        except Exception:
            return
        if left <= x < right and top <= y < bottom:
            hit.append(True)

    try:
        win32gui.EnumWindows(_find, None)
    except Exception:
        return False
    return bool(hit)


# --------------------------------------------------------------------------
# Module level helper
# --------------------------------------------------------------------------


def praat_available() -> bool:
    """True when a visible Praat window exists on this machine.

    Never raises.  Used by the tests to skip live checks.
    """
    if win32gui is None:
        return False
    found = False

    def _cb(hwnd: int, _extra: Any) -> None:
        nonlocal found
        if found:
            return
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return
            cls = win32gui.GetClassName(hwnd) or ""
            title = win32gui.GetWindowText(hwnd) or ""
        except Exception:
            return
        if cls.lower().startswith("praat") or title == "Praat Objects":
            found = True

    try:
        win32gui.EnumWindows(_cb, None)
    except Exception:
        return False
    return found


# --------------------------------------------------------------------------
# The sensor
# --------------------------------------------------------------------------


class PraatUI:
    """Read-only-ish view of the Praat UI through Windows UI Automation.

    Parameters
    ----------
    praat_exe:
        Optional path to ``Praat.exe``.  The sensor never launches Praat and
        never needs the binary; the path is only kept for callers that want
        to know which executable is being inspected.
    """

    #: Windows are re-enumerated at most once per this many seconds.
    WINDOW_CACHE_TTL = 1.0
    #: Default depth used by :meth:`tree` and :meth:`find_all`.
    MAX_DEPTH = 8
    #: How long the named-element index of a window stays valid.
    NAMED_CACHE_TTL = 1.0

    def __init__(self, praat_exe: Path | None = None) -> None:
        self.praat_exe = Path(praat_exe) if praat_exe is not None else None
        self._windows: list[UiaWindow] = []
        self._windows_by_hwnd: dict[int, UiaWindow] = {}
        self._windows_cached_at: float = 0.0
        self._named_cache: dict[int, tuple[float, list[Element]]] = {}
        #: The items of the open popup menu, with the popup windows they
        #: came from: ``(hwnds, items)``.
        self._popup_cache: tuple[tuple[int, ...], list[Element]] | None = None

    # -- windows ---------------------------------------------------------

    def windows(self) -> list[UiaWindow]:
        """All visible Praat top-level windows (cached for ~1 s)."""
        return list(self._refresh_windows())

    def objects_window(self) -> UiaWindow | None:
        """The ``Praat Objects`` shell window, or ``None``."""
        for win in self._refresh_windows():
            if win.kind == "objects":
                return win
        return None

    def picture_window(self) -> UiaWindow | None:
        """The ``Praat Picture`` window, or ``None``."""
        for win in self._refresh_windows():
            if win.kind == "picture":
                return win
        return None

    def editor_windows(self) -> list[UiaWindow]:
        """Editor windows such as ``2. Sound demo_vowel``."""
        return [win for win in self._refresh_windows() if win.kind == "editor"]

    def window_at_point(self, x: int, y: int) -> UiaWindow | None:
        """The Praat window under the screen point ``(x, y)``, or ``None``."""
        wins = self._refresh_windows()
        hwnd = 0
        if auto is not None:
            try:
                hwnd = int(auto.WindowFromPoint(x, y))
            except Exception:
                hwnd = 0
        if hwnd:
            win = self._windows_by_hwnd.get(hwnd)
            if win is not None:
                return win
        for win in wins:
            if _rect_contains(win.rect, x, y):
                return win
        return None

    def available(self) -> bool:
        """True when at least one Praat window is visible."""
        return bool(self._refresh_windows())

    # -- elements --------------------------------------------------------

    def tree(self, window: UiaWindow, max_depth: int = 8) -> list[Element]:
        """Flatten the UIA subtree of ``window`` into a list of elements.

        The window itself is the element at depth 0.  Stale or unreachable
        nodes are skipped instead of raising.
        """
        ctrl = self._control_from_window(window)
        if ctrl is None:
            return []
        out: list[Element] = []
        for node, depth in self._iter_controls(ctrl, max_depth=max_depth):
            out.append(self._element_from(node, depth=depth, window_title=window.title))
        return out

    def element_at_point(
        self, x: int, y: int, *, praat_only: bool = True
    ) -> Element | None:
        """The element under the screen point ``(x, y)``, or ``None``.

        Fast path: a single UIA hit test plus a walk *up* the parent chain
        (to find the owning window and the depth).  Works over menu popups
        as well, because UIA exposes the popup as a child of the window that
        opened it.

        With ``praat_only`` (the default) the answer is ``None`` when the
        cursor is not over a Praat window at all, so the overlay only ever
        talks about Praat.  Two measurements shape the code here:

        * **A UIA hit test activates the window it hits.**  Praat jumps to
          the front, so a hit test while the student is typing in another
          program steals the keyboard from them.  The hit test therefore
          only happens while a Praat window has the focus.
        * Another application may cover Praat.  Then the control under the
          pointer belongs to that application, not to Praat, so the coach
          has to stay quiet (see :meth:`_praat_in_front`).
        """
        if auto is None:
            return None
        if praat_only and not praat_has_focus():
            # Praat is not the application in front: a hit test would
            # pull Praat over whatever the student is doing.
            return None
        try:
            ctrl = auto.ControlFromPoint(x, y)
        except Exception:
            return None
        if ctrl is None:
            return None
        owner, depth = self._resolve_owner(ctrl)
        if owner is None and praat_only:
            # The control is not inside a Praat window.  Another
            # application may be sitting *on top* of Praat, and the
            # geometric fallback below would happily hand us that
            # application's control while pretending it belongs to
            # Praat.  So the fallback is only allowed when Praat really
            # is the frontmost thing at this point.
            if not self._praat_in_front(x, y):
                return None
            # The parent-chain walk occasionally fails (COM race), even
            # though the point is clearly inside a Praat window.  Fall back
            # to the geometric test so the hover does not flicker.
            owner = self._window_containing(x, y)
            if owner is None:
                return None
            depth = 0

        title = owner.title if owner is not None else ""

        # Praat pops up a tooltip ("pip") over the object list while the
        # cursor rests on a row.  That little window sits on top of the
        # control we want, so a raw hit test lands on the tooltip.  Ignore
        # tooltips and resolve the real control geometrically instead.
        if _is_tooltip(ctrl):
            if owner is None:
                return None
            match = self._named_element_at(owner, x, y)
            if match is None:
                return None
            return Element(
                name=match.name,
                control_type=match.control_type,
                automation_id=match.automation_id,
                hwnd=match.hwnd,
                rect=match.rect,
                window_title=title,
                depth=match.depth,
                enabled=match.enabled,
            )

        # UIA often reports the *container* under the cursor rather than the
        # control inside it: Praat draws its buttons inside unnamed
        # ``rowColumn`` panes, the object list is a ListControl whose rows
        # are ListItemControls, and a menu popup is a MenuControl whose
        # entries are MenuItemControls.  Always prefer the *smallest* named
        # descendant under the point - that is the control the user means.
        deeper = self._named_descendant_at(ctrl, x, y)
        if deeper is not None:
            ctrl = deeper
            depth += 1
        elif not _text(ctrl, "Name").strip():
            # A *disabled* button is reported as its unnamed container, and
            # that container's parent does not expose the button as a child -
            # it is a sibling there.
            sibling = self._named_sibling_at(ctrl, x, y)
            if sibling is not None:
                ctrl = sibling
                depth += 1

        if _text(ctrl, "Name").strip():
            return self._element_from(ctrl, depth=depth, window_title=title)

        # Last resort: match the point against the named elements we know
        # about in that window.  A *disabled* Praat button is reported by UIA
        # as its unnamed container, and the container's parent does not always
        # expose the button as a child - but the window tree does.
        if owner is not None:
            match = self._named_element_at(owner, x, y)
            if match is not None:
                return Element(
                    name=match.name,
                    control_type=match.control_type,
                    automation_id=match.automation_id,
                    hwnd=match.hwnd,
                    rect=match.rect,
                    window_title=title,
                    depth=match.depth,
                    enabled=match.enabled,
                )
        return None

    def _named_element_at(self, window: UiaWindow, x: int, y: int) -> Element | None:
        """Smallest named element of ``window`` whose rectangle covers the point.

        Uses a short-lived cache of the window's named elements, because the
        full tree walk costs ~80 ms and the hover loop runs at 45 ms.

        When the cached list holds nothing at the point, the tree is walked
        again: a stale list must never hide a control that is really there.
        """
        now = time.monotonic()
        cached = self._named_cache.get(window.hwnd)
        named: list[Element] | None = None
        if cached is not None and (now - cached[0]) < self.NAMED_CACHE_TTL:
            named = cached[1]
        if named is None:
            named = [e for e in self.tree(window, max_depth=self.MAX_DEPTH) if e.name]
            self._named_cache[window.hwnd] = (now, named)

        best: Element | None = None
        best_area: float | None = None
        for element in named:
            rect = element.rect
            if rect is None or not _rect_contains(rect, x, y):
                continue
            area = float((rect[2] - rect[0]) * (rect[3] - rect[1]))
            if best is None or best_area is None or area < best_area:
                best, best_area = element, area
        if best is None and cached is not None:
            # The cached list is too old to be trusted: walk the tree.
            named = [e for e in self.tree(window, max_depth=self.MAX_DEPTH) if e.name]
            self._named_cache[window.hwnd] = (time.monotonic(), named)
            for element in named:
                rect = element.rect
                if rect is None or not _rect_contains(rect, x, y):
                    continue
                area = float((rect[2] - rect[0]) * (rect[3] - rect[1]))
                if best is None or best_area is None or area < best_area:
                    best, best_area = element, area
        return best

    def _named_sibling_at(self, control: Any, x: int, y: int) -> Any | None:
        """The named sibling of ``control`` that contains the point.

        Used when the hit lands on an unnamed container: the real control
        (the button) is a *sibling* of that container in the accessibility
        tree, not a child.
        """
        try:
            parent = control.GetParentControl()
        except Exception:
            parent = None
        if parent is None:
            return None
        best: Any | None = None
        best_area: float | None = None
        for child in self._children(parent):
            rect = _safe_rect(child)
            if rect is None or not _rect_contains(rect, x, y):
                continue
            if not _text(child, "Name").strip():
                continue
            area = float((rect[2] - rect[0]) * (rect[3] - rect[1]))
            if best is None or best_area is None or area < best_area:
                best, best_area = child, area
        return best

    def _named_descendant_at(self, control: Any, x: int, y: int) -> Any | None:
        """The deepest named descendant of ``control`` that contains the point.

        Praat's buttons live inside unnamed container panes, so a raw hit test
        often lands on the pane.  This walks down (breadth first) and returns
        the first named control whose rectangle covers the point.
        """
        queue: deque[tuple[Any, int]] = deque([(control, 0)])
        seen = 0
        best: Any | None = None
        best_area = None
        while queue and seen < 500:
            node, depth = queue.popleft()
            seen += 1
            if depth > 0:
                rect = _safe_rect(node)
                if rect is not None and _rect_contains(rect, x, y):
                    if _text(node, "Name").strip():
                        area = (rect[2] - rect[0]) * (rect[3] - rect[1])
                        if best is None or area < best_area:
                            best, best_area = node, area
            if depth >= 4:
                continue
            for child in self._children(node):
                queue.append((child, depth + 1))
        return best

    def _window_containing(self, x: int, y: int) -> UiaWindow | None:
        """The Praat window whose rectangle contains the screen point."""
        for win in self._refresh_windows():
            left, top, right, bottom = win.rect
            if left <= x < right and top <= y < bottom:
                return win
        return None

    def _praat_in_front(self, x: int, y: int) -> bool:
        """Is the frontmost window at the screen point one of Praat's?

        The coach may only talk about Praat.  A geometric test ("is the
        point inside a Praat rectangle") is not enough: another
        application can cover that rectangle, and then the control under
        the cursor belongs to *that* application.

        Praat's own popups count as Praat: a menu popup is a standard
        ``#32768`` window and the object-list tooltip ("pip") is a
        ``MouseInc`` window, so both are recognised by their owner.
        """

        if win32gui is None:  # pragma: no cover - pywin32 missing
            return True
        try:
            hwnd = win32gui.WindowFromPoint((x, y))
        except Exception:
            return True
        if not hwnd:
            return True
        try:
            class_name = (win32gui.GetClassName(hwnd) or "").casefold()
        except Exception:
            return True
        if "praat" in class_name:
            return True
        if class_name in (_MENU_WINDOW_CLASS, "mouseinc") or "pip" in class_name:
            try:
                owner = win32gui.GetWindow(hwnd, _GW_OWNER)
                owner_class = (
                    (win32gui.GetClassName(owner) or "").casefold() if owner else ""
                )
            except Exception:
                return False
            return "praat" in owner_class
        return False

    def open_popup_items(
        self, window: UiaWindow | None = None
    ) -> list[Element]:
        """The items of the popup menu that is open right now.

        Returns an empty list when no popup is open.  The items are read
        from the popup's own control tree, never through a hit test: a UIA
        hit test over the *menu bar* of an open menu closes that menu
        (measured), so the coach must not use one while a menu is open.

        The popup is a standard Win32 menu window (class ``#32768``) that
        belongs to a Praat window, so its items are read straight from
        that window.  Walking the whole tree of every Praat window for
        them cost 90-120 ms, which froze the pointer for a tenth of a
        second every time the menu was looked at; reading the popup's
        own tree costs about 13 ms, once per menu, and nothing after
        that (the result is cached until the popup changes).
        """

        popups = self._popup_windows()
        if not popups:
            # No menu is open: there is nothing to read.  (The old code
            # walked the whole tree of every Praat window here, which cost
            # 60-90 ms and found nothing, every single time.)
            self._popup_cache = None
            return []
        cached = self._popup_cache
        if cached is not None and cached[0] == popups:
            return list(cached[1])
        items = self._read_popup_items(popups, window)
        if items:
            self._popup_cache = (popups, items)
            return list(items)
        # The popup is there but its items could not be read: fall back
        # to the (slow) tree walk rather than losing the explanation.

        windows = [window] if window is not None else self._refresh_windows()
        for win in windows:
            if win is None:
                continue
            control = self._control_from_window(win)
            if control is None:
                continue
            for node, _depth in self._iter_controls(control, max_depth=self.MAX_DEPTH):
                if _text(node, "ControlTypeName") != "MenuControl":
                    continue
                items: list[Element] = []
                for child in self._children(node):
                    if _text(child, "ControlTypeName") == _SEPARATOR_CONTROL:
                        continue
                    items.append(
                        self._element_from(child, depth=2, window_title=win.title)
                    )
                if items:
                    return items
        return []

    def _popup_windows(self) -> tuple[int, ...]:
        """The visible Praat menu popups (the ``#32768`` windows they own)."""

        return tuple(
            hwnd for hwnd in _menu_popup_windows() if _praat_owned_popup(hwnd)
        )

    def _read_popup_items(
        self, popups: tuple[int, ...], window: UiaWindow | None
    ) -> list[Element]:
        """Read the items of the popup menus themselves."""

        if auto is None:
            return []
        title = window.title if window is not None else ""
        if not title:
            objects = self.objects_window()
            title = objects.title if objects is not None else ""
        items: list[Element] = []
        for hwnd in popups:
            try:
                control = auto.ControlFromHandle(hwnd)
            except Exception:
                continue
            if control is None:
                continue
            for child in self._children(control):
                if _text(child, "ControlTypeName") == _SEPARATOR_CONTROL:
                    continue
                items.append(self._element_from(child, depth=2, window_title=title))
        return items

    def find(
        self,
        name: str,
        *,
        window: UiaWindow | None = None,
        control_type: str | None = None,
    ) -> Element | None:
        """Find one element by (normalised) name.

        Matching is case insensitive and runs against :func:`normalize_name`.
        An exact match wins; only when there is none a substring match is
        accepted, so ``find('Sound')`` still finds ``Sound help``.
        """
        target = normalize_name(name).casefold()
        if not target:
            return None
        elements = self.find_all(window=window, control_type=control_type)
        for element in elements:
            if element.key.casefold() == target:
                return element
        for element in elements:
            if target in element.key.casefold():
                return element
        return None

    def find_all(
        self,
        window: UiaWindow | None = None,
        control_type: str | None = None,
    ) -> list[Element]:
        """All elements of ``window`` (or of every Praat window)."""
        if window is not None:
            windows = [window]
        else:
            windows = self._refresh_windows()
        out: list[Element] = []
        for win in windows:
            out.extend(self.tree(win, max_depth=self.MAX_DEPTH))
        if control_type:
            out = [e for e in out if e.control_type == control_type]
        return out

    # -- actions ---------------------------------------------------------

    def invoke(self, element: Element) -> bool:
        """Invoke ``element`` (UIA Invoke pattern, fallback to a click).

        The element is looked up again in the live tree, because the
        dataclass only carries plain data.  Returns ``False`` when the
        element cannot be found or neither mechanism works.
        """
        ctrl = self._find_control(element)
        if ctrl is None:
            return False
        try:
            ctrl.GetInvokePattern().Invoke()
            return True
        except Exception:
            pass
        return self._click_control(ctrl)

    def open_menu(
        self,
        window: UiaWindow,
        menu_name: str,
        timeout: float = 2.0,
        keep_open: bool = False,
    ) -> list[Element]:
        """Open a menu bar item, collect the popup items, close the popup.

        ``menu_name`` is matched against the menu bar items of ``window``
        (e.g. ``'Open'``).  The popup items are returned as elements whose
        ``depth`` is 2 (window -> MenuControl -> MenuItemControl); menu
        separators are skipped because they carry no name and cannot be
        activated.

        The popup is always closed again, even when something goes wrong half
        way through.  ``ESC`` is posted straight to the popup window, because
        a real ``ESC`` keystroke would land on the Objects window and clear
        Praat's object selection.

        ``keep_open=True`` leaves the popup open (the caller is then
        responsible for closing it, e.g. via :meth:`close_popup`).  That is
        what the hover coach needs: the user must be able to hover an item
        *while* the menu is still open.
        """
        popup: Any | None = None
        opened = False
        try:
            self._activate(window)
            ctrl = self._control_from_window(window)
            if ctrl is None:
                return []
            target = normalize_name(menu_name).casefold()
            menu_item = None
            for node, _depth in self._iter_controls(ctrl, max_depth=self.MAX_DEPTH):
                if _text(node, "ControlTypeName") != "MenuItemControl":
                    continue
                if normalize_name(_text(node, "Name")).casefold() == target:
                    menu_item = node
                    break
            if menu_item is None:
                return []
            opened = self._click_control(menu_item)
            popup = self._wait_for_popup(window, menu_name, timeout)
            # The first click on an inactive window is swallowed by Windows
            # (click-to-activate), and Praat's own tooltip ("pip") can
            # steal it.  Both are cured by clicking again.
            for _attempt in range(3):
                if popup is not None:
                    break
                # A click that landed on a menu *item* opens a modal
                # dialog (a file dialog, for instance).  Close it again,
                # or it swallows everything that comes next.
                _close_stray_dialogs()
                opened = self._click_control(menu_item, move_mouse=True) or opened
                popup = self._wait_for_popup(window, menu_name, timeout)
            if popup is None:
                _close_stray_dialogs()
                return []
            items: list[Element] = []
            for child in self._children(popup):
                if _text(child, "ControlTypeName") == _SEPARATOR_CONTROL:
                    continue
                items.append(
                    self._element_from(child, depth=2, window_title=window.title)
                )
            return items
        finally:
            if opened and not keep_open:
                self._close_popup(window, popup)

    def close_popup(self, window: UiaWindow | None = None,
                    popup: Any | None = None) -> None:
        """Close an open popup menu without disturbing Praat's selection."""
        self._close_popup(window, popup)

    def _activate(self, window: UiaWindow) -> bool:
        """Bring a window to the front before clicking inside it.

        Windows' *click-to-activate* means the first click on an inactive
        window only activates that window and is swallowed.  A menu bar
        therefore has to be active before the click, otherwise nothing
        happens at all - which is exactly what a user would experience.

        ``SetForegroundWindow`` alone is refused when the foreground
        belongs to another process and the user did not just click
        somewhere (the foreground lock).  Attaching to the foreground
        thread first lifts that restriction, which is the standard way
        for a background tool to take the focus.
        """

        hwnd = getattr(window, "hwnd", 0)
        if not hwnd or win32gui is None:
            return False
        if win32api is None or win32process is None:  # pragma: no cover
            return False
        # Windows refuses the request now and then (the foreground lock
        # counts on the *user* having clicked), so it is worth a few
        # attempts: the whole click path depends on it.
        for attempt in range(3):
            try:
                if win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, 9)  # SW_RESTORE
                foreground = win32gui.GetForegroundWindow()
                attached = False
                foreground_thread = 0
                if foreground and foreground != hwnd:
                    current_thread = win32api.GetCurrentThreadId()
                    foreground_thread = win32process.GetWindowThreadProcessId(foreground)[0]
                    try:
                        attached = bool(
                            win32process.AttachThreadInput(
                                current_thread, foreground_thread, True
                            )
                        )
                    except Exception:
                        attached = False
                try:
                    win32gui.SetForegroundWindow(hwnd)
                    win32gui.BringWindowToTop(hwnd)
                finally:
                    if attached:
                        try:
                            win32process.AttachThreadInput(
                                win32api.GetCurrentThreadId(), foreground_thread, False
                            )
                        except Exception:
                            pass
                time.sleep(0.2)
                if win32gui.GetForegroundWindow() == hwnd:
                    return True
            except Exception:
                pass
            time.sleep(0.15)
        return False

    # -- internals -------------------------------------------------------

    def _refresh_windows(self, force: bool = False) -> list[UiaWindow]:
        """Enumerate Praat windows, reusing the cache for ~1 second."""
        now = time.monotonic()
        if (
            not force
            and self._windows
            and (now - self._windows_cached_at) < self.WINDOW_CACHE_TTL
        ):
            return self._windows
        wins = self._enum_windows()
        self._windows = wins
        self._windows_by_hwnd = {w.hwnd: w for w in wins}
        self._windows_cached_at = now
        return wins

    def _enum_windows(self) -> list[UiaWindow]:
        if win32gui is None:
            return []
        found: list[UiaWindow] = []

        def _cb(hwnd: int, _extra: Any) -> None:
            try:
                if not win32gui.IsWindowVisible(hwnd):
                    return
                cls = win32gui.GetClassName(hwnd) or ""
                title = win32gui.GetWindowText(hwnd) or ""
            except Exception:
                return
            if not cls.lower().startswith("praat") and title != "Praat Objects":
                return
            try:
                rect = tuple(int(v) for v in win32gui.GetWindowRect(hwnd))
            except Exception:
                rect = (0, 0, 0, 0)
            found.append(
                UiaWindow(
                    hwnd=int(hwnd),
                    title=title,
                    class_name=cls,
                    rect=rect,  # type: ignore[arg-type]
                    kind=classify_window(title, cls),
                )
            )

        try:
            win32gui.EnumWindows(_cb, None)
        except Exception:
            return []
        return found

    def _control_from_window(self, window: UiaWindow) -> Any | None:
        """Resolve a :class:`UiaWindow` back into a uiautomation control."""
        if auto is None or window is None:
            return None
        try:
            ctrl = auto.ControlFromHandle(int(window.hwnd))
        except Exception:
            return None
        if ctrl is None:
            return None
        return ctrl

    def _children(self, control: Any) -> list[Any]:
        try:
            children = control.GetChildren()
        except Exception:
            return []
        return list(children or [])

    def _iter_controls(
        self, control: Any, max_depth: int = 8
    ) -> Iterator[tuple[Any, int]]:
        """Breadth-first walk over a control subtree.

        ``uiautomation.WalkTree`` proved unreliable on this machine, so the
        walk uses explicit ``GetChildren()`` recursion.
        """
        queue: deque[tuple[Any, int]] = deque([(control, 0)])
        seen = 0
        while queue and seen < 5000:
            node, depth = queue.popleft()
            seen += 1
            yield node, depth
            if depth >= max_depth:
                continue
            for child in self._children(node):
                queue.append((child, depth + 1))

    def _element_from(
        self, control: Any, depth: int = 0, window_title: str = ""
    ) -> Element:
        try:
            enabled = bool(control.IsEnabled)
        except Exception:
            enabled = True
        return Element(
            name=_text(control, "Name"),
            control_type=_text(control, "ControlTypeName"),
            automation_id=_text(control, "AutomationId"),
            hwnd=_number(control, "NativeWindowHandle"),
            rect=_safe_rect(control),
            window_title=window_title,
            depth=depth,
            enabled=enabled,
        )

    def _resolve_owner(self, control: Any) -> tuple[UiaWindow | None, int]:
        """Walk up the parent chain to find the owning Praat window.

        Returns ``(window, depth)`` where ``depth`` is the distance of
        ``control`` below that window (0 == the window itself).
        """
        self._refresh_windows()
        by_hwnd = self._windows_by_hwnd
        current = control
        depth = 0
        for _ in range(64):
            hwnd = _number(current, "NativeWindowHandle")
            if hwnd and hwnd in by_hwnd:
                return by_hwnd[hwnd], depth
            parent = None
            try:
                parent = current.GetParentControl()
            except Exception:
                parent = None
            if parent is None:
                break
            current = parent
            depth += 1
        return None, depth

    def _find_control(self, element: Element) -> Any | None:
        """Locate the live control that matches ``element``."""
        target = element.key.casefold()
        same_window = None
        any_window = None
        for win in self._refresh_windows():
            ctrl = self._control_from_window(win)
            if ctrl is None:
                continue
            for node, _depth in self._iter_controls(ctrl, max_depth=self.MAX_DEPTH):
                if element.control_type and _text(node, "ControlTypeName") != element.control_type:
                    continue
                if element.hwnd and _number(node, "NativeWindowHandle") == element.hwnd:
                    return node
                if normalize_name(_text(node, "Name")).casefold() != target:
                    continue
                if win.title == element.window_title and same_window is None:
                    same_window = node
                elif any_window is None:
                    any_window = node
        return same_window if same_window is not None else any_window

    def _click_control(self, control: Any, move_mouse: bool = True) -> bool:
        """Activate a control.

        Two different mechanisms are needed, and picking the wrong one fails
        *silently*:

        * A control with a real HWND (Praat's buttons) is activated with the
          UIA Invoke pattern.  That does not move the mouse.
        * A control **without** an HWND (Praat's menu bar items, whose
          ``NativeWindowHandle`` is 0) cannot be invoked: ``Invoke()`` returns
          without doing anything and without raising.  For those, a real
          Win32 mouse click is the only reliable way - and it needs the
          cursor to be on the control, so the cursor is moved there.

        ``move_mouse=False`` avoids touching the cursor, so only the Invoke
        path is available then.
        """
        rect = _safe_rect(control)
        if rect is None:
            return False
        hwnd = _number(control, "NativeWindowHandle")

        if hwnd:
            # A real window: UIA can invoke it without touching the mouse.
            try:
                control.GetInvokePattern().Invoke()
                return True
            except Exception:
                pass
        if not move_mouse:
            try:
                control.Click(simulateMove=False)
                return True
            except Exception:
                return False
        x = (rect[0] + rect[2]) // 2
        y = (rect[1] + rect[3]) // 2
        if _raw_click(x, y):
            return True
        try:
            control.GetInvokePattern().Invoke()
            return True
        except Exception:
            return False

    def _find_popup_menu(self, control: Any, menu_name: str) -> Any | None:
        """Find the ``MenuControl`` of an open popup inside a control tree."""
        target = normalize_name(menu_name).casefold()
        fallback = None
        for node, _depth in self._iter_controls(control, max_depth=self.MAX_DEPTH):
            if _text(node, "ControlTypeName") != "MenuControl":
                continue
            if normalize_name(_text(node, "Name")).casefold() == target:
                return node
            if fallback is None:
                fallback = node
        return fallback

    def _wait_for_popup(self, window: UiaWindow, menu_name: str, timeout: float) -> Any | None:
        """Wait until the popup menu shows up, return its ``MenuControl``."""
        deadline = time.monotonic() + max(0.0, timeout)
        while True:
            ctrl = self._control_from_window(window)
            if ctrl is not None:
                popup = self._find_popup_menu(ctrl, menu_name)
                if popup is not None:
                    return popup
            if time.monotonic() >= deadline:
                break
            time.sleep(0.08)
        # Fallback: the popup may live in a separate top-level window.
        return self._popup_from_top_level(menu_name)

    def _popup_from_top_level(self, menu_name: str) -> Any | None:
        """Look for a popup menu in a separate top-level window."""
        if auto is None or win32gui is None:
            return None
        candidates: list[int] = []

        def _cb(hwnd: int, _extra: Any) -> None:
            try:
                if not win32gui.IsWindowVisible(hwnd):
                    return
                cls = win32gui.GetClassName(hwnd) or ""
            except Exception:
                return
            if cls == _MENU_WINDOW_CLASS:  # standard Win32 menu window
                candidates.append(int(hwnd))

        try:
            win32gui.EnumWindows(_cb, None)
        except Exception:
            return None
        for hwnd in candidates:
            try:
                ctrl = auto.ControlFromHandle(hwnd)
            except Exception:
                continue
            if ctrl is None:
                continue
            popup = self._find_popup_menu(ctrl, menu_name)
            if popup is not None:
                return popup
        return None

    def _popup_hwnd(self, window: UiaWindow, popup: Any | None = None) -> int:
        """Native handle of the open popup menu window (0 when unknown)."""
        if popup is not None:
            hwnd = _number(popup, "NativeWindowHandle")
            if hwnd:
                return hwnd
        ctrl = self._control_from_window(window)
        if ctrl is None:
            return 0
        for node, _depth in self._iter_controls(ctrl, max_depth=self.MAX_DEPTH):
            if _text(node, "ControlTypeName") == "MenuControl":
                hwnd = _number(node, "NativeWindowHandle")
                if hwnd:
                    return hwnd
        return 0

    def _close_popup(self, window: UiaWindow, popup: Any | None = None) -> None:
        """Close an open popup menu.

        ``ESC`` is posted to the popup window itself.  A synthetic ESC
        keystroke would be delivered to the Objects window instead, and in
        Praat that clears the object selection - exactly what we must not
        do.  ``WM_CANCELMODE`` on the owner window is the fallback; no raw
        keystroke is ever sent.
        """
        if win32gui is None:
            return
        hwnd = self._popup_hwnd(window, popup)
        if hwnd:
            try:
                win32gui.PostMessage(hwnd, _WM_KEYDOWN, _VK_ESCAPE, 0)
                win32gui.PostMessage(hwnd, _WM_KEYUP, _VK_ESCAPE, 0)
            except Exception:
                pass
            if self._wait_popup_gone(hwnd, 0.6):
                return
        try:
            win32gui.PostMessage(int(window.hwnd), _WM_CANCELMODE, 0, 0)
        except Exception:
            pass

    @staticmethod
    def _wait_popup_gone(hwnd: int, timeout: float) -> bool:
        """Wait until the popup window is destroyed."""
        if win32gui is None or not hwnd:
            return True
        deadline = time.monotonic() + max(0.0, timeout)
        while True:
            try:
                if not win32gui.IsWindow(hwnd):
                    return True
            except Exception:
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.05)
