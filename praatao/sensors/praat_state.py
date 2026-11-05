"""Semantic state sensor for Praat.

This module answers the question *"what does Praat contain right now?"* for
the Praatao overlay: which objects are in the Objects window, which of them
are selected, whether an editor is open, and which tiers a TextGrid has.

How the state is obtained
-------------------------

Two independent sources are combined, because Praat offers no single
read-only API for "the whole picture":

1. **A Praat script** (``praatao/probes/snapshot.praat``) is handed to the
   running GUI with ``Praat.exe --send <script>``.  The script writes a small
   tab-separated dump to a temporary file which is then parsed here.  It
   reports the Praat version, the current selection (ids + full names), the
   attributes of a single selected Sound and the tier names of the selected
   TextGrid.  The script never changes the selection.
2. **The Objects window** is read through UI Automation, because Praat's
   scripting language cannot enumerate the *whole* object list (there is no
   ``numberOfObjects()`` and ``object[i]`` exposes numbers only).  The list
   items of the Objects window look like ``1. Sound demo_vowel``.  The UIA
   sensor (:mod:`praatao.sensors.uia`) is used first, with a direct read of
   the Objects list box as a fallback.

Window titles alone give the fast path (:meth:`PraatStateProbe.quick`), which
runs in well under a millisecond and is used for hover responsiveness.

Probe file format
-----------------

One record per line, fields separated by a TAB, lines terminated by CRLF::

    V<TAB>6.4.12                     Praat version
    N<TAB>1                          number of selected objects
    S<TAB>2<TAB>Sound demo_vowel     one record per selected object:
                                     object id + full name ("<Type> <name>")
    A<TAB>0.8<TAB>16000<TAB>1<TAB>0<TAB>0.8
                                     attributes of a single selected Sound:
                                     duration, sampling frequency, channels,
                                     start time, end time
    T<TAB>2                          number of tiers of the selected TextGrid
    I<TAB>1<TAB>marks                one record per tier: index + tier name
    E                                end-of-probe marker

Inside a name, a backslash is doubled and a TAB or newline is written as
``\\t`` / ``\\n``; the parser undoes that.

Hazard notes (learned the hard way on Praat 6.4.12 / Windows)
--------------------------------------------------------------

* A Praat script that fails pops up a **modal message box** in the running
  Praat, and ``--send`` then blocks forever.  Every call is therefore
  wrapped in a timeout and every public method swallows exceptions.
* Praat writes text files as ANSI when the content is ASCII, but switches to
  UTF-16 (with a byte-order mark) as soon as a non-ASCII character is
  written, so the parser has to detect the encoding.
* ``Praat.exe --send`` starts a *new* Praat instance when none is running.
  :meth:`PraatStateProbe.send` refuses to do that and returns ``False``.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from ..paths import PRAAT_EXE, STATE_DIR, ensure_state_dir
from .uia import praat_has_focus

#: ``CREATE_NO_WINDOW``: a console Praat must not flash a window.
_NO_WINDOW = 0x08000000

__all__ = [
    "PraatObject",
    "PraatState",
    "PraatStateProbe",
    "decode_probe_bytes",
    "parse_editor_title",
    "parse_object_list_item",
    "parse_probe_output",
    "praat_available",
    "split_full_name",
    "state_from_windows",
]


#: Directory with the packaged ``.praat`` probe scripts.
PROBE_DIR = Path(__file__).resolve().parent.parent / "probes"

#: The packaged probe template.  ``@OUT@`` is replaced with the path of the
#: file the probe should write.
SNAPSHOT_PROBE = PROBE_DIR / "snapshot.praat"

#: Praat's own window classes (Windows GUI).
PRAAT_SHELL_CLASS = "PraatShell1 Praat"
PRAAT_CHILD_CLASS = "PraatChildWindow1 Praat"

#: Title of an editor window: ``2. Sound demo_vowel``.
_EDITOR_TITLE_RE = re.compile(r"^\s*(\d+)\.\s*(.+?)\s*$")

#: Cache for :func:`praat_version` (reading it costs a process start).
_VERSION_CACHE: str | None = None

#: How long the resolved Objects-window list box is reused.
#:
#: Finding the list box costs two UIA searches (about 18 ms); reading it
#: costs about 2 ms.  The probe runs every 0.9 s, so the search is done
#: once in a while and the read is done every time.
_LISTING_TTL = 5.0

#: The resolved list box: ``{"listing": <control>, "at": <monotonic>}``.
_listing_cache: dict[str, Any] = {"listing": None, "at": 0.0}


# --------------------------------------------------------------------------
# data model
# --------------------------------------------------------------------------


@dataclass
class PraatObject:
    """One object in Praat's Objects window."""

    id: int
    type: str  # 'Sound', 'TextGrid', 'Pitch', ...
    name: str


