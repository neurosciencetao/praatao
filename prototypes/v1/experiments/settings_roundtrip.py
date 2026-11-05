"""Does the settings window really change the coach while it runs?"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from praatao.settings import Settings, settings_path  # noqa: E402
import run as praatao_run  # noqa: E402


def main() -> int:
    # Start from a known state: Chinese, model on, no pictures.
    Settings(lang="zh", use_llm=True, allow_vision=False).save()
    app = praatao_run.Praatao(lang="zh", use_llm=False, ui_backend="qt")
    app.host.after(praatao_run.MOUSE_POLL_MS, app._mouse_poll)
    app.host.after(45, app._tick)

    window = app.settings_window
    window.show()
    for _ in range(20):
        app.pump()
        time.sleep(0.05)

    print("language before:", app.lang)
    print("llm before    :", app.advisor.llm.available())

    window.language_box.setCurrentIndex(window.language_box.findData("en"))
    window.llm_box.setChecked(False)
    window.apply()
    for _ in range(20):
        app.pump()
        time.sleep(0.05)

    print("language after :", app.lang)
    print("llm after      :", app.advisor.llm.available())
    print("panel lang     :", app.panel.lang)
    print("vision env     :", "PRAATAO_VISION" in __import__("os").environ)

    saved = json.loads(settings_path().read_text(encoding="utf-8"))
    print("saved file     :", saved)

    app.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
