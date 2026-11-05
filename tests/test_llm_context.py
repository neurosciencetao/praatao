"""The model has to be told more than the label of the control.

The student asked for an answer that takes the *situation* into account:
which object is selected, what the editor shows, what the tiers are.  These
tests pin that context into the prompt.
"""

from __future__ import annotations

import unittest

from praatao.sensors.praat_state import PraatObject, PraatState
from praatao.sensors.uia import Element
from praatao.tutor.advisor import Advisor
from praatao.tutor.kb import load_default


def _element(name: str = "To Intensity...") -> Element:
    return Element(
        name=name,
        control_type="ButtonControl",
        automation_id="",
        hwnd=0,
        rect=(10, 20, 200, 60),
        window_title="Praat Objects",
        depth=1,
        enabled=True,
    )


def _state() -> PraatState:
    return PraatState(
        running=True,
        version="6.4.12",
        objects=[PraatObject(id=1, type="Sound", name="demo_vowel")],
        selected=[PraatObject(id=1, type="Sound", name="demo_vowel")],
        editor_open=True,
        editor_object="1. Sound demo_vowel",
        textgrid_tiers=["phones"],
        raw={"attributes": {"duration": 1.234, "samplingFrequency": 44100}},
    )


class PromptContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.advisor = Advisor(load_default(), lang="zh")

    def test_the_prompt_carries_the_state(self) -> None:
        prompt = self.advisor._user_prompt(
            "", _element(), _state(), [], "To Intensity...", "ButtonControl"
        )
        self.assertIn("demo_vowel", prompt)
        self.assertIn("Sound", prompt)
        self.assertIn("phones", prompt)
        self.assertIn("duration", prompt)
        self.assertIn("44100", prompt)

    def test_the_prompt_carries_the_window(self) -> None:
        prompt = self.advisor._user_prompt(
            "", _element(), None, [], "To Intensity...", "ButtonControl"
        )
        self.assertIn("Praat Objects", prompt)

    def test_the_prompt_asks_for_a_contextual_answer(self) -> None:
        prompt = self.advisor._user_prompt(
            "", _element(), _state(), [], "To Intensity...", "ButtonControl"
        )
        self.assertIn("context", prompt.casefold())

    def test_the_prompt_works_without_a_state(self) -> None:
        prompt = self.advisor._user_prompt(
            "what is this?", _element(), None, [], "To Intensity...", "ButtonControl"
        )
        self.assertIn("what is this?", prompt)
        self.assertIn("To Intensity...", prompt)


if __name__ == "__main__":
    unittest.main()