@dataclass
class PraatState:
    """A snapshot of what Praat currently holds."""

    running: bool
    version: str | None
    objects: list[PraatObject]
    selected: list[PraatObject]
    editor_open: bool
    editor_object: str | None
    textgrid_tiers: list[str]
    error: str | None = None
    raw: dict = field(default_factory=dict)

    @property
    def selected_types(self) -> list[str]:
        """The types of the selected objects, in selection order."""
        return [obj.type for obj in self.selected]

    def selected_of(self, type_name: str) -> list[PraatObject]:
        """The selected objects whose type is *type_name* (case-insensitive)."""
        wanted = type_name.lower()
        return [obj for obj in self.selected if obj.type.lower() == wanted]


# --------------------------------------------------------------------------
# pure helpers (unit-testable, no Praat involved)
# --------------------------------------------------------------------------


def split_full_name(full_name: str) -> tuple[str, str]:
    """Split a Praat full name ``"Sound demo_vowel"`` into type and name.

    Praat object types are always a single word, so the first space is the
    separator.  ``("Sound", "")`` is returned for a nameless object.
    """
    type_, _, name = full_name.partition(" ")
    return type_.strip(), name.strip()


def parse_editor_title(title: str) -> str | None:
    """Return the object label of an editor window title.

    ``"2. Sound demo_vowel"`` -> ``"Sound demo_vowel"``.
    Returns ``None`` when *title* is not an editor title.
    """
    match = _EDITOR_TITLE_RE.match(title or "")
    if not match:
        return None
    return match.group(2).strip() or None


def _unescape(text: str) -> str:
    """Undo the escaping applied by the Praat probe."""
    out: list[str] = []
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char == "\\" and index + 1 < length:
            nxt = text[index + 1]
            if nxt == "t":
                out.append("\t")
                index += 2
                continue
            if nxt == "n":
                out.append("\n")
                index += 2
                continue
            if nxt == "\\":
                out.append("\\")
                index += 2
                continue
        out.append(char)
        index += 1
    return "".join(out)


