"""Does the model really get the context?

Prints the prompt that goes to the model for one control in a
secondary window and the answer that comes back.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from praatao.sensors.praat_state import PraatObject, PraatState  # noqa: E402
from praatao.sensors.uia import Element  # noqa: E402
from praatao.tutor.advisor import Advisor  # noqa: E402
from praatao.tutor.kb import load_default  # noqa: E402
from praatao.tutor.llm import LlmClient  # noqa: E402


def main() -> int:
    llm = LlmClient.from_env()
    if llm is None:
        print("no model configured")
        return 1
    advisor = Advisor(load_default(), llm=llm, lang="zh")

    element = Element(
        name="To Intensity...",
        control_type="ButtonControl",
        automation_id="",
        hwnd=0,
        rect=(10, 20, 200, 60),
        window_title="Praat Objects",
        depth=1,
        enabled=True,
    )
    state = PraatState(
        running=True,
        version="6.4.12",
        objects=[PraatObject(id=1, type="Sound", name="demo_vowel")],
        selected=[PraatObject(id=1, type="Sound", name="demo_vowel")],
        editor_open=True,
        editor_object="1. Sound demo_vowel",
        textgrid_tiers=["phones", "words"],
        raw={"attributes": {"duration": 1.234, "samplingFrequency": 44100,
                            "channels": 1, "domain": "0.0 - 1.234 s"}},
    )

    print("=" * 70)
    print("PROMPT:")
    print(advisor._user_prompt(
        "这是什么？我该按下去吗？", element, state, [],
        "To Intensity...", "ButtonControl",
    ))
    print("=" * 70)

    start = time.time()
    advice = advisor.ask(
        "这是什么？我该按下去吗？", element=element, state=state
    )
    print(f"ANSWER ({time.time() - start:.1f} s):")
    print(advice.body if advice else "(nothing)")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
