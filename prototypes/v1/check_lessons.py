"""Check that the lesson packs load and the runner walks through them."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from praatao import paths
from praatao.tutor.kb import load_default
from praatao.tutor.lessons import LessonLibrary, LessonRunner

lib = LessonLibrary.load(paths.LESSONS_DIR)
print("lessons:", len(lib))
for lesson in lib.lessons():
    print(f"  {lesson.id}: {lesson.title('zh')}  ({len(lesson.steps)} steps)")
    for step in lesson.steps:
        print(f"      - {step.id}: {step.tip('zh')[:50]}")

runner = LessonRunner(lib)
runner.start(lib.lessons()[0].id)
print("current step:", runner.next_step().id)
print("progress:", runner.progress())

kb = load_default()
print("kb entries:", len(kb))
print("kb stats:", kb.stats())
