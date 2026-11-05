"""The hover card: a small explainer that follows the cursor.

This is the Tk version of the card that ``praatao/ui/qt/hover.py`` draws
with Qt.  The two are kept in step on purpose: the same colours, the same
type sizes, the same order (title, now, what, how, concept, traps, footer)
and the same parsing of the tutor's plain text.

Behaviour
---------
* Appears when the cursor rests on a Praat control that the knowledge base
  knows about.
* Never steals focus from Praat, never blocks Praat's mouse input.
* Clicking the card pins it open so the user can read it and copy text;
  clicking again unpins it.
"""

from __future__ import annotations

import math
import tkinter as tk
from dataclasses import dataclass, field
from tkinter import font as tkfont

from .overlay import clamp_rect, keep_on_top, set_click_through, set_no_activate

# --------------------------------------------------------------------------
# One visual language, shared with the Qt card, the side panel and the
# settings window.
# --------------------------------------------------------------------------
BG = "#FFFFFF"
FG = "#1F2933"
MUTED = "#6B7A89"
ACCENT = "#B4530A"
SOFT = "#FDF6EC"
BORDER = "#E3D9C6"
WARN_BG = "#FFF4E5"
WARN_FG = "#8A3B12"

# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------
MAX_CARD_W = 400
CARD_PAD = 14
MAX_CARD_H = 520
MIN_CHARS = 16
MAX_CHARS = 52
MAX_LINES = 40

#: The size of the pin and the close button.
BUTTON_SIZE = 24

#: The label in front of the "now" band, per language.
NOW_LABEL = {"zh": "现在", "en": "Now"}

#: The section labels the tutor uses, per language.
SECTION_LABELS = {
    "zh": ("这是什么", "怎么用", "概念", "常见坑"),
    "en": ("What it is", "How to use it", "Concept", "Common pitfalls"),
}
#: The order the card shows the sections in, whatever order they arrive in.
SECTION_KEYS = ("what", "how", "concept", "pitfalls")

#: What the footer says, per language and per kind of source.
FOOTER_TEXT = {
    "zh": {
        "kb": "本地知识库",
        "llm": "大模型回答 · 模型回答可能较慢，请稍候",
        "kb+llm": "知识库 + 大模型 · 模型那部分可能较慢",
    },
    "en": {
        "kb": "Knowledge base",
        "llm": "Model answer · a model answer can take a while",
        "kb+llm": "Knowledge base + model · the model part can take a while",
    },
}


@dataclass
class Section:
    """One part of the explanation."""

    key: str
    label: str = ""
    text: str = ""
    items: list[str] = field(default_factory=list)


@dataclass
class Body:
    """The advice, split into the parts the card shows."""

    notices: list[str] = field(default_factory=list)
    context: list[str] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)
    prose: list[str] = field(default_factory=list)

    @property
    def known(self) -> list[Section]:
        """The four sections that make up a normal explanation.

        They always come in the order the card shows them in, whatever
        order the body had them in.
        """

        sections = [s for s in self.sections if s.key in SECTION_KEYS]
        sections.sort(key=lambda s: SECTION_KEYS.index(s.key))
        return sections

    @property
    def lists(self) -> list[Section]:
        """Extra lists, such as the related entries the knowledge base found."""

        return [s for s in self.sections if s.key == "list"]


def _blocks(body: str) -> list[str]:
    """The paragraphs of a body, separated by a blank line."""

    text = (body or "").replace("\r\n", "\n").replace("\r", "\n")
    return [block.strip() for block in text.split("\n\n") if block.strip()]


def _split_label(line: str, lang: str) -> tuple[str, str]:
    """Is this line the start of a section?  Returns (key, the rest)."""

    labels = SECTION_LABELS.get(lang, SECTION_LABELS["zh"])
    for key, candidate in zip(SECTION_KEYS, labels):
        for sep in ("：", ":"):
            if line.startswith(candidate + sep):
                return key, line[len(candidate) + len(sep):].strip()
    return "", line


def _is_notice(text: str) -> bool:
    """A notice is a whole sentence in brackets: the tutor talking to the user."""

    stripped = text.strip()
    if len(stripped) < 4:
        return False
    return (stripped.startswith("（") and stripped.endswith("）")) or (
        stripped.startswith("(") and stripped.endswith(")")
    )


