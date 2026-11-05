"""End-to-end test of the late model answer in the real application.

Hovers a control the knowledge base does not know, waits for the model
answer, and checks that the open card is updated in place.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from types import SimpleNamespace  # noqa: E402


def main() -> int:
    import run as praatao_run

    app = praatao_run.Praatao(lang="zh", use_llm=True)
    print("backend:", app.backend)
    print("tutor  :", app.advisor.status())

    # A control the knowledge base certainly does not cover.
    element = SimpleNamespace(
        name="Xyzzy Blorb",
        control_type="ButtonControl",
        automation_id="",
        hwnd=0,
        rect=(100, 100, 220, 130),
        window_title="Praat Objects",
        depth=0,
        enabled=True,
    )

    app.card.show("?", "准备中", anchor=(150, 150), rect=(100, 100, 220, 130),
                  source="", signature=("probe", "s"))
    app._current_rect = (100, 100, 220, 130)
    app._last_key = "probe"
    app.pump()

    advice = app.advisor.advise(
        element, state=app.state, on_llm=app._on_llm_answer("probe")
    )
    print("headline :", advice.headline)
    print("body     :", advice.body[:120].replace("\n", " | "))
    app.card.update_body(advice.body)
    app.pump()

    print("waiting for the model ...")
    deadline = time.time() + 40
    last = ""
    while time.time() < deadline:
        app.pump()
        text = app.card.body.toPlainText()
        if text != last:
            last = text
        if "AI" in text or len(text) > 200:
            break
        time.sleep(0.2)
    print("card now :", last[:300].replace("\n", " | "))
    app.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())


