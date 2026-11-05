"""Check that the late model answer really arrives."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from praatao.tutor.advisor import Advisor
    from praatao.tutor.kb import load_default
    from praatao.tutor.llm import LlmClient

    client = LlmClient.from_env()
    print("configured:", client.available(), client.config.model)
    advisor = Advisor(load_default(), llm=client, lang="zh")

    element = SimpleNamespace(
        name="Xyzzy Blorb", control_type="ButtonControl", automation_id="",
        hwnd=0, rect=(0, 0, 10, 10), window_title="Praat Objects", depth=0,
    )

    got: list = []
    started = time.time()

    def on_llm(advice) -> None:
        print(f"  answer after {time.time() - started:.1f} s")
        got.append(advice)

    advice = advisor.advise(element, on_llm=on_llm)
    print("immediate:", advice.headline, "|", advice.body[:60].replace("\n", " "))
    for _ in range(150):
        if got:
            break
        time.sleep(0.2)
    if not got:
        print("NO ANSWER after 30 s")
        return 1
    print("body:", got[0].body[:300].replace("\n", " | "))
    return 0


if __name__ == "__main__":
    sys.exit(main())
