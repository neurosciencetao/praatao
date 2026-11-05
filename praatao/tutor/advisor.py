"""Turn a Praat control + the live Praat state into teaching text.

The advisor is the "what should we say?" layer of Praatao:

* it looks a control up in the bilingual knowledge base
  (:mod:`praatao.tutor.kb`) and renders *what / how / concept / pitfalls*
* it appends **context-aware** remarks derived from the live Praat state
  (selected Sound, open editor, missing TextGrid, ...)
* when the control is unknown it falls back to an optional LLM that is
  grounded with the raw control name, the state summary and the top knowledge
  base entries.

The module is written so that it keeps working while sibling modules are
still under construction: the knowledge base is imported defensively and the
sensor types are only needed for type checking.  Nothing here imports
``praatao.ui``.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence, TYPE_CHECKING

from .llm import LlmClient, NullLlmClient, default_llm_client

try:  # pragma: no cover - the knowledge base ships with the package
    from .kb import KnowledgeBase, KnowledgeEntry
except Exception:  # noqa: BLE001 - keep partial checkouts importable
    KnowledgeBase = Any  # type: ignore[assignment,misc]
    KnowledgeEntry = Any  # type: ignore[assignment,misc]

if TYPE_CHECKING:  # pragma: no cover
    from ..sensors.praat_state import PraatState, PraatStateProbe
    from ..sensors.uia import Element

__all__ = [
    "Advice",
    "Advisor",
    "NullLlmClient",  # re-exported: the default "LLM off" client
    "LANG_ZH",
    "LANG_EN",
    "SUPPORTED_LANGS",
]

LANG_ZH = "zh"
LANG_EN = "en"
SUPPORTED_LANGS: tuple[str, ...] = (LANG_ZH, LANG_EN)

#: Advice sources.
SOURCE_KB = "kb"
SOURCE_LLM = "llm"
SOURCE_KB_LLM = "kb+llm"


# ----------------------------------------------------------------------
# tutor-owned strings (both languages always exist here)
# ----------------------------------------------------------------------
_STRINGS: dict[str, dict[str, str]] = {
    LANG_ZH: {
        "section_what": "这是什么",
        "section_how": "怎么用",
        "section_concept": "概念",
        "section_pitfalls": "常见坑",
        "unknown_headline": "还不认识这个控件",
        "unknown_body": "知识库里还没有这个控件的说明。",
        "unknown_related": "知识库里可能相关的条目：",
        "selected_sound": "已选中 Sound {name}",
        "detail_duration": "时长 {value} 秒",
        "detail_rate": "采样率 {value} Hz",
        "detail_channels": "声道数 {value}",
        "open_editor_hint": "点这个可以打开编辑器。",
        "selected_other": "当前选中：{items}",
        "editor_open": "编辑器已打开 {name}",
        "no_selection": "先在 Objects 窗口里选中一个对象，这个按钮才会生效。",
        "view_edit_object": "已选中 {type} {name}，点这个可以打开编辑器。",
        "need_textgrid_first": (
            "还没有 TextGrid：先在 Objects 窗口里选中一个 Sound，"
            "再点这个按钮来创建；Sound 没有被选中时，这个按钮不会显示。"
        ),
        "textgrid_exists": "Objects 窗口里已经有 TextGrid：{names}",
        "missing_object": "Objects 窗口里还没有 {type} 对象，先创建或读入一个。",
        "not_selected": "请先在 Objects 窗口里选中 {type} {name}。",
        "ask_headline": "关于「{question}」",
        "ask_matches": "知识库匹配到的条目：",
        "ask_no_match": "知识库里没有找到相关条目。",
        "ask_intro": "先看知识库里的相关条目：",
        "llm_note": "（本地知识库没有这个控件，以上内容由模型生成，可能不够准确。）",
        "llm_pending": "（本地知识库没有这个控件，正在请模型回答，稍后会自动补上。）",
        "canvas_title": "绘图区",
        "canvas_object": "当前显示的是 {name}。",
        "canvas_window": "当前窗口：{name}。",
        "canvas_guess": "本地判断这张图看起来像：{kind}。",
        "vision_pending": "（正在请模型看这张图，答案稍后自动补上。）",
        "vision_note": "（以上是模型看着绘图区给出的判断，可能不准确。）",
        "status": "导师：知识库 {n} 条 · 大模型 {llm} · 语言 {lang}",
        "status_lang": "中文",
        "llm_on": "已开启",
        "llm_off": "未开启（离线模式）",
        "list_sep": "、",
    },
    LANG_EN: {
        "section_what": "What it is",
        "section_how": "How to use it",
        "section_concept": "Concept",
        "section_pitfalls": "Common pitfalls",
        "unknown_headline": "Unknown control",
        "unknown_body": "The knowledge base has no entry for this control yet.",
        "unknown_related": "Possibly related knowledge base entries:",
        "selected_sound": "Selected Sound {name}",
        "detail_duration": "duration {value} s",
        "detail_rate": "sampling rate {value} Hz",
        "detail_channels": "{value} channel(s)",
        "open_editor_hint": "click this to open the editor.",
        "selected_other": "Currently selected: {items}",
        "editor_open": "The editor is open on {name}",
        "no_selection": "Select an object in the Objects window first, then this button works.",
        "view_edit_object": "{type} {name} is selected - click this to open the editor.",
        "need_textgrid_first": (
            "There is no TextGrid yet: select a Sound in the Objects window first, "
            "then click this button to create one. This button only appears when a "
            "Sound is selected."
        ),
        "textgrid_exists": "TextGrid already in the Objects window: {names}",
        "missing_object": "There is no {type} object in the Objects window yet - create or read one first.",
        "not_selected": "Select {type} {name} in the Objects window first.",
        "ask_headline": "About: {question}",
        "ask_matches": "Knowledge base entries that match:",
        "ask_no_match": "No matching entry in the knowledge base.",
        "ask_intro": "Related entries from the knowledge base:",
        "llm_note": "(This control is not in the local knowledge base; the text above was generated by a model and may be inaccurate.)",
        "llm_pending": "(This control is not in the local knowledge base; asking the model, the answer will appear here in a moment.)",
        "canvas_title": "The drawing area",
        "canvas_object": "Currently showing {name}.",
        "canvas_window": "Current window: {name}.",
        "canvas_guess": "Locally, this picture looks like: {kind}.",
        "vision_pending": "(Asking the model to look at this picture; the answer will appear here in a moment.)",
        "vision_note": "(The text above is the model's reading of the drawing area and may be inaccurate.)",
        "status": "Tutor: {n} entries · LLM {llm} · language {lang}",
        "status_lang": "English",
        "llm_on": "on",
        "llm_off": "off (offline mode)",
        "list_sep": ", ",
    },
}

#: Dynamic action buttons and the object type they need.
_DYNAMIC_REQUIREMENTS: dict[str, str] = {
    "query": "Sound",
    "modify": "Sound",
    "annotate": "Sound",
    "analyse periodicity": "Sound",
    "analyse spectrum": "Sound",
    "manipulate": "Sound",
    "convert": "Sound",
    "filter": "Sound",
    "combine": "Sound",
    "draw": "Sound",
    "to textgrid": "Sound",
    "to pitch": "Sound",
    "to intensity": "Sound",
    "to spectrum": "Sound",
    "to formants": "Sound",
    "to harmonics": "Sound",
    "to manipulation": "Sound",
    "to duration": "Sound",
    "to table": "Sound",
    "to matrix": "Sound",
    "to klattgrid": "Sound",
    "to harmonicity": "Sound",
    "to points": "Sound",
    "to phonogram": "Sound",
    "to curve": "Sound",
    "to tier": "TextGrid",
    "to intervals": "TextGrid",
    "to tier table": "TextGrid",
}

#: Object type whose absence must be reported for these controls.
_TEXTGRID_FROM_SOUND = ("to textgrid", "annotate")


@dataclass
class Advice:
    """What the tutor wants to say about one control."""

    headline: str
    body: str
    source: str  # 'kb' | 'llm' | 'kb+llm'
    element_key: str | None = None
    entries: list[KnowledgeEntry] = field(default_factory=list)


class Advisor:
    """Compose teaching text for a Praat control or a free-text question.

    Parameters
    ----------
    kb:
        The bilingual knowledge base.
    state:
        Optional :class:`~praatao.sensors.praat_state.PraatStateProbe` (or an
        already captured state object).  When no state is passed to
        :meth:`advise` / :meth:`ask`, a snapshot is taken from this probe.
    llm:
        Optional LLM client.  ``None`` means "use the environment default",
        which is unavailable (offline) unless ``PRAATAO_LLM_*`` is set.
    lang:
        ``'zh'`` (default) or ``'en'``.
    """

    def __init__(
        self,
        kb: KnowledgeBase,
        state: "PraatStateProbe | PraatState | None" = None,
        llm: LlmClient | None = None,
        lang: str = LANG_ZH,
        *,
        use_probe: bool = True,
    ) -> None:
        self.kb = kb
        #: The last known state.  The application keeps this up to date;
        #: it is ``None`` until the first poll comes in.
        self.state = state if not _is_probe(state) else None
        #: The state probe (a deep probe sends a Praat script).
        self.state_probe = state if _is_probe(state) else None
        #: May the advisor ask the probe for a state on its own?  The
        #: hover path says no: a probe call would send a Praat script on
        #: the interface thread, which takes a moment and closes an open
        #: menu.
        self.use_probe = use_probe
        self.llm: LlmClient = llm if llm is not None else default_llm_client()
        self.lang = lang if lang in SUPPORTED_LANGS else LANG_ZH
        #: Hard limit for one LLM round-trip, in seconds.
        self.llm_timeout = 8.0
        #: A vision call carries a picture and needs more time than a chat
        #: turn: measured 3-20 s depending on the size of the picture.
        self.vision_timeout = 30.0
        #: Timeout used when taking a state snapshot from the probe.
        self.state_timeout = 3.0

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def advise(
        self,
        element: "Element | None",
        state: "PraatState | None" = None,
        *,
        on_llm: "Callable[[Advice], None] | None" = None,
        on_image: "Callable[[bytes], None] | None" = None,
    ) -> Advice:
        """Explain the control under the cursor.

        When the knowledge base does not cover the control, the model is
        asked for an explanation.  That call takes seconds, and a hover must
        never wait for it: the answer is returned immediately (without the
        model text) and the model answer is delivered later through
        ``on_llm``.  Pass ``on_llm=None`` to keep everything synchronous.

        ``on_image`` receives the bytes of a drawn teaching picture.  It is
        only used when the knowledge base has nothing to say, because
        drawing a picture is slow and expensive.
        """

        snapshot = self._resolve_state(state)
        raw_name = str(getattr(element, "name", "") or "")
        control_type = str(getattr(element, "control_type", "") or "") or None
        key = self._element_key(element)

        entry = self._lookup(key or raw_name, control_type)
        if entry is None:
            # A control inside a modal dialog (Praat's "Formant settings",
            # for instance) usually has no entry of its own.  The dialog
            # has one, and that is what the student actually wants to
            # know: "what is this dialog for".
            entry = self._lookup_dialog_entry(element)
        else:
            # A loose keyword hit on a field inside a dialog ("Formant
            # ceiling (Hz):" lands on the Formant *object*) explains the
            # wrong thing; the dialog's own entry explains the dialog.
            if self._only_keyword_hit(key or raw_name):
                dialog_entry = self._lookup_dialog_entry(element)
                if dialog_entry is not None:
                    entry = dialog_entry
        context = self._context_lines(element, snapshot)
        if entry is not None:
            return self._kb_advice(entry, element, key, context)

        related = self._related_entries(key or raw_name)
        if on_llm is not None and self._llm_ready():
            # The hover must not wait for the network: answer now, refine
            # later.
            self._ask_llm_later(
                element=element,
                state=snapshot,
                entries=related,
                raw_name=raw_name,
                control_type=control_type,
                context=context,
                on_llm=on_llm,
                on_image=on_image,
            )
            body = self._t("llm_pending")
            if related:
                body += "\n\n" + self._related_body(related)
            if context:
                body += "\n\n" + "\n".join(context)
            return Advice(
                headline=self._unknown_headline(key or raw_name),
                body=body,
                source=SOURCE_KB if related else SOURCE_KB,
                element_key=key,
                entries=list(related),
            )

        answer = self._ask_llm(
            question="",
            element=element,
            state=snapshot,
            entries=related,
            raw_name=raw_name,
            control_type=control_type,
        )
        if answer:
            body = answer + "\n\n" + self._t("llm_note")
            if related:
                body += "\n\n" + self._related_body(related)
            if context:
                body += "\n\n" + "\n".join(context)
            return Advice(
                headline=self._unknown_headline(key or raw_name),
                body=body,
                source=SOURCE_KB_LLM if related else SOURCE_LLM,
                element_key=key,
                entries=list(related),
            )

        body = self._t("unknown_body")
        if related:
            body += "\n\n" + self._related_body(related)
        if context:
            body += "\n\n" + "\n".join(context)
        return Advice(
            headline=self._unknown_headline(key or raw_name),
            body=body,
            source=SOURCE_KB,
            element_key=key,
            entries=list(related),
        )

    def advise_canvas(
        self,
        *,
        window_title: str = "",
        object_type: str = "",
        object_name: str = "",
        kind: str = "unknown",
        confidence: float = 0.0,
        image: Any = None,
        state: "PraatState | None" = None,
        on_llm: "Callable[[Advice], None] | None" = None,
    ) -> Advice:
        """Explain one of Praat's drawing areas.

        The knowledge base always has something to say about a canvas, and
        it does so without the picture leaving the machine.  When the user
        has switched the vision route on (``PRAATAO_VISION=1``) and a
        picture is available, the model is asked what it sees; that answer
        arrives later through ``on_llm``.
        """

        snapshot = self._resolve_state(state)
        entry = self._lookup(f"canvas-{kind}", None)
        if entry is None:
            entry = self._lookup("canvas-drawing-area", None)

        context: list[str] = []
        if object_name:
            who = f"{object_type} {object_name}".strip()
            context.append(self._t("canvas_object").format(name=who))
        elif window_title:
            context.append(self._t("canvas_window").format(name=window_title))
        if kind and kind != "unknown":
            context.append(self._t("canvas_guess").format(kind=kind))
        context.extend(self._context_lines(None, snapshot))

        if entry is not None:
            advice = self._kb_advice(entry, None, f"canvas-{kind}", context)
        else:
            advice = Advice(
                headline=self._t("canvas_title"),
                body="\n\n".join(context),
                source=SOURCE_KB,
                element_key="canvas-drawing-area",
            )

        if on_llm is not None and image is not None and self._vision_ready():
            self._ask_vision_later(
                image=image,
                kind=kind,
                object_name=object_name,
                state=snapshot,
                on_llm=on_llm,
            )
            advice = Advice(
                headline=advice.headline,
                body=advice.body + "\n\n" + self._t("vision_pending"),
                source=advice.source,
                element_key=advice.element_key,
                entries=advice.entries,
            )
        return advice

    def ask(
        self,
        question: str,
        element: "Element | None" = None,
        state: "PraatState | None" = None,
    ) -> Advice:

        snapshot = self._resolve_state(state)
        question = (question or "").strip()
        raw_name = str(getattr(element, "name", "") or "")
        control_type = str(getattr(element, "control_type", "") or "") or None
        key = self._element_key(element)

        matches = self._search(question, limit=5)
        if not matches and key:
            matches = self._search(key, limit=5)

        answer = self._ask_llm(
            question=question,
            element=element,
            state=snapshot,
            entries=matches,
            raw_name=raw_name,
            control_type=control_type,
        )

        headline = self._t("ask_headline").format(question=question or key or "")
        if matches:
            kb_body = self._matches_body(matches)
        else:
            kb_body = self._t("ask_no_match")

        if answer:
            body = answer
            if matches:
                body += "\n\n" + kb_body
            source = SOURCE_KB_LLM if matches else SOURCE_LLM
        else:
            body = kb_body
            source = SOURCE_KB

        return Advice(
            headline=headline,
            body=body,
            source=source,
            element_key=key,
            entries=list(matches),
        )

    def status(self) -> str:
        """One-line human-readable status of the tutor."""

        try:
            count = len(self.kb.entries())
        except Exception:  # noqa: BLE001 - a broken KB must not break the UI
            count = 0
        if self._llm_available():
            llm_text = self._t("llm_on")
            config = getattr(self.llm, "config", None)
            model = str(getattr(config, "model", "") or "")
            backend = str(getattr(config, "backend", "") or "")
            if model:
                llm_text = f"{llm_text} ({backend} · {model})" if backend else (
                    f"{llm_text} ({model})"
                )
        else:
            llm_text = self._t("llm_off")
        return self._t("status").format(
            n=count,
            llm=llm_text,
            lang=self._t("status_lang"),
        )

    # ------------------------------------------------------------------
    # knowledge base access
    # ------------------------------------------------------------------
    def _lookup(
        self, name: str, control_type: str | None
    ) -> KnowledgeEntry | None:
        if not name:
            return None
        try:
            entry = self.kb.lookup(name, control_type)
        except TypeError:
            try:
                entry = self.kb.lookup(name)
            except Exception:  # noqa: BLE001
                return None
        except Exception:  # noqa: BLE001
            return None
        return entry

    def _only_keyword_hit(self, name: str) -> bool:
        """Did the lookup fall back on a keyword instead of a real alias?"""

        if not name:
            return False
        try:
            return self.kb.exact_match(name) is None
        except Exception:  # noqa: BLE001
            return False

    def _lookup_dialog_entry(self, element: "Element | None") -> KnowledgeEntry | None:
        """The knowledge entry of the dialog the control lives in.

        Only the modal dialogs count.  The Objects window and the editors
        have titles that say nothing about the control under the cursor
        ("Praat Objects", "1. Sound demo_vowel"), and using those would
        explain the wrong thing.
        """

        if element is None:
            return None
        title = str(getattr(element, "window_title", "") or "").strip()
        if not title:
            return None
        if title.casefold() in ("praat objects", "praat picture", "praat"):
            return None
        # A Praat window whose title is not an object name: a dialog.
        if title.casefold().startswith("praat "):
            return None
        # Praat's dialogs are named after the menu item that opened them,
        # and the menu item carries the ellipsis: "Formant settings..."
        # opens the "Formant settings" dialog.
        for candidate in (title + "...", title):
            try:
                entry = self.kb.lookup(candidate)
            except Exception:  # noqa: BLE001
                entry = None
            if entry is not None:
                return entry
        return None

    def _search(self, query: str, limit: int = 5) -> list[KnowledgeEntry]:
        query = (query or "").strip()
        if not query:
            return []
        try:
            found = self.kb.search(query, limit)
        except TypeError:
            try:
                found = self.kb.search(query)
            except Exception:  # noqa: BLE001
                return []
        except Exception:  # noqa: BLE001
            return []
        return list(found or [])

    def _related_entries(self, name: str, limit: int = 3) -> list[KnowledgeEntry]:
        """Entries that really relate to a control name (not search noise)."""

        key = _match_key(name)
        if not key:
            return []
        hits = self._search(name, limit=limit * 3)
        related = [entry for entry in hits if _is_related(entry, key)]
        return related[:limit]

    # ------------------------------------------------------------------
    # rendering
    # ------------------------------------------------------------------
    def _kb_advice(
        self,
        entry: KnowledgeEntry,
        element: "Element | None",
        key: str | None,
        context: Sequence[str],
    ) -> Advice:
        title = self._entry_field(entry, "title") or key or ""
        body_parts: list[str] = []

        what = self._entry_field(entry, "what")
        if what:
            body_parts.append(f"{self._t('section_what')}：{what}" if self.lang == LANG_ZH
                             else f"{self._t('section_what')}: {what}")
        how = self._entry_field(entry, "how")
        if how:
            body_parts.append(f"{self._t('section_how')}：{how}" if self.lang == LANG_ZH
                             else f"{self._t('section_how')}: {how}")
        concept = self._entry_field(entry, "concept")
        if concept:
            body_parts.append(f"{self._t('section_concept')}：{concept}" if self.lang == LANG_ZH
                             else f"{self._t('section_concept')}: {concept}")
        pitfalls = self._entry_pitfalls(entry)
        if pitfalls:
            label = self._t("section_pitfalls")
            bullet = "\n".join(f"• {p}" for p in pitfalls)
            body_parts.append(f"{label}：\n{bullet}" if self.lang == LANG_ZH
                             else f"{label}:\n{bullet}")

        context_block = list(context)
        if context_block:
            body_parts.append("\n".join(context_block))

        return Advice(
            headline=title,
            body="\n\n".join(part for part in body_parts if part),
            source=SOURCE_KB,
            element_key=key,
            entries=[entry],
        )

    def _matches_body(self, matches: Sequence[KnowledgeEntry]) -> str:
        lines = [self._t("ask_matches")]
        for entry in matches:
            title = self._entry_field(entry, "title") or _entry_id(entry)
            what = self._entry_field(entry, "what")
            text = f"• {title}"
            if what:
                text += f"：{what}" if self.lang == LANG_ZH else f": {what}"
            lines.append(text)
        return "\n".join(lines)

    def _related_body(self, related: Sequence[KnowledgeEntry]) -> str:
        lines = [self._t("unknown_related")]
        for entry in related:
            title = self._entry_field(entry, "title") or _entry_id(entry)
            what = self._entry_field(entry, "what")
            text = f"• {title}"
            if what:
                text += f"：{what}" if self.lang == LANG_ZH else f": {what}"
            lines.append(text)
        return "\n".join(lines)

    def _unknown_headline(self, raw_name: str) -> str:
        base = self._t("unknown_headline")
        if not raw_name:
            return base
        if self.lang == LANG_ZH:
            return f"{base}「{raw_name}」"
        return f"{base}: {raw_name}"

    # ------------------------------------------------------------------
    # context-aware advice
    # ------------------------------------------------------------------
    def _context_lines(
        self,
        element: "Element | None",
        state: "PraatState | None",
    ) -> list[str]:
        """Facts about the current Praat state, never invented."""

        if state is None:
            return []

        lines: list[str] = []
        objects = list(getattr(state, "objects", None) or [])
        selected = list(getattr(state, "selected", None) or [])

        sounds = [o for o in objects if _obj_type(o).lower() == "sound"]
        textgrids = [o for o in objects if _obj_type(o).lower() == "textgrid"]
        selected_sounds = [o for o in selected if _obj_type(o).lower() == "sound"]

        # 1) the selected Sound, with whatever details the state really has.
        raw_name = str(getattr(element, "name", "") or "")
        key = _match_key(raw_name)
        is_view_edit = _is_view_edit(key)

        if selected_sounds:
            line = self._sound_line(selected_sounds[0], state)
            if is_view_edit:
                hint = self._t("open_editor_hint")
                line = f"{line}，{hint}" if self.lang == LANG_ZH else f"{line} - {hint}"
            lines.append(line)
        elif selected:
            items = self._t("list_sep").join(
                f"{_obj_type(o)} {_obj_name(o)}".strip() for o in selected
            )
            lines.append(self._t("selected_other").format(items=items))

        # 2) the editor that is already open.
        editor_open = bool(getattr(state, "editor_open", False))
        editor_object = getattr(state, "editor_object", None)
        if editor_open and editor_object and self._in_objects_window(element):
            lines.append(self._t("editor_open").format(name=editor_object))

        # 3) control specific guidance.
        if is_view_edit and not selected_sounds:
            if selected:
                first = selected[0]
                lines.append(
                    self._t("view_edit_object").format(
                        type=_obj_type(first), name=_obj_name(first)
                    )
                )
            else:
                lines.append(self._t("no_selection"))

        if _matches_any(key, _TEXTGRID_FROM_SOUND):
            if not textgrids:
                lines.append(self._t("need_textgrid_first"))
            else:
                names = self._t("list_sep").join(_obj_name(t) for t in textgrids)
                lines.append(self._t("textgrid_exists").format(names=names))

        required = _required_type(key)
        if required and not _matches_any(key, _TEXTGRID_FROM_SOUND):
            existing = [o for o in objects if _obj_type(o).lower() == required.lower()]
            if not existing:
                lines.append(self._t("missing_object").format(type=required))
            else:
                chosen = [o for o in selected if _obj_type(o).lower() == required.lower()]
                if not chosen:
                    lines.append(
                        self._t("not_selected").format(
                            type=required, name=_obj_name(existing[0])
                        )
                    )

        return lines

    def _sound_line(self, obj: Any, state: "PraatState | None") -> str:
        name = _obj_name(obj)
        text = self._t("selected_sound").format(name=name)
        duration = _obj_detail(obj, state, _DURATION_KEYS)
        rate = _obj_detail(obj, state, _RATE_KEYS)
        channels = _obj_detail(obj, state, _CHANNEL_KEYS)
        details: list[str] = []
        if duration is not None:
            details.append(self._t("detail_duration").format(value=_fmt_number(duration)))
        if rate is not None:
            details.append(self._t("detail_rate").format(value=_fmt_number(rate)))
        if channels is not None:
            details.append(self._t("detail_channels").format(value=_fmt_number(channels)))
        if not details:
            return text
        separator = "，" if self.lang == LANG_ZH else ", "
        return f"{text}（{separator.join(details)}）" if self.lang == LANG_ZH else (
            f"{text} ({separator.join(details)})"
        )

    def _in_objects_window(self, element: "Element | None") -> bool:
        title = str(getattr(element, "window_title", "") or "").lower()
        return "object" in title

    # ------------------------------------------------------------------
    # LLM
    # ------------------------------------------------------------------
    def _llm_available(self) -> bool:
        try:
            return bool(self.llm.available())
        except Exception:  # noqa: BLE001
            return False

    def _llm_ready(self) -> bool:
        """Is a model available *and* worth calling for a hover?"""

        return self._llm_available()

    def _vision_ready(self) -> bool:
        """May an image be sent to the model?

        The user has to say so (``PRAATAO_VISION=1``): a Praat picture can
        show a participant's voice.
        """

        try:
            return bool(self.llm.supports_vision())
        except Exception:  # noqa: BLE001
            return False

    def _ask_vision_later(
        self,
        *,
        image: Any,
        kind: str,
        object_name: str,
        state: "PraatState | None",
        on_llm: "Callable[[Advice], None]",
    ) -> None:
        """Ask a vision model about a canvas, on a worker thread."""

        def worker() -> None:
            try:
                answer = self._ask_vision(image, kind, object_name, state)
                if not answer:
                    return
                on_llm(Advice(
                    headline=self._t("canvas_title"),
                    body=answer + "\n\n" + self._t("vision_note"),
                    source=SOURCE_LLM,
                    element_key="canvas-drawing-area",
                ))
            except Exception:  # noqa: BLE001 - the model is strictly optional
                return

        try:
            thread = threading.Thread(target=worker, name="praatao-vision", daemon=True)
            thread.start()
        except Exception:  # noqa: BLE001
            return

    def _ask_vision(
        self,
        image: Any,
        kind: str,
        object_name: str,
        state: "PraatState | None",
    ) -> str | None:
        """Ask the model what it sees in a Praat drawing area."""

        if not self._vision_ready():
            return None
        from .llm import ImageInput  # local import keeps the module import-light

        payload = image
        if isinstance(image, (bytes, bytearray)):
            payload = ImageInput(data=bytes(image), mime="image/png")
        elif isinstance(image, str):
            payload = ImageInput.from_path(image)
        elif hasattr(image, "save"):
            import io

            buffer = io.BytesIO()
            try:
                image.save(buffer, format="PNG")
            except Exception:
                return None
            payload = ImageInput(data=buffer.getvalue(), mime="image/png")

        subject = object_name or "the sound"
        if self.lang == LANG_ZH:
            system = (
                "你是 Praatao，一个教用户使用 Praat（语音学软件）的助教。"
                "你看到的是 Praat 某个绘图区的截图。"
                "只根据图里真实可见的内容回答，不要编造数字。"
                "回答用中文，不超过 120 字，分三句：这是什么图；学生现在最可能卡在哪里；下一步具体做什么。"
            )
            user = f"这是 {subject} 的绘图区截图（本地判断的类型：{kind}）。请说明。"
        else:
            system = (
                "You are Praatao, a tutor for Praat. The image is a screenshot of "
                "one of Praat's drawing areas. Answer only from what is visible; "
                "never invent numbers. Use English, at most 120 words, in three "
                "sentences: what the picture is, where the student is probably "
                "stuck, and what to do next."
            )
            user = f"Here is the drawing area of {subject} (local guess: {kind})."
        try:
            try:
                answer = self.llm.chat_with_image(system, user, [payload],
                                                  timeout=self.vision_timeout)
            except TypeError:
                answer = self.llm.chat_with_image(system, user, [payload])
        except Exception:  # noqa: BLE001 - the model is strictly optional
            return None
        if isinstance(answer, str) and answer.strip():
            return answer.strip()
        return None

    def _ask_llm_later(
        self,
        *,
        element: "Element | None",
        state: "PraatState | None",
        entries: Sequence[KnowledgeEntry],
        raw_name: str,
        control_type: str | None,
        context: Sequence[str],
        on_llm: "Callable[[Advice], None]",
        on_image: "Callable[[bytes], None] | None" = None,
    ) -> None:
        """Ask the model on a worker thread and hand the answer back.

        The hover loop must stay responsive, so the model call happens in the
        background and the refined advice is pushed through ``on_llm`` when
        it arrives.  Nothing here can raise.
        """

        def worker() -> None:
            try:
                answer = self._ask_llm(
                    question="",
                    element=element,
                    state=state,
                    entries=entries,
                    raw_name=raw_name,
                    control_type=control_type,
                )
                if not answer:
                    return
                body = answer + "\n\n" + self._t("llm_note")
                if entries:
                    body += "\n\n" + self._related_body(entries)
                if context:
                    body += "\n\n" + "\n".join(context)
                headline = self._unknown_headline(self._element_key(element) or raw_name)
                advice = Advice(
                    headline=headline,
                    body=body,
                    source=SOURCE_KB_LLM if entries else SOURCE_LLM,
                    element_key=self._element_key(element),
                    entries=list(entries),
                )
                on_llm(advice)
                if on_image is not None:
                    self._ask_image_later(
                        headline=headline, answer=answer, on_image=on_image
                    )
            except Exception:  # noqa: BLE001 - the model is strictly optional
                return

        try:
            thread = threading.Thread(target=worker, name="praatao-llm", daemon=True)
            thread.start()
        except Exception:  # noqa: BLE001 - no threads, no model answer
            return

    def _ask_image_later(
        self,
        *,
        headline: str,
        answer: str,
        on_image: "Callable[[bytes], None]",
    ) -> None:
        """Draw a teaching picture in the background.

        The prompt is built from the text answer only: no picture of the
        participant's voice ever reaches the image model.  The style is
        deliberately free of words, because a drawn letter is never a
        readable letter.
        """

        def worker() -> None:
            try:
                picture = self._generate_teaching_image(headline, answer)
            except Exception:  # noqa: BLE001
                return
            if picture:
                try:
                    on_image(picture)
                except Exception:  # noqa: BLE001
                    return

        try:
            thread = threading.Thread(
                target=worker, name="praatao-imagegen", daemon=True
            )
            thread.start()
        except Exception:  # noqa: BLE001
            return

    def _generate_teaching_image(self, headline: str, answer: str) -> bytes | None:
        """Ask the image model for an illustration of the answer."""

        client = self.llm
        if client is None or not client.supports_image_generation():
            return None
        topic = headline.strip()
        summary = " ".join(answer.strip().split())[:400]
        # The image model likes to write the topic into the picture.  The
        # instruction therefore comes last, twice, and the context is
        # described rather than quoted.
        prompt = (
            "A flat vector educational illustration of this topic: "
            f"{topic}. Context: {summary}. "
            "Minimal, clean, textbook illustration style, soft colours, "
            "a plain background, simple shapes.\n"
            "IMPORTANT: the picture must contain no writing at all - "
            "no text, no letters, no numbers, no captions, no labels, "
            "no title, no watermark. Show the idea with pictures only."
        )
        try:
            return client.generate_image(prompt)
        except Exception:  # noqa: BLE001
            return None

    def _ask_llm(
        self,
        question: str,
        element: "Element | None",
        state: "PraatState | None",
        entries: Sequence[KnowledgeEntry],
        raw_name: str,
        control_type: str | None,
    ) -> str | None:
        """Ask the LLM, grounded with the KB and the live state."""

        if not self._llm_available():
            return None
        system = self._system_prompt()
        user = self._user_prompt(question, element, state, entries, raw_name, control_type)
        try:
            try:
                answer = self.llm.chat(system, user, timeout=self.llm_timeout)
            except TypeError:
                answer = self.llm.chat(system, user)
        except Exception:  # noqa: BLE001 - the LLM is strictly optional
            return None
        if isinstance(answer, str) and answer.strip():
            return answer.strip()
        return None

    def _system_prompt(self) -> str:
        if self.lang == LANG_ZH:
            return (
                "你是 Praatao，一个教用户使用 Praat（语音学软件）的助教。"
                "只依据给出的上下文回答，不要编造数字、菜单路径或对象名称。"
                "回答保持简短（不超过 120 字），不确定时明确说明。"
                "请用中文回答。"
            )
        return (
            "You are Praatao, a tutor that teaches Praat (phonetics software). "
            "Answer only from the given context; never invent numbers, menu paths "
            "or object names. Keep it short (max ~120 words) and say so when you "
            "are unsure. Answer in English."
        )

    def _user_prompt(
        self,
        question: str,
        element: "Element | None",
        state: "PraatState | None",
        entries: Sequence[KnowledgeEntry],
        raw_name: str,
        control_type: str | None,
    ) -> str:
        parts: list[str] = []
        if question:
            parts.append(f"Question: {question}")
        else:
            parts.append("Question: what does this control do in Praat?")
        parts.append(f"Control raw name: {raw_name or '(none)'}")
        parts.append(f"Control type: {control_type or '(unknown)'}")
        window_title = getattr(element, "window_title", "") if element else ""
        if window_title:
            parts.append(f"Window the control is in: {window_title}")
        summary = self._state_summary(state)
        if summary:
            parts.append(f"Praat state: {summary}")
        context = self._kb_context(entries)
        if context:
            parts.append("Knowledge base excerpts:\n" + context)
        parts.append(
            "Use the context above: say what this control means for the objects "
            "that are selected right now, not only what the button is called. "
            "If the context is not enough, say what is missing."
        )
        if self.lang == LANG_ZH:
            parts.append("请用中文回答，并说明你是否确定。")
        else:
            parts.append("Answer in English and say whether you are certain.")
        return "\n".join(parts)

    def _kb_context(self, entries: Sequence[KnowledgeEntry], limit: int = 3) -> str:
        lines: list[str] = []
        for entry in list(entries)[:limit]:
            title = self._entry_field(entry, "title") or _entry_id(entry)
            what = self._entry_field(entry, "what") or ""
            how = self._entry_field(entry, "how") or ""
            lines.append(f"- {title}: {what} {how}".strip())
        return "\n".join(lines)

    def _state_summary(self, state: "PraatState | None") -> str:
        if state is None:
            return ""
        parts: list[str] = []
        running = getattr(state, "running", None)
        if running is not None:
            parts.append(f"running={bool(running)}")
        objects = list(getattr(state, "objects", None) or [])
        if objects:
            parts.append(
                "objects: "
                + ", ".join(f"{_obj_type(o)} {_obj_name(o)}".strip() for o in objects)
            )
        selected = list(getattr(state, "selected", None) or [])
        if selected:
            parts.append(
                "selected: "
                + ", ".join(f"{_obj_type(o)} {_obj_name(o)}".strip() for o in selected)
            )
        if getattr(state, "editor_open", False):
            editor_object = getattr(state, "editor_object", None)
            parts.append(
                f"editor open: {editor_object}" if editor_object else "editor open: yes"
            )
        tiers = list(getattr(state, "textgrid_tiers", None) or [])
        if tiers:
            parts.append("tiers: " + ", ".join(str(t) for t in tiers))
        # The acoustic details of the selection (duration, sampling rate,
        # channels).  Without them the model can only talk about the label
        # of the control, which is not what the student asked for.
        attributes = dict((getattr(state, "raw", None) or {}).get("attributes") or {})
        if attributes:
            parts.append(
                "selected object details: "
                + ", ".join(f"{key}={value}" for key, value in attributes.items())
            )
        error = getattr(state, "error", None)
        if error:
            parts.append(f"error: {error}")
        return "; ".join(parts)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _resolve_state(self, state: "PraatState | None") -> "PraatState | None":
        """The state the advice is built on.

        The probe is only asked when the caller allows it.  A probe call
        sends a Praat script, which takes a moment and closes whatever
        menu the user has open, so the hover path (which runs on the
        interface thread, twenty times a second) must never trigger one.
        """

        if state is not None:
            return state
        if self.state is not None:
            return self.state
        if not self.use_probe:
            return None
        probe = self.state_probe
        if probe is None:
            return None
        snapshot = getattr(probe, "snapshot", None)
        if callable(snapshot):
            try:
                try:
                    return snapshot(timeout=self.state_timeout)
                except TypeError:
                    return snapshot()
            except Exception:  # noqa: BLE001 - never break the hover path
                return None
        return probe

    def _element_key(self, element: "Element | None") -> str | None:
        if element is None:
            return None
        raw = str(getattr(element, "name", "") or "")
        if not raw:
            return None
        key = _normalize(raw)
        return key or None

    def _entry_field(self, entry: KnowledgeEntry, base: str) -> str | None:
        """Read ``<base>_<lang>`` with a fallback to the other language."""

        other = LANG_EN if self.lang == LANG_ZH else LANG_ZH
        for name in (f"{base}_{self.lang}", f"{base}_{other}"):
            value = getattr(entry, name, None)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _entry_pitfalls(self, entry: KnowledgeEntry) -> list[str]:
        """Read the pitfalls of an entry in the requested language."""

        other = LANG_EN if self.lang == LANG_ZH else LANG_ZH
        raw = getattr(entry, "pitfalls", None)
        if not raw:
            return []
        if isinstance(raw, dict):
            for name in (self.lang, other):
                value = raw.get(name)
                if isinstance(value, list) and value:
                    return [str(v).strip() for v in value if str(v).strip()]
            return []
        if isinstance(raw, str):
            return [raw.strip()] if raw.strip() else []
        if isinstance(raw, (list, tuple)):
            out: list[str] = []
            for item in raw:
                if isinstance(item, str):
                    text = item.strip()
                elif isinstance(item, dict):
                    text = ""
                    for name in (self.lang, other):
                        value = item.get(name)
                        if isinstance(value, str) and value.strip():
                            text = value.strip()
                            break
                else:
                    text = str(item).strip()
                if text:
                    out.append(text)
            return out
        return []

    def _t(self, key: str) -> str:
        table = _STRINGS.get(self.lang, _STRINGS[LANG_ZH])
        return table.get(key, _STRINGS[LANG_ZH].get(key, key))


# ----------------------------------------------------------------------
# module level helpers
# ----------------------------------------------------------------------
_DURATION_KEYS = ("duration", "duration_s", "duration_seconds", "total_duration")
_RATE_KEYS = (
    "sampling_frequency",
    "sampling_rate",
    "sample_rate",
    "samplerate",
    "fs",
)
_CHANNEL_KEYS = ("n_channels", "num_channels", "channels", "number_of_channels")


def _is_probe(obj: object) -> bool:
    """Is this object a state probe (and not a state)?

    A probe knows how to take a snapshot, a state does not.
    """

    return obj is not None and callable(getattr(obj, "snapshot", None))


def _normalize(raw: str) -> str:
    """Normalize a raw UIA name (uses ``sensors.uia`` when it is importable)."""

    try:
        from ..sensors.uia import normalize_name  # noqa: PLC0415

        value = normalize_name(raw)
        if isinstance(value, str) and value.strip():
            return value.strip()
    except Exception:  # noqa: BLE001 - sibling module may not exist yet
        pass
    return _local_normalize(raw)


def _local_normalize(raw: str) -> str:
    """Fallback implementation of the documented name normalization."""

    text = raw.replace("\u202f", " ").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s*>+\s*$", "", text).strip()
    text = re.sub(r"\t.*$", "", text).strip()
    text = re.sub(r":\s*$", "", text).strip()
    text = re.sub(r"^\d+\.\s*", "", text).strip()
    return text


def _match_key(raw_name: str) -> str:
    """Lower-cased, punctuation-free key used for the rule tables."""

    key = _normalize(raw_name).lower()
    key = key.replace("&", "and")
    key = key.strip(" .")
    return key


def _matches_any(key: str, needles: Iterable[str]) -> bool:
    for needle in needles:
        if key.startswith(needle) or key == needle:
            return True
    return False


def _is_view_edit(key: str) -> bool:
    return "view and edit" in key or "view & edit" in key


def _required_type(key: str) -> str | None:
    """Object type a dynamic action button needs, if it is a known one."""

    for needle, obj_type in _DYNAMIC_REQUIREMENTS.items():
        if key.startswith(needle):
            return obj_type
    return None


def _is_related(entry: KnowledgeEntry, key: str) -> bool:
    """True when an entry shares an alias / keyword with a control name."""

    tokens: list[str] = []
    tokens.extend(str(t) for t in (getattr(entry, "keywords", None) or []))
    tokens.extend(str(t) for t in (getattr(entry, "aliases", None) or []))
    tokens.append(str(getattr(entry, "id", "") or ""))
    for token in tokens:
        normalized = _match_key(token)
        if len(normalized) < 3:
            continue
        if normalized in key or key in normalized:
            return True
    return False


def _obj_type(obj: Any) -> str:
    if isinstance(obj, dict):
        return str(obj.get("type") or "")
    return str(getattr(obj, "type", "") or "")


def _obj_name(obj: Any) -> str:
    if isinstance(obj, dict):
        return str(obj.get("name") or "")
    return str(getattr(obj, "name", "") or "")


def _obj_id(obj: Any) -> Any:
    if isinstance(obj, dict):
        return obj.get("id")
    return getattr(obj, "id", None)


def _entry_id(entry: KnowledgeEntry) -> str:
    return str(getattr(entry, "id", "") or "")


def _raw_objects(state: "PraatState | None") -> list[dict]:
    raw = getattr(state, "raw", None)
    if isinstance(raw, dict):
        for key in ("objects", "praat_objects", "objectlist"):
            value = raw.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return []
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    return []


def _obj_detail(obj: Any, state: "PraatState | None", keys: Sequence[str]) -> Any:
    """Look a detail (duration, sampling rate, ...) up on the object or in ``raw``."""

    for key in keys:
        value = getattr(obj, key, None)
        if value is not None and value != "":
            return value
    obj_id = _obj_id(obj)
    obj_name = _obj_name(obj)
    for record in _raw_objects(state):
        same_id = obj_id is not None and record.get("id") == obj_id
        same_name = bool(obj_name) and record.get("name") == obj_name
        if same_id or same_name:
            for key in keys:
                value = record.get(key)
                if value is not None and value != "":
                    return value
    return None


def _fmt_number(value: Any) -> str:
    """Format a numeric detail without inventing precision."""

    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value == int(value):
            return str(int(value))
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)