def parse_probe_output(text: str) -> dict[str, Any]:
    """Parse the tab-separated output of the Praat probe.

    Returns a dict with the keys ``version`` (str | None), ``selected``
    (list of :class:`PraatObject`), ``tiers`` (list of str), ``tier_count``
    (int), ``attributes`` (dict, empty when the selection has no readable
    attributes) and ``complete`` (bool, True when the end marker was seen).
    Malformed lines are ignored instead of raising.
    """
    result: dict[str, Any] = {
        "version": None,
        "selected": [],
        "tiers": [],
        "tier_count": 0,
        "attributes": {},
        "complete": False,
    }
    for raw_line in (text or "").splitlines():
        line = raw_line.strip("\r\n")
        if not line:
            continue
        fields = line.split("\t")
        tag = fields[0]
        if tag == "V" and len(fields) >= 2:
            result["version"] = fields[1].strip() or None
        elif tag == "N" and len(fields) >= 2:
            try:
                result["selected_count"] = int(fields[1].strip())
            except ValueError:
                pass
        elif tag == "S" and len(fields) >= 3:
            try:
                obj_id = int(fields[1].strip())
            except ValueError:
                obj_id = 0
            type_, name = split_full_name(_unescape(fields[2]))
            if not type_:
                # A malformed record: Praat objects always have a type.
                continue
            result["selected"].append(PraatObject(id=obj_id, type=type_, name=name))
        elif tag == "A" and len(fields) >= 6:
            names = ("duration", "sampling_frequency", "channels", "start_time", "end_time")
            values: dict[str, float | int] = {}
            for key, raw_value in zip(names, fields[1:6]):
                try:
                    values[key] = float(raw_value)
                except ValueError:
                    continue
            if "channels" in values:
                values["channels"] = int(values["channels"])
            result["attributes"] = values
        elif tag == "T" and len(fields) >= 2:
            try:
                result["tier_count"] = int(fields[1].strip())
            except ValueError:
                pass
        elif tag == "I" and len(fields) >= 3:
            result["tiers"].append(_unescape(fields[2]))
        elif tag == "E":
            result["complete"] = True
    return result


def decode_probe_bytes(data: bytes) -> str:
    """Decode a probe output file.

    Praat writes ANSI text for ASCII content but switches to UTF-16 (with a
    byte-order mark) when the text contains non-ASCII characters.  Praat
    6.4.12 on Windows writes the BOM as ``FE FF`` while the payload itself
    is little-endian, so the endianness is detected from the payload.
    """
    if not data:
        return ""
    if data.startswith(b"\xff\xfe"):
        return data[2:].decode("utf-16-le", errors="replace")
    if data.startswith(b"\xfe\xff"):
        body = data[2:]
        little = body.decode("utf-16-le", errors="replace")
        big = body.decode("utf-16-be", errors="replace")
        return little if _looks_like_text(little) else big
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8", errors="replace")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def _looks_like_text(text: str) -> bool:
    """True when *text* looks like plain (ASCII-ish) text, not mojibake."""
    if not text:
        return True
    weird = sum(1 for ch in text if ord(ch) > 126 or (ord(ch) < 32 and ch not in "\t\r\n"))
    return weird * 20 <= len(text)


def parse_object_list_item(item: str) -> PraatObject | None:
    """Parse one Objects-window list item (``"2. Sound demo_vowel"``)."""
    if not item:
        return None
    match = _EDITOR_TITLE_RE.match(item)
    if not match:
        return None
    try:
        obj_id = int(match.group(1))
    except ValueError:
        obj_id = 0
    type_, name = split_full_name(match.group(2))
    if not type_:
        return None
    return PraatObject(id=obj_id, type=type_, name=name)


def state_from_windows(windows: Sequence[tuple[int, str, str]]) -> PraatState:
    """Build a :class:`PraatState` from a list of ``(hwnd, class, title)``.

    This is the pure part of :meth:`PraatStateProbe.quick`.
    """
    editor_labels: list[str] = []
    running = False
    for _hwnd, class_name, title in windows:
        if class_name == PRAAT_SHELL_CLASS and title == "Praat Objects":
            running = True
        elif title == "Praat Picture":
            running = True
        label = parse_editor_title(title)
        if label and class_name == PRAAT_CHILD_CLASS:
            editor_labels.append(label)
            running = True
    return PraatState(
        running=running,
        version=None,
        objects=[],
        selected=[],
        editor_open=bool(editor_labels),
        editor_object=editor_labels[0] if editor_labels else None,
        textgrid_tiers=[],
        raw={"editor_labels": editor_labels},
    )


# --------------------------------------------------------------------------
# window helpers
# --------------------------------------------------------------------------


