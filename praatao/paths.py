"""Paths and constants for Praatao v1."""

from __future__ import annotations

import os
import sys
from pathlib import Path

#: True when the program runs from the packaged executable.
FROZEN = bool(getattr(sys, "frozen", False))

if FROZEN:
    # The executable sits where the student put it; Praat.exe is expected
    # next to it.
    ROOT = Path(sys.executable).resolve().parent
    # One-file builds unpack their data into a temporary folder.
    _bundle = getattr(sys, "_MEIPASS", None)
    if _bundle:
        CONTENT_DIR = Path(_bundle) / "praatao" / "content"
    else:
        CONTENT_DIR = Path(sys.executable).resolve().parent / "praatao" / "content"
else:
    #: Repository root (the folder that holds ``Praat.exe`` and ``praatao/``).
    ROOT = Path(__file__).resolve().parents[1]
    #: Content packs: UI-element dictionary and lesson packs.
    CONTENT_DIR = Path(__file__).resolve().parent / "content"

#: The Praat binary shipped with this project.
PRAAT_EXE = ROOT / "Praat.exe"

ELEMENTS_FILE = CONTENT_DIR / "elements.yaml"
LESSONS_DIR = CONTENT_DIR / "lessons"

#: Where runtime state (probe files, caches) is written.
STATE_DIR = Path(
    os.environ.get("PRAATAO_STATE_DIR")
    or (Path(os.environ.get("LOCALAPPDATA") or (Path.home() / ".local" / "share")) / "praatao")
)


def ensure_state_dir() -> Path:
    """Create and return the runtime state directory."""

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    return STATE_DIR
