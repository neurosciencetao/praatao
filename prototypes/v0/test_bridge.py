"""Headless checks for Praatao v0 bridge (no Tk UI)."""

from __future__ import annotations

import json
import sys
import time

from lessons import match_step
from praat_bridge import (
    is_praat_running,
    launch_praat,
    load_demo_sound,
    note_sound_loaded,
    probe_state,
)


def main() -> int:
    print("== Praatao v0 bridge test ==")
    if not is_praat_running():
        print("Praat not running — launching…")
        launch_praat()
        time.sleep(2.0)

    assert is_praat_running(), "Praat windows not detected"
    print("OK praat running")

    print("Loading demo sound…")
    load_demo_sound()
    note_sound_loaded()
    time.sleep(0.8)

    state = probe_state()
    print("state.raw:", json.dumps(state.raw, ensure_ascii=False))
    print("selected:", state.selected)
    print("has_sound:", state.has_sound, "sound_selected:", state.sound_selected)
    print("editor_open:", state.editor_open)
    print("windows:", [(w.kind, w.title) for w in state.windows])

    assert state.has_sound or state.sound_selected or state.editor_open, "expected sound signal"
    step = match_step(state, set())
    print("matched step:", step.id, "—", step.title)
    assert step.id in {"select-sound", "view-edit", "spectrogram", "bonus-textgrid"}, step.id

    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