def _enum_praat_windows() -> list[tuple[int, str, str]]:
    """Return ``(hwnd, class, title)`` for every visible Praat window."""
    try:
        import win32gui
    except Exception:  # pragma: no cover - pywin32 missing
        return []

    found: list[tuple[int, str, str]] = []

    def callback(hwnd: int, _lparam: Any) -> None:
        try:
            title = win32gui.GetWindowText(hwnd)
        except Exception:
            return
        if not title:
            return
        # Cheap pre-filter: only Praat-ish titles get a class lookup.
        if "Praat" not in title and not _EDITOR_TITLE_RE.match(title):
            return
        try:
            class_name = win32gui.GetClassName(hwnd)
        except Exception:
            return
        if "Praat" not in class_name:
            return
        found.append((hwnd, class_name, title))

    try:
        win32gui.EnumWindows(callback, None)
    except Exception:  # pragma: no cover - defensive
        return found
    return found


def praat_available() -> bool:
    """True when a Praat GUI instance is running.

    Used by the test suite to skip live tests when Praat is not up.
    """
    try:
        windows = _enum_praat_windows()
    except Exception:
        return False
    return any(
        class_name == PRAAT_SHELL_CLASS and title == "Praat Objects"
        for _hwnd, class_name, title in windows
    )


def _object_list_via_uia_sensor() -> list[str]:
    """Read the Objects-window list items through the UIA sensor.

    ``praatao.sensors.uia`` is the owner of the UI Automation layer; it is
    used first.  Returns the raw item names (``"1. Sound demo_vowel"``).
    """
    try:
        from .uia import PraatUI
    except Exception:
        return []
    try:
        ui = PraatUI()
        window = ui.objects_window()
        if window is None:
            return []
        names: list[str] = []
        for element in ui.find_all(window, control_type="ListItemControl"):
            names.append(element.name)
            if element.key and element.key not in names:
                names.append(element.key)
        return names
    except Exception:
        return []


def _read_objects_window_items() -> list[str]:
    """Read the Objects-window list items directly.

    Fallback for :func:`_object_list_via_uia_sensor`: it touches only the
    list box of the Objects window, which is a good deal faster than a full
    tree walk.  Returns an empty list when the window is not available.
    """
    try:
        import uiautomation as auto
    except Exception:
        return []
    try:
        window = auto.WindowControl(
            searchDepth=1, ClassName=PRAAT_SHELL_CLASS, Name="Praat Objects"
        )
        if not window.Exists(0.2):
            return []
        listing = window.ListControl(searchDepth=4, ClassName="ListBox")
        if not listing.Exists(0.2):
            return []
        return [child.Name for child in listing.GetChildren()]
    except Exception:
        return []


# --------------------------------------------------------------------------
# the probe
# --------------------------------------------------------------------------


def _objects_listing() -> Any | None:
    """The list box of the Objects window, resolved once and reused.

    Finding the list box costs a search of the accessibility tree, and
    the search used to start at the desktop - where this machine has
    about 800 windows - so it took 20 ms at best and 450 ms at worst.
    The window handle is found with one Win32 call instead, and the
    list box is then one of the window's own children.

    The result is kept for :data:`_LISTING_TTL` seconds: reading the
    items out of the list box costs about 2 ms, and the state probe runs
    every 0.9 s.
    """

    now = time.monotonic()
    cached = _listing_cache.get("listing")
    if cached is not None and (now - _listing_cache.get("at", 0.0)) < _LISTING_TTL:
        return cached

    try:
        import uiautomation as auto
    except Exception:  # pragma: no cover - uiautomation missing
        return None

    listing = _listing_from_handle(auto)
    if listing is None:
        # The fallback: search the accessibility tree for the window.
        try:
            window = auto.WindowControl(
                searchDepth=1, ClassName=PRAAT_SHELL_CLASS, Name="Praat Objects"
            )
            if not window.Exists(0.2):
                return None
            listing = window.ListControl(searchDepth=4, ClassName="ListBox")
            if not listing.Exists(0.2):
                return None
        except Exception:
            return None
    _listing_cache["listing"] = listing
    _listing_cache["at"] = now
    return listing


