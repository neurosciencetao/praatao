"""End-to-end test of the drawn teaching picture."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

os.environ["PRAATAO_IMAGEGEN"] = "1"


def main() -> int:
    import run as praatao_run

    app = praatao_run.Praatao(lang="zh", use_llm=True)
    print("backend:", app.backend)
    print("tutor  :", app.advisor.status())

    element = SimpleNamespace(
        name="Xyzzy Blorb", control_type="ButtonControl", automation_id="",
        hwnd=0, rect=(100, 100, 220, 130), window_title="Praat Objects", depth=0,
    )
    app.card.show("?", "准备中", anchor=(150, 150), rect=(100, 100, 220, 130),
                  source="", signature=("probe", "s"))
    app._current_rect = (100, 100, 220, 130)
    app._last_key = "probe"
    app.pump()

    started = time.time()
    app.advisor.advise(element, state=app.state,
                       on_llm=app._on_llm_answer("probe"),
                       on_image=app._on_llm_image("probe"))
    print("asked the model, waiting for the picture ...")

    deadline = time.time() + 90
    while time.time() < deadline:
        app.pump()
        try:
            if app.card.image_label.isVisible():
                break
        except Exception:
            pass
        time.sleep(0.3)
    elapsed = time.time() - started
    try:
        visible = app.card.image_label.isVisible()
    except Exception:
        visible = False
    print(f"picture after {elapsed:.1f} s : visible={visible}")
    if visible:
        out = ROOT / "docs" / "screenshots" / "generated-teaching-picture.png"
        app.card.image_label.pixmap().save(str(out))
        print("saved", out)
    app.quit()
    return 0 if visible else 1


if __name__ == "__main__":
    sys.exit(main())
