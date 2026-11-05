"""Praat process / window / probe bridge for Praatao v0."""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

import win32gui

ROOT = Path(__file__).resolve().parents[2]
V0 = Path(__file__).resolve().parent
PRAAT = ROOT / "Praat.exe"
STATE_PATH = V0 / "last_state.json"
PROBES = V0 / "probes"

# App can set this after Load demo / successful read so we do not need select-all.
_known_has_sound = False


def note_sound_loaded() -> None:
    global _known_has_sound
    _known_has_sound = True


def clear_sound_knowledge() -> None:
    global _known_has_sound
    _known_has_sound = False


@dataclass
class PraatWindow:
    hwnd: int
    title: str
    rect: tuple[int, int, int, int]
    kind: str  # objects | picture | editor | other


@dataclass
class PraatState:
    running: bool = False
    object_count: int = 0
    objects: list[str] = field(default_factory=list)
    selected: list[str] = field(default_factory=list)
    windows: list[PraatWindow] = field(default_factory=list)
    has_sound: bool = False
    sound_selected: bool = False
    textgrid_selected: bool = False
    sound_and_textgrid_selected: bool = False
    editor_open: bool = False
    raw: dict = field(default_factory=dict)

    def fingerprint(self) -> tuple:
        return (
            self.running,
            self.has_sound,
            self.sound_selected,
            self.editor_open,
            tuple(self.selected),
            tuple((w.kind, w.title, w.rect) for w in self.windows),
        )


def _classify_title(title: str) -> str:
    t = title.lower().strip()
    if "praat objects" in t:
        return "objects"
    if "praat picture" in t:
        return "picture"
    if t.startswith("sound ") or t.startswith("textgrid ") or t.startswith("longsound "):
        return "editor"
    if "praat" in t:
        return "other"
    return "other"


def find_praat_windows() -> list[PraatWindow]:
    found: list[PraatWindow] = []

    def enum_handler(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if not title or "praatao" in title.lower():
            return
        lower = title.lower()
        looks_praat = (
            "praat" in lower
            or lower.startswith("sound ")
            or lower.startswith("textgrid ")
            or lower.startswith("longsound ")
        )
        if not looks_praat:
            return
        try:
            rect = win32gui.GetWindowRect(hwnd)
        except Exception:
            return
        found.append(
            PraatWindow(hwnd=hwnd, title=title, rect=rect, kind=_classify_title(title))
        )

    win32gui.EnumWindows(enum_handler, None)
    return found


def is_praat_running() -> bool:
    wins = find_praat_windows()
    return any(w.kind in {"objects", "picture", "editor"} for w in wins) or any(
        "praat" in w.title.lower() for w in wins
    )


def launch_praat() -> None:
    if not PRAAT.exists():
        raise FileNotFoundError(PRAAT)
    subprocess.Popen([str(PRAAT)], cwd=str(ROOT))


def send_script(script: Path, timeout: float = 8.0) -> None:
    """Hand a script to the live Praat GUI via ``--send`` (stdout silenced)."""
    if not PRAAT.exists():
        raise FileNotFoundError(PRAAT)
    subprocess.run(
        [str(PRAAT), "--send", str(script)],
        check=False,
        timeout=timeout,
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def sense_windows_only() -> PraatState:
    """Fast, non-invasive: HWND titles only (no Praat script)."""
    windows = find_praat_windows()
    running = is_praat_running()
    state = PraatState(running=running, windows=windows)
    state.editor_open = any(w.kind == "editor" for w in windows)
    # Editor title like "Sound demo_vowel" implies a Sound exists / is open
    sound_editor = any(w.title.lower().startswith("sound ") for w in windows)
    state.has_sound = sound_editor or _known_has_sound
    if sound_editor:
        state.sound_selected = True  # editor implies that sound is in play
        note_sound_loaded()
    return state


def probe_state(wait: float = 0.15) -> PraatState:
    """Window sense + light selection probe (does not select all)."""
    state = sense_windows_only()
    if not state.running:
        return state

    try:
        if STATE_PATH.exists():
            STATE_PATH.unlink()
    except OSError:
        pass

    try:
        send_script(PROBES / "dump_state.praat")
    except Exception as exc:
        state.raw = {"error": str(exc)}
        return state

    deadline = time.time() + 2.5
    while time.time() < deadline and not STATE_PATH.exists():
        time.sleep(0.04)
    time.sleep(wait)

    if not STATE_PATH.exists():
        state.raw = {"error": "no state file"}
        return state

    try:
        raw = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        state.raw = {"error": f"json: {exc}"}
        return state

    state.raw = raw
    selected = [o.get("label", "") for o in raw.get("selected") or []]
    state.selected = selected
    state.objects = list(selected)  # without select-all we only know selection
    state.object_count = int(raw.get("selectedCount") or len(selected))

    n_sound = int(raw.get("selectedSoundCount") or 0)
    n_tg = int(raw.get("selectedTextGridCount") or 0)
    state.sound_selected = n_sound > 0 or any(x.startswith("Sound ") for x in selected)
    state.textgrid_selected = n_tg > 0 or any(x.startswith("TextGrid ") for x in selected)
    state.sound_and_textgrid_selected = state.sound_selected and state.textgrid_selected

    if state.sound_selected or state.editor_open:
        note_sound_loaded()
    state.has_sound = state.has_sound or state.sound_selected or _known_has_sound
    return state


def load_demo_sound() -> None:
    send_script(PROBES / "load_demo.praat")
    note_sound_loaded()