def _listing_from_handle(auto: Any) -> Any | None:
    """The Objects window's list box, found through its window handle.

    The list box is a Win32 child window of the Objects window.  It sits
    inside the "form" pane, so it is *not* a direct child of the window
    in the accessibility tree - looking for it there finds nothing and
    sends the probe into the slow search of the whole tree.
    """

    try:
        import win32gui

        hwnd = int(win32gui.FindWindow(PRAAT_SHELL_CLASS, "Praat Objects") or 0)
    except Exception:  # pragma: no cover - pywin32 missing
        return None
    if not hwnd:
        return None

    listbox = 0

    def _find(child: int, _extra: Any) -> None:
        nonlocal listbox
        try:
            if (win32gui.GetClassName(child) or "") == "ListBox":
                listbox = child
        except Exception:
            pass

    try:
        win32gui.EnumChildWindows(hwnd, _find, None)
    except Exception:
        return None
    if not listbox:
        return None
    try:
        control = auto.ControlFromHandle(listbox)
    except Exception:
        return None
    if control is None:
        return None
    return control


def _forget_objects_listing() -> None:
    """Drop the cached list box (it has to be looked up again)."""

    _listing_cache["listing"] = None
    _listing_cache["at"] = 0.0


def _objects_and_selection_via_uia() -> tuple[list[PraatObject], list[PraatObject]]:
    """Read the Objects window: every item, and the ones that are selected.

    The list box of the Objects window is read through UI Automation.  The
    selected rows come from the list's ``SelectionPattern``, which the
    Motif list box does implement.

    This reader does **not** run a Praat script, and that is the point: a
    script closes whatever menu the user has open (see
    :meth:`PraatStateProbe.snapshot`), so the coach's hot path must not
    use one.
    """

    listing = _objects_listing()
    if listing is None:
        return [], []

    items: list[str] = []
    selected: list[str] = []
    try:
        items = [child.Name for child in listing.GetChildren()]
    except Exception:
        # The window may have been closed; look it up again next time.
        _forget_objects_listing()
        return [], []
    try:
        pattern = listing.GetSelectionPattern()
        picked = pattern.GetSelection()
        selected = [item.Name for item in picked or []]
    except Exception:
        selected = []

    objects: list[PraatObject] = []
    for item in items:
        parsed = parse_object_list_item(item)
        if parsed is not None:
            objects.append(parsed)
    chosen: list[PraatObject] = []
    for item in selected:
        parsed = parse_object_list_item(item)
        if parsed is not None:
            chosen.append(parsed)
    if chosen:
        return objects, chosen
    return objects, []


def praat_version() -> str | None:
    """The version of the installed Praat, without disturbing anything.

    The version is read from the executable's version resource, so no
    process is started at all.  (Running ``Praat.exe --version`` works
    too, but it starts a console Praat, and the output is UTF-16.)
    """

    global _VERSION_CACHE
    if _VERSION_CACHE is not None:
        return _VERSION_CACHE
    try:
        if not PRAAT_EXE.exists():
            return None
    except Exception:
        return None

    # 1. the version resource of the executable (no process, no window)
    try:
        import win32api  # type: ignore

        info = win32api.GetFileVersionInfo(str(PRAAT_EXE), "\\")
        ms = info["FileVersionMS"]
        ls = info["FileVersionLS"]
        version = "%d.%d.%d.%d" % (
            (ms >> 16) & 0xFFFF,
            ms & 0xFFFF,
            (ls >> 16) & 0xFFFF,
            ls & 0xFFFF,
        )
        _VERSION_CACHE = version
        return version
    except Exception:
        pass

    # 2. a console Praat, hidden and without a window of its own
    try:
        result = subprocess.run(
            [str(PRAAT_EXE), "--version"],
            timeout=6.0,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            creationflags=_NO_WINDOW,
        )
    except Exception:
        return None
    text = (result.stdout or b"").decode("utf-16-le", errors="replace").strip()
    if "\x00" in text:  # not UTF-16 after all
        text = (result.stdout or b"").decode("utf-8", errors="replace").strip()
    match = re.search(r"\d+\.\d+(?:\.\d+)?", text)
    _VERSION_CACHE = match.group(0) if match else (text or None)
    return _VERSION_CACHE


