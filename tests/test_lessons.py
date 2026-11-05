"""Tests for the lesson engine."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from praatao.tutor.lessons import LessonLibrary, LessonRunner, step_matches

PACK = """
version: 1
id: first-sound
title: {en: "Your first sound", zh: "你的第一个声音"}
steps:
  - id: read-file
    detect:
      object_types_present: []
    highlight: {kind: menu, path: ["Open", "Read from file..."]}
    tip: {en: "Load a WAV file", zh: "载入一个 WAV 文件"}
    detail: {en: "Praat needs a file to work on.", zh: "Praat 需要一个文件才能开始。"}
  - id: view-edit
    detect:
      selected_types: [Sound]
    highlight: {kind: button, name: "View & Edit"}
    tip: {en: "Open the editor", zh: "打开编辑器"}
  - id: annotate
    detect:
      editor_open: true
    highlight: {kind: button, name: "TextGrid"}
    tip: {en: "Annotate", zh: "标注"}
"""


def make_state(objects=(), selected=(), editor_open=False):
    return SimpleNamespace(
        objects=[SimpleNamespace(type=t, name=n) for t, n in objects],
        selected=[SimpleNamespace(type=t, name=n) for t, n in selected],
        editor_open=editor_open,
    )


class DetectTests(unittest.TestCase):
    def test_empty_detect_always_matches(self):
        self.assertTrue(step_matches({}, None))

    def test_object_types_present(self):
        detect = {"object_types_present": ["Sound"]}
        self.assertTrue(step_matches(detect, make_state([("Sound", "a")])))
        self.assertFalse(step_matches(detect, make_state([("TextGrid", "a")])))

    def test_selected_types(self):
        detect = {"selected_types": ["Sound"]}
        self.assertTrue(step_matches(detect, make_state([("Sound", "a")], [("Sound", "a")])))
        self.assertFalse(step_matches(detect, make_state([("Sound", "a")])))

    def test_editor_open(self):
        detect = {"editor_open": True}
        self.assertTrue(step_matches(detect, make_state(editor_open=True)))
        self.assertFalse(step_matches(detect, make_state(editor_open=False)))

    def test_none_state_does_not_match(self):
        self.assertFalse(step_matches({"selected_types": ["Sound"]}, None))


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        (self.dir / "01-first.yaml").write_text(PACK, encoding="utf-8")
        self.lib = LessonLibrary.load(self.dir)

    def tearDown(self):
        self.tmp.cleanup()

    def test_loads_lesson(self):
        self.assertEqual(len(self.lib), 1)
        lesson = self.lib.get("first-sound")
        self.assertIsNotNone(lesson)
        self.assertEqual(len(lesson.steps), 3)
        self.assertEqual(lesson.title("zh"), "你的第一个声音")

    def test_highlight_parsed(self):
        step = self.lib.get("first-sound").steps[0]
        self.assertEqual(step.highlight.kind, "menu")
        self.assertEqual(step.highlight.path, ["Open", "Read from file..."])


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        (self.dir / "01-first.yaml").write_text(PACK, encoding="utf-8")
        self.lib = LessonLibrary.load(self.dir)
        self.runner = LessonRunner(self.lib)

    def tearDown(self):
        self.tmp.cleanup()

    def test_start_and_first_step(self):
        self.runner.start("first-sound")
        self.assertIsNotNone(self.runner.next_step())
        self.assertEqual(self.runner.next_step().id, "read-file")

    def test_sync_advances_when_satisfied(self):
        self.runner.start("first-sound")
        step = self.runner.sync(make_state([("Sound", "a")]))
        # read-file is satisfied by nothing, so we move to view-edit
        self.assertEqual(step.id, "view-edit")
        self.assertEqual(self.runner.progress(), (1, 3))

    def test_sync_stops_at_unsatisfied(self):
        self.runner.start("first-sound")
        self.runner.sync(make_state([("Sound", "a")]))
        step = self.runner.sync(make_state([("Sound", "a")]))
        self.assertEqual(step.id, "view-edit")

    def test_advance(self):
        self.runner.start("first-sound")
        self.runner.advance()
        self.assertEqual(self.runner.progress(), (1, 3))

    def test_unknown_lesson(self):
        self.assertIsNone(self.runner.start("nope"))


if __name__ == "__main__":
    unittest.main()
