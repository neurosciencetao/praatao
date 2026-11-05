"""Lesson packs: ordered, declarative steps that react to Praat's state."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

from .kb import _bilingual, _clean


@dataclass
class Highlight:
    """Where the spotlight should point for this step."""

    kind: str = "button"          # menu | button | list | region | none
    path: list[str] = field(default_factory=list)
    name: str = ""

    @classmethod
    def from_raw(cls, raw: Any) -> "Highlight":
        if not raw:
            return cls(kind="none")
        if isinstance(raw, str):
            return cls(kind="button", name=raw)
        return cls(
            kind=_clean(raw.get("kind")) or "button",
            path=[_clean(p) for p in (raw.get("path") or []) if _clean(p)],
            name=_clean(raw.get("name")),
        )


@dataclass
class LessonStep:
    id: str
    detect: dict[str, Any] = field(default_factory=dict)
    highlight: Highlight = field(default_factory=Highlight)
    tip_en: str = ""
    tip_zh: str = ""
    detail_en: str = ""
    detail_zh: str = ""

    def tip(self, lang: str = "zh") -> str:
        return self.tip_zh if lang == "zh" else self.tip_en

    def detail(self, lang: str = "zh") -> str:
        return self.detail_zh if lang == "zh" else self.detail_en


@dataclass
class Lesson:
    id: str
    title_en: str = ""
    title_zh: str = ""
    steps: list[LessonStep] = field(default_factory=list)

    def title(self, lang: str = "zh") -> str:
        return self.title_zh if lang == "zh" else self.title_en


def _state_types(state: Any) -> set[str]:
    objects = getattr(state, "objects", None) or []
    out = set()
    for obj in objects:
        t = getattr(obj, "type", None)
        if t:
            out.add(str(t))
    return out


def _selected_types(state: Any) -> set[str]:
    selected = getattr(state, "selected", None) or []
    out = set()
    for obj in selected:
        t = getattr(obj, "type", None)
        if t:
            out.add(str(t))
    return out


def step_matches(detect: dict[str, Any], state: Any) -> bool:
    """Does the current Praat state satisfy this step's detect rule?

    A step with no ``detect`` block is always considered satisfied (it is a
    purely instructional step).
    """
    if not detect:
        return True
    if state is None:
        return False

    present = _state_types(state)
    selected = _selected_types(state)

    for t in detect.get("object_types_present") or []:
        if str(t) not in present:
            return False
    any_present = detect.get("object_types_present_any")
    if any_present and not (set(map(str, any_present)) & present):
        return False
    for t in detect.get("selected_types") or []:
        if str(t) not in selected:
            return False
    any_selected = detect.get("selected_types_any")
    if any_selected and not (set(map(str, any_selected)) & selected):
        return False
    if "editor_open" in detect and detect["editor_open"] is not None:
        if bool(getattr(state, "editor_open", False)) != bool(detect["editor_open"]):
            return False
    min_objects = detect.get("min_objects")
    if min_objects is not None:
        if len(getattr(state, "objects", None) or []) < int(min_objects):
            return False
    min_selected = detect.get("min_selected")
    if min_selected is not None:
        if len(getattr(state, "selected", None) or []) < int(min_selected):
            return False
    return True


class LessonLibrary:
    """All lesson packs found on disk."""

    def __init__(self, lessons: Iterable[Lesson] | None = None) -> None:
        self._lessons: list[Lesson] = list(lessons or [])
        self._by_id = {lesson.id.casefold(): lesson for lesson in self._lessons}

    @classmethod
    def load(cls, directory: str | Path) -> "LessonLibrary":
        directory = Path(directory)
        lessons: list[Lesson] = []
        if yaml is None or not directory.exists():
            return cls(lessons)
        for path in sorted(directory.glob("*.yaml")):
            if path.name == "index.yaml":
                continue
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            lesson = cls._lesson_from_raw(data, path.stem)
            if lesson is not None:
                lessons.append(lesson)
        return cls(lessons)

    @staticmethod
    def _lesson_from_raw(data: dict[str, Any], fallback_id: str) -> "Lesson | None":
        if not isinstance(data, dict):
            return None
        lesson = Lesson(
            id=_clean(data.get("id")) or fallback_id,
            title_en=_bilingual(data.get("title"), "en"),
            title_zh=_bilingual(data.get("title"), "zh"),
        )
        for raw in data.get("steps") or []:
            if not isinstance(raw, dict):
                continue
            lesson.steps.append(
                LessonStep(
                    id=_clean(raw.get("id")) or f"step-{len(lesson.steps) + 1}",
                    detect=raw.get("detect") or {},
                    highlight=Highlight.from_raw(raw.get("highlight")),
                    tip_en=_bilingual(raw.get("tip"), "en"),
                    tip_zh=_bilingual(raw.get("tip"), "zh"),
                    detail_en=_bilingual(raw.get("detail"), "en"),
                    detail_zh=_bilingual(raw.get("detail"), "zh"),
                )
            )
        return lesson

    def lessons(self) -> list[Lesson]:
        return list(self._lessons)

    def get(self, lesson_id: str) -> Lesson | None:
        return self._by_id.get(lesson_id.casefold())

    def __len__(self) -> int:
        return len(self._lessons)


class LessonRunner:
    """Tracks which step of a lesson the user is on."""

    def __init__(self, library: LessonLibrary | None = None) -> None:
        self.library = library or LessonLibrary()
        self.lesson: Lesson | None = None
        self.step_index: int = 0
        self.completed: set[str] = set()

    # -- control ----------------------------------------------------
    def start(self, lesson_id: str) -> Lesson | None:
        lesson = self.library.get(lesson_id)
        if lesson is None:
            return None
        self.lesson = lesson
        self.step_index = 0
        self.completed = set()
        return lesson

    def stop(self) -> None:
        self.lesson = None
        self.step_index = 0

    def next_step(self) -> LessonStep | None:
        if self.lesson is None:
            return None
        if self.step_index < len(self.lesson.steps):
            return self.lesson.steps[self.step_index]
        return None

    def advance(self) -> LessonStep | None:
        if self.lesson is None:
            return None
        step = self.next_step()
        if step is not None:
            self.completed.add(step.id)
        self.step_index += 1
        return self.next_step()

    # -- state-driven -----------------------------------------------
    def sync(self, state: Any) -> LessonStep | None:
        """Advance past steps whose detect rule is already satisfied.

        Returns the step the user should be working on right now, or ``None``.
        """
        if self.lesson is None:
            return None
        # Never skip more than a couple of steps per sync: a user may satisfy
        # several detect rules at once, and jumping the whole lesson would be
        # confusing.
        for _ in range(2):
            step = self.next_step()
            if step is None:
                return None
            if not step.detect:
                return step
            if step_matches(step.detect, state):
                self.completed.add(step.id)
                self.step_index += 1
                continue
            return step
        return self.next_step()

    def progress(self) -> tuple[int, int]:
        if self.lesson is None:
            return (0, 0)
        return (min(self.step_index, len(self.lesson.steps)), len(self.lesson.steps))