class PraatStateProbe:
    """Reads the semantic state of a running Praat.

    All public methods are defensive: they never raise, and they never
    leave a modal dialog behind in Praat.
    """

    def __init__(
        self,
        praat_exe: Path | None = None,
        state_dir: Path | None = None,
    ) -> None:
        self.praat_exe = Path(praat_exe) if praat_exe else Path(PRAAT_EXE)
        self.state_dir = Path(state_dir) if state_dir else Path(STATE_DIR)
        self._counter = 0

    # -- low level ---------------------------------------------------------

    def _temp_dir(self) -> Path:
        """Directory for temporary probe files (state dir, else temp dir)."""
        try:
            ensure_state_dir()
        except Exception:
            pass
        try:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            return self.state_dir
        except Exception:
            return Path(tempfile.gettempdir())

    def _next_paths(self, prefix: str) -> tuple[Path, Path]:
        """Return unique ``(script_path, output_path)`` for one probe run."""
        self._counter += 1
        stamp = f"{os.getpid()}_{self._counter}"
        folder = self._temp_dir()
        script_path = folder / f"praatao_{prefix}_{stamp}.praat"
        output_path = folder / f"praatao_{prefix}_{stamp}.txt"
        return script_path, output_path

    def send(self, script: str | Path, timeout: float = 10.0) -> bool:
        """Run a Praat script in the running GUI instance.

        *script* is either the path of a ``.praat`` file or the script text
        (which is then written to a temporary file that is removed again
        afterwards).  Returns ``True`` when the script was handed to Praat
        without timing out.  Never raises.
        """
        temporary = False
        try:
            path, temporary = self._materialise(script)
        except Exception:
            return False
        try:
            if path is None or not path.exists():
                return False
            if not self.praat_exe.exists():
                return False
            if not praat_available():
                # --send would start a brand new Praat instance; do not.
                return False
            subprocess.run(
                [str(self.praat_exe), "--send", str(path)],
                timeout=max(0.1, float(timeout)),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            return True
        except subprocess.TimeoutExpired:
            # A script error leaves a modal message box in Praat, which
            # blocks every later --send call.  Clear it right away.
            try:
                self.dismiss_dialogs()
            except Exception:
                pass
            return False
        except Exception:
            return False
        finally:
            if temporary and path is not None:
                try:
                    path.unlink()
                except OSError:
                    pass

    def dismiss_dialogs(self) -> int:
        """Close modal message boxes that Praat may have opened.

        A Praat script that fails pops up a modal box (title ``Message`` or
        ``Error``) in the running Praat.  While that box is up, every
        ``--send`` call blocks, so the probe clears such boxes after a
        timeout.  Returns the number of dialogs that were closed.
        """
        try:
            import win32con
            import win32gui
        except Exception:  # pragma: no cover - pywin32 missing
            return 0

        targets: list[int] = []

        def callback(hwnd: int, _lparam: Any) -> None:
            try:
                if not win32gui.IsWindowVisible(hwnd):
                    return
                title = win32gui.GetWindowText(hwnd)
                if not title:
                    return
                if title.strip().lower() not in (
                    "message",
                    "error",
                    "script error",
                    "praat error",
                ):
                    return
                class_name = win32gui.GetClassName(hwnd)
                if class_name == "#32770" or class_name.startswith("Praat"):
                    targets.append(hwnd)
            except Exception:
                return

        try:
            win32gui.EnumWindows(callback, None)
        except Exception:  # pragma: no cover - defensive
            return 0

        closed = 0
        for hwnd in targets:
            try:
                buttons: list[int] = []

                def child(kid: int, _lparam: Any) -> None:
                    try:
                        if win32gui.GetClassName(kid) != "Button":
                            return
                        label = win32gui.GetWindowText(kid).replace("&", "").strip().lower()
                        if label in ("ok", "yes", "确定"):
                            buttons.append(kid)
                    except Exception:
                        return

                win32gui.EnumChildWindows(hwnd, child, None)
                if buttons:
                    win32gui.PostMessage(buttons[0], win32con.BM_CLICK, 0, 0)
                else:
                    win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                closed += 1
            except Exception:
                continue
        return closed

    def _materialise(self, script: str | Path) -> tuple[Path | None, bool]:
        """Turn *script* into a file on disk.

        Returns ``(path, is_temporary)``.  *path* is ``None`` when the
        argument cannot be turned into a usable script file.

        An empty script is **not** turned into a file: ``Path("")`` is
        the current directory, and handing a directory to ``Praat.exe
        --send`` makes Praat try to *run* it.  Praat answers that with a
        modal "Message" box, which then blocks every later script and
        every later read of the Praat window.
        """

        if isinstance(script, Path):
            return (script if script.is_file() else None), False
        text = str(script)
        if not text.strip():
            return None, False
        if "\n" in text or "\r" in text:
            return self._write_temp_script(text), True
        candidate = Path(text)
        try:
            if candidate.is_file():
                return candidate, False
            if candidate.is_dir():
                # A directory is not a script, and Praat answers the
                # attempt with a modal Message box.
                return None, False
        except OSError:
            pass
        if text.lower().endswith(".praat"):
            # Looks like a path to a script that does not exist.
            return None, False
        return self._write_temp_script(text), True

    def _write_temp_script(self, text: str) -> Path | None:
        """Write script *text* to a temporary ``.praat`` file."""
        try:
            self._counter += 1
            path = self._temp_dir() / f"praatao_script_{os.getpid()}_{self._counter}.praat"
            path.write_text(text, encoding="utf-8")
            return path
        except Exception:
            return None

    # -- full snapshot -----------------------------------------------------

    def fast(self) -> PraatState:
        """The state of Praat, **without** running a Praat script.

        Running a script closes whatever menu the user has open - a menu
        that is open at that moment disappears, which makes Praat unusable
        for as long as the coach is watching.  So the hot path reads the
        window titles and the Objects window (through UI Automation)
        instead, and never sends a script.

        What this cannot give is the TextGrid tier names and the
        attributes of the selected Sound; those come from
        :meth:`snapshot`, which is used on demand.
        """

        state = self.quick()
        objects, selected = _objects_and_selection_via_uia()
        state.objects = objects
        state.selected = selected
        state.version = praat_version()
        state.raw = {
            "probe_ok": True,
            "source": "uia",
            "version": state.version,
            "selected": [
                {"id": obj.id, "type": obj.type, "name": obj.name}
                for obj in state.selected
            ],
            "objects": [
                {"id": obj.id, "type": obj.type, "name": obj.name}
                for obj in state.objects
            ],
            "tiers": list(state.textgrid_tiers),
            "tier_count": len(state.textgrid_tiers),
            "attributes": {},
            "has_textgrid": any(obj.type == "TextGrid" for obj in state.objects),
        }
        return state

    def snapshot(self, timeout: float = 3.0, require_focus: bool = False) -> PraatState:
        """Take a full semantic snapshot of Praat.

        Combines the Praat script probe (version, selection, TextGrid tiers)
        with the Objects window (the full object list).  Never raises.

        The script part **activates the Praat window**, so the caller has
        to be sure that is acceptable.  ``require_focus=True`` refuses to
        send anything while another program is in front.
        """

        budget = max(0.2, float(timeout))
        deadline = time.monotonic() + budget

        state = self.quick()
        if not state.running:
            state.error = "praat not running"
            return state

        if require_focus and not praat_has_focus():
            state.error = "praat is not in front (no script sent)"
            return state

        script_path: Path | None = None
        output_path: Path | None = None
        try:
            script_path, output_path = self._next_paths("snapshot")
            template = SNAPSHOT_PROBE.read_text(encoding="utf-8")
            praat_path = str(output_path).replace("\\", "/")
            script_path.write_text(template.replace("@OUT@", praat_path), encoding="utf-8")
            try:
                output_path.unlink()
            except OSError:
                pass

            remaining = max(0.2, deadline - time.monotonic())
            sent = self.send(script_path, timeout=remaining)

            data = self._wait_for_output(output_path, deadline)
            if data is None:
                state.error = "probe timed out" if not sent else "probe produced no output"
                state.raw = {"probe_ok": False, "error": state.error}
                return state

            parsed = parse_probe_output(decode_probe_bytes(data))
            state.version = parsed.get("version")
            state.selected = list(parsed.get("selected") or [])
            state.textgrid_tiers = list(parsed.get("tiers") or [])

            objects, object_source = self._read_object_list()
            if objects:
                state.objects = objects
                selected_ids = {obj.id for obj in state.selected}
                state.selected = [
                    obj for obj in objects if obj.id in selected_ids
                ] or state.selected
            else:
                state.objects = list(state.selected)
                object_source = "script"

            state.raw = {
                "probe_ok": bool(parsed.get("complete")),
                "version": state.version,
                "selected": [
                    {"id": obj.id, "type": obj.type, "name": obj.name}
                    for obj in state.selected
                ],
                "objects": [
                    {"id": obj.id, "type": obj.type, "name": obj.name}
                    for obj in state.objects
                ],
                "tiers": list(state.textgrid_tiers),
                "tier_count": parsed.get("tier_count", 0),
                "attributes": dict(parsed.get("attributes") or {}),
                "has_textgrid": any(obj.type == "TextGrid" for obj in state.objects),
                "source": f"script+{object_source}",
            }
            if not parsed.get("complete"):
                state.error = "probe incomplete"
            return state
        except Exception as exc:  # pragma: no cover - defensive
            state.error = f"{type(exc).__name__}: {exc}"
            return state
        finally:
            for path in (script_path, output_path):
                if path is None:
                    continue
                try:
                    path.unlink()
                except OSError:
                    pass

    def _wait_for_output(self, output_path: Path | None, deadline: float) -> bytes | None:
        """Poll for the probe output file until *deadline*."""
        if output_path is None:
            return None
        while True:
            try:
                if output_path.exists():
                    data = output_path.read_bytes()
                    if data:
                        return data
            except OSError:
                return None
            if time.monotonic() >= deadline:
                return None
            time.sleep(0.02)

    def _read_object_list(self) -> tuple[list[PraatObject], str]:
        """Read the full object list from Praat's Objects window.

        Returns ``(objects, source)`` where *source* names the reader that
        produced the list (``"uia"``, ``"listbox"`` or ``"script"``).
        """
        for items, source in (
            (_object_list_via_uia_sensor(), "uia"),
            (_read_objects_window_items(), "listbox"),
        ):
            objects: list[PraatObject] = []
            for item in items:
                parsed = parse_object_list_item(item)
                if parsed is not None:
                    objects.append(parsed)
            if objects:
                return objects, source
        return [], "script"

    # -- fast path ---------------------------------------------------------

    def quick(self) -> PraatState:
        """Window-title-only state.  No script, no I/O: a few hundred
        microseconds.  Used for hover responsiveness."""
        try:
            windows = _enum_praat_windows()
        except Exception:
            windows = []
        return state_from_windows(windows)
