"""Check that invoke() really activates a Praat button (uses the harmless 'Play')."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from praatao.sensors.uia import PraatUI  # noqa: E402


def main() -> int:
    ui = PraatUI()
    obj = ui.objects_window()
    if obj is None:
        print("Praat not running")
        return 1
    button = ui.find("Play", window=obj)
    print("Play button:", button)
    if button is None:
        print("no Play button (is a Sound selected?)")
        return 1
    print("invoke ->", ui.invoke(button))
    time.sleep(1.0)
    # The button must still be there and Praat must still be responsive.
    print("still there:", ui.find("Play", window=obj) is not None)
    print("windows:", [(w.title, w.kind) for w in ui.windows()])
    return 0


if __name__ == "__main__":
    sys.exit(main())