def parse_body(body: str, lang: str = "zh") -> Body:
    """Split the tutor's plain text into the parts the card shows.

    The body is a sequence of blocks separated by a blank line.  A block
    that starts with a known section label is a section; a block of
    bullets is a list; a block in brackets is a notice; anything else is
    prose.  When the body has the four sections, the remaining prose is
    about the state of Praat right now, and becomes the "now" band.
    """

    parsed = Body()
    paragraphs: list[str] = []

    for block in _blocks(body):
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue

        key, rest = _split_label(lines[0], lang)
        if key:
            items: list[str] = []
            extra: list[str] = []
            for line in lines[1:]:
                if line.startswith("•"):
                    items.append(line.lstrip("•").strip())
                else:
                    extra.append(line)
            text = " ".join(part for part in [rest, *extra] if part)
            labels = SECTION_LABELS.get(lang, SECTION_LABELS["zh"])
            label = labels[SECTION_KEYS.index(key)]
            parsed.sections.append(
                Section(key=key, label=label, text=text, items=items)
            )
            continue

        bullets = [line.lstrip("•").strip() for line in lines if line.startswith("•")]
        if bullets:
            label = "" if lines[0].startswith("•") else lines[0].rstrip("：: ").strip()
            parsed.sections.append(Section(key="list", label=label, items=bullets))
            continue

        text = " ".join(lines)
        if _is_notice(text):
            parsed.notices.append(text)
        else:
            paragraphs.append(text)

    if parsed.known:
        # The leftovers are about the state of Praat right now.
        parsed.context = paragraphs
    else:
        parsed.prose = paragraphs
    return parsed


def source_kind(source: str) -> str:
    """Which kind of source is this?

    ``kb``, ``llm`` or ``kb+llm``.  An empty string means: the source is
    not one of the three the card knows, and the card shows it as it is.
    """

    text = (source or "").lower()
    has_model = (
        "ai" in text or "llm" in text or "模型" in text or "model" in text
    )
    has_kb = "知识库" in text or "knowledge base" in text
    if has_model and has_kb:
        return "kb+llm"
    if has_model:
        return "llm"
    if has_kb:
        return "kb"
    return ""


def footer_text(source: str, lang: str = "zh") -> str:
    """What the footer says about where the answer came from."""

    if not source:
        return ""
    kind = source_kind(source)
    if not kind:
        return source
    table = FOOTER_TEXT.get(lang, FOOTER_TEXT["zh"])
    return "● " + table.get(kind, source)


SOURCE_LABELS = {
    "kb": "离线知识库 / offline knowledge base",
    "llm": "AI 生成 / AI generated - may be imperfect",
    "kb+llm": "离线知识库 + AI / knowledge base + AI",
}


def source_label(source: str) -> str:
    """Human-readable label for where an answer came from."""
    return SOURCE_LABELS.get(source, source or "")


