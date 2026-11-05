"""Does a Praat script close an open menu?"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from praatao.paths import PRAAT_EXE  # noqa: E402


def main() -> int:
    from praatao.sensors import uia as uia_module
    from praatao.sensors.uia import PraatUI

    ui = PraatUI()
    objects = ui.objects_window()

    def menus() -> int:
        ctrl = ui._control_from_window(objects)
        return len([
            n for n, _d in ui._iter_controls(ctrl)
            if uia_module._text(n, "ControlTypeName") == "MenuControl"
        ])

    out = Path(tempfile.gettempdir()) / "praatao_trivial.txt"
    script = Path(tempfile.gettempdir()) / "praatao_trivial.praat"
    script.write_text(
        'writeFileLine("%s", "hi")\n' % str(out).replace("\\", "/"),
        encoding="utf-8",
    )

    items = ui.open_menu(objects, "Open", keep_open=True)
    time.sleep(0.3)
    print("menu open      : menus =", menus())
    start = time.time()
    subprocess.run([str(PRAAT_EXE), "--send", str(script)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("send took      : %.2f s" % (time.time() - start))
    time.sleep(0.5)
    print("after the script: menus =", menus())
    ui.close_popup()
    return 0


if __name__ == "__main__":
    sys.exit(main())