class HoverCard:
    """A click-through card that explains one UI element."""

    def __init__(self, master: tk.Tk, lang: str = "zh") -> None:
        self.master = master
        self.lang = lang
        self.pinned = False
        #: Set by the application: called when the user clicks the card.
        self.on_click = None
        self._signature: tuple[str, str] | None = None
        self._width = 320
        self._height = 120
        self._font = tkfont.Font(family="Microsoft YaHei UI", size=9)
        self._title_font = tkfont.Font(family="Microsoft YaHei UI", size=10,
                                       weight="bold")
        self._label_font = tkfont.Font(family="Microsoft YaHei UI", size=9,
                                       weight="bold")

        self.win = tk.Toplevel(master)
        self.win.withdraw()
        self.win.overrideredirect(True)
        self.win.configure(bg=BORDER)
        self.win.attributes("-topmost", True)

        self.inner = tk.Frame(self.win, bg=BG, bd=0)
        self.inner.pack(fill="both", expand=True, padx=1, pady=1)

        self.title_label = tk.Label(
            self.inner, text="", bg=BG, fg=ACCENT, anchor="w",
            justify="left", font=self._title_font,
        )
        self.title_label.pack(fill="x", padx=CARD_PAD, pady=(CARD_PAD, 6))

        self.rule = tk.Frame(self.inner, bg=BORDER, height=1)
        self.rule.pack(fill="x", padx=CARD_PAD)

        # The "now" band: what the control means at this moment.
        self.now_box = tk.Frame(self.inner, bg=SOFT)
        self.now_marker = tk.Label(
            self.now_box, text="", bg=SOFT, fg=ACCENT, anchor="w",
            font=self._label_font,
        )
        self.now_marker.pack(side="left", padx=(8, 0), pady=6)
        self.now_label = tk.Label(
            self.now_box, text="", bg=SOFT, fg=FG, anchor="w",
            justify="left", font=self._font, wraplength=MAX_CARD_W - 2 * CARD_PAD,
        )
        self.now_label.pack(side="left", fill="both", expand=True,
                            padx=(6, 8), pady=6)

        self.body = tk.Text(
            self.inner, bg=BG, fg=FG, relief="flat", borderwidth=0,
            wrap="word", height=1, width=1, cursor="arrow",
            font=self._font,
            padx=CARD_PAD, pady=0, spacing1=0, spacing3=4,
        )
        self.body.tag_configure("label", font=self._label_font, foreground=FG)
        self.body.tag_configure("body", foreground=FG)
        self.body.tag_configure("pitfall", foreground=FG)
        self.body.tag_configure("warn", foreground=WARN_FG)
        self.body.tag_configure("muted", foreground=MUTED)
        self.body.tag_configure("accent", foreground=ACCENT)
        self.body.tag_configure("src", foreground=MUTED,
                                font=tkfont.Font(family="Microsoft YaHei UI", size=8))
        self.body.configure(state="disabled")
        self.body.pack(fill="both", expand=True, padx=0, pady=(8, 0))

        self.source_label = tk.Label(
            self.inner, text="", bg=BG, fg=MUTED, anchor="w",
            font=tkfont.Font(family="Microsoft YaHei UI", size=8),
        )

        self.win.bind("<Button-1>", self._on_click)
        self.inner.bind("<Button-1>", self._on_click)

        keep_on_top(self.win)
        set_no_activate(self.win, True)
        # The card is a normal window on purpose: it stays readable and
        # selectable.  It is placed *beside* the control it explains, and it
        # never takes focus away from Praat.

    # -- rendering --------------------------------------------------
    def _on_click(self, _event=None) -> None:
        # The card is click-through in Tk (Praat must keep working), so this
        # only fires when the user clicks the title bar of a mapped window.
        # The application decides what a click means.
        clicker = getattr(self, "on_click", None)
        if clicker:
            clicker()

    def is_visible(self) -> bool:
        """Is the card on screen?"""

        try:
            return bool(self.win.winfo_viewable())
        except tk.TclError:
            return False

    def geometry(self) -> tuple[int, int, int, int]:
        """The card's rectangle on screen."""

        try:
            x = self.win.winfo_rootx()
            y = self.win.winfo_rooty()
            return (x, y, x + self.win.winfo_width(), y + self.win.winfo_height())
        except tk.TclError:
            return (0, 0, 0, 0)

    def set_pinned(self, pinned: bool) -> None:
        self.pinned = pinned
        # A pinned card is click-through too (Praat must keep working), but the
        # user can still scroll it with the wheel.
        set_click_through(self.win, True)

    def show(self, headline: str, body: str, *,
             anchor: tuple[int, int] | None = None,
             rect: tuple[int, int, int, int] | None = None,
             source: str = "", signature: tuple[str, str] | None = None,
             image=None) -> None:
        """Render and position the card."""
        if signature is not None and signature == self._signature and self.win.winfo_viewable():
            self._reposition(anchor, rect)
            return

        self._signature = signature
        self.title_label.configure(text=headline or "")

        parsed = parse_body(body or "", self.lang)
        self._fill_body(parsed)
        self._fill_now(parsed)

        text = footer_text(source, self.lang)
        self.source_label.configure(text=text)
        if text:
            self.source_label.pack(fill="x", padx=CARD_PAD, pady=(6, CARD_PAD))
        else:
            self.source_label.pack_forget()

        self._fit(body or "")
        self.win.geometry(f"{self._width}x{self._height}+0+0")
        self._reposition(anchor, rect)
        if not self.win.winfo_viewable():
            self.win.deiconify()
        # Tk rebuilds the HWND when a withdrawn toplevel is deiconified, so the
        # window styles have to be applied *after* the window is mapped.
        set_no_activate(self.win, True)
        keep_on_top(self.win)
        try:
            self.win.lift()
        except tk.TclError:
            pass

    def _fill_now(self, parsed: Body) -> None:
        """The band that says what the control means right now."""

        marker = ""
        parts: list[str] = []
        for notice in parsed.notices:
            parts.append(f"⚠ {notice}")
        if parsed.context:
            now = NOW_LABEL.get(self.lang, NOW_LABEL["zh"])
            marker = now
            parts.append(" ".join(parsed.context))
        if not parts:
            self.now_box.pack_forget()
            return
        self.now_marker.configure(text=marker)
        self.now_label.configure(text="\n\n".join(parts))
        self.now_box.pack(fill="x", padx=CARD_PAD, pady=(8, 0), before=self.body)

    def _fill_body(self, parsed: Body) -> None:
        """The sections, with their labels and their lists."""

        self.body.configure(state="normal")
        self.body.delete("1.0", "end")
        for section in parsed.known:
            if section.label:
                marker = "• " if section.key == "pitfalls" else ""
                tag = "warn" if section.key == "pitfalls" else "label"
                self.body.insert("end", f"{marker}{section.label}\n", tag)
            if section.text:
                self.body.insert("end", f"{section.text}\n\n", "body")
            for item in section.items:
                self.body.insert("end", f"• {item}\n", "pitfall")
            self.body.insert("end", "\n")
        for paragraph in parsed.prose:
            self.body.insert("end", f"{paragraph}\n\n", "body")
        for section in parsed.lists:
            if section.label:
                self.body.insert("end", f"{section.label}\n", "muted")
            for item in section.items:
                self.body.insert("end", f"• {item}\n", "body")
            self.body.insert("end", "\n")
        self.body.configure(state="disabled")

    def _fit(self, body_text: str) -> None:
        """Size the card to its content.

        The Text widget is sized in "average character" units, so we measure
        the real pixel width of the text with the actual font and convert it
        back.  The height is then taken from Tk's own layout: the widget is
        first made tall enough for any text, which forces Tk to lay out the
        wrapped lines, and the resulting geometry says how many display lines
        the text really needs.  (Asking Tk for the line *count* does not work:
        ``index`` counts logical lines, and wrapped text does not create new
        ones.)
        """
        avg = self._font.measure("abcdefghijklmnopqrstuvwxyz") / 26.0
        avg = max(6.0, avg)

        # The card has the same width as the Qt card: a fixed column that
        # the text never re-wraps in.
        usable_px = MAX_CARD_W - 2 * CARD_PAD - 6
        chars = max(MIN_CHARS, min(MAX_CHARS, int(usable_px / avg)))
        self.now_label.configure(wraplength=max(120, usable_px - 11))

        # Make the widget tall enough for anything, so Tk lays out the
        # wrapped text, then read the real height back.
        self.body.configure(width=chars, height=MAX_LINES)
        self.win.update_idletasks()

        line_h = max(12, int(self._font.metrics("linespace")))
        # The text widget knows how many *display* lines its content needs
        # at the current width: the wrapped lines count, not the logical
        # ones.
        needed = max(0, self.body.winfo_reqheight())
        total_lines = max(1, min(MAX_LINES, int(math.ceil(needed / line_h))))

        # Everything that is not the text: the title, the band, the footer.
        chrome = max(0, self.inner.winfo_reqheight()
                     - self.body.winfo_reqheight())
        room = max(4, int((MAX_CARD_H - chrome) / line_h))
        total_lines = min(total_lines, room)

        self.body.configure(height=total_lines)
        self.win.update_idletasks()

        self._width = MAX_CARD_W
        self._height = max(60, min(MAX_CARD_H, self.inner.winfo_reqheight() + 2))

    def _reposition(self, anchor: tuple[int, int] | None,
                   rect: tuple[int, int, int, int] | None) -> None:
        width = self._width
        height = self._height
        if rect is not None:
            x, y = clamp_rect(rect, width, height)
        elif anchor is not None:
            x, y = clamp_rect((anchor[0], anchor[1], anchor[0], anchor[1]), width, height)
        else:
            x, y = 40, 40
        self.win.geometry(f"+{x}+{y}")

    def raise_(self) -> None:
        """Put the card above the other overlay windows."""

        try:
            self.win.lift()
        except tk.TclError:
            pass

    def hide(self) -> None:
        self._signature = None
        if self.win.winfo_viewable():
            self.win.withdraw()

    def destroy(self) -> None:
        try:
            self.win.destroy()
        except tk.TclError:
            pass
