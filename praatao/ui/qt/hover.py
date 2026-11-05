"""The hover card, drawn with Qt.

The card is the coach's one chance to explain a control, so it has to look
like something a beginner can trust and read in two seconds.  The shape is
the one every good tool uses (VS Code, IntelliJ, Raycast, the system
tooltips):

    title          what the control is
    now            why it matters at this moment, in this window
    what / how     what it does, and how to use it here
    concept        the idea behind it
    pitfalls       the traps, one per line
    footer         where the answer came from

Everything is drawn from plain text: the tutor hands over a body of text
with a few markers, :func:`parse_body` splits it into the parts above and
:func:`body_to_html` typesets them.

The card never takes focus away from Praat and never blocks Praat's mouse
input: it is a ``Qt.Tool`` window that is shown without activating.
"""

from __future__ import annotations

import html
from dataclasses import dataclass, field
from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets

__all__ = [
    "QtHoverCard",
    "body_to_html",
    "parse_body",
    "source_kind",
    "footer_text",
    "CARD_MAX_WIDTH",
    "CARD_MAX_HEIGHT",
    "CONTENT_WIDTH",
    "TEXT_WIDTH",
]

# --------------------------------------------------------------------------
# One visual language, shared with the side panel and the settings window.
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
# Metrics.  The card is a card, not a panel: it is narrow enough to sit
# next to the control it explains, and short enough to read at a glance.
# --------------------------------------------------------------------------
CARD_MAX_WIDTH = 400
CARD_MAX_HEIGHT = 520
CARD_RADIUS = 12
CARD_PAD = 14
#: Room around the card for the shadow.  It is smaller than the gap
#: between the card and the control it explains, so the window of the card
#: never reaches over that control.
SHADOW_MARGIN = 12
#: The width of the text column.
CONTENT_WIDTH = CARD_MAX_WIDTH - 2 * CARD_PAD
#: The width of the title: the column minus the two buttons.
TITLE_WIDTH = CONTENT_WIDTH - 2 * 24 - 2 * 4
#: The width the text is measured at.  The scroll bar takes a little of the
#: column when it appears, and the text must not re-wrap when it does.
TEXT_WIDTH = CONTENT_WIDTH - 12

TITLE_PX = 14
LABEL_PX = 12
BODY_PX = 13
FOOT_PX = 11

#: The size of the pin and the close button.
BUTTON_SIZE = 24

#: Chinese needs air: about 1.56 times the font size, never less than 1.5.
LINE_HEIGHT = 156
LABEL_LINE_HEIGHT = 135

#: The gaps between the parts of the card.
GAP_AFTER_TITLE = 7
GAP_AFTER_RULE = 8
GAP_BEFORE_RULE = 8
GAP_BEFORE_FOOTER = 6

#: A font stack that has good CJK glyphs at small sizes on Windows.
FONT_STACK = (
    "Microsoft YaHei UI",
    "Microsoft YaHei",
    "PingFang SC",
    "Hiragino Sans GB",
    "Noto Sans CJK SC",
    "Source Han Sans SC",
    "Segoe UI",
    "sans-serif",
)

#: How tall a picture inside the card may be.
CARD_IMAGE_HEIGHT = 170

#: The soft shadow is a stack of rounded rectangles.
SHADOW_STEPS = 5
SHADOW_STEP = 2
SHADOW_ALPHA = 52

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

#: The colour of the little dot in front of the footer text.
FOOTER_DOT = {"kb": MUTED, "llm": ACCENT, "kb+llm": ACCENT}

#: The label in front of the "now" band, per language.
NOW_LABEL = {"zh": "现在", "en": "Now"}


# --------------------------------------------------------------------------
# The body of the advice: plain text with a few markers.
# --------------------------------------------------------------------------
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

    #: System notices ("this button is greyed out", "asking the model...").
    notices: list[str] = field(default_factory=list)
    #: The lines about the state of Praat right now.
    context: list[str] = field(default_factory=list)
    #: The four sections, plus any extra list.
    sections: list[Section] = field(default_factory=list)
    #: Free text, for a body that has no sections (a model answer).
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


def _esc(text: str) -> str:
    """Make a string safe to put in the document."""

    return html.escape(text or "", quote=True)


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


# --------------------------------------------------------------------------
# Typesetting
# --------------------------------------------------------------------------
_ROOT_STYLE = (
    "font-family:'Microsoft YaHei UI','Microsoft YaHei','PingFang SC',"
    "'Hiragino Sans GB','Noto Sans CJK SC','Source Han Sans SC','Segoe UI',"
    f"sans-serif; font-size:{BODY_PX}px; color:{FG}; margin:0; padding:0;"
)


def _band(text: str, background: str, label: str = "") -> str:
    """A tinted band with room around the text.

    A table is the only thing Qt's rich text gives padding to, so the
    bands are single cell tables of a fixed width.
    """

    content = f"{label}{_esc(text)}" if label else _esc(text)
    return (
        f'<table width="{TEXT_WIDTH}" cellpadding="8" cellspacing="0" '
        f'bgcolor="{background}" style="margin:0 0 9px 0;">'
        f"<tr><td>{content}</td></tr></table>"
    )


def _section_html(section: Section) -> str:
    """One section: a small bold label and the text under it."""

    colour = WARN_FG if section.key == "pitfalls" else FG
    # The traps are a list, so the label gets the same bullet as the list
    # below it.
    marker = "• " if section.key == "pitfalls" else ""
    parts: list[str] = []
    if section.label:
        parts.append(
            f'<div class="label" style="margin:0 0 3px 0; font-size:{LABEL_PX}px; '
            f"font-weight:600; color:{colour}; line-height:{LABEL_LINE_HEIGHT}%;\">"
            f"{_esc(marker + section.label)}</div>"
        )
    if section.text:
        parts.append(
            f'<div class="text" style="margin:0 0 9px 0; font-size:{BODY_PX}px; '
            f'color:{FG}; line-height:{LINE_HEIGHT}%;">{_esc(section.text)}</div>'
        )
    if section.items:
        items = "".join(
            f'<li style="margin:0 0 3px 0; font-size:{BODY_PX}px; color:{FG}; '
            f'line-height:{LINE_HEIGHT}%;">{_esc(item)}</li>'
            for item in section.items
        )
        parts.append(f'<ul class="traps" style="margin:0 0 3px 0;">{items}</ul>')
    return (
        f'<div class="section" data-kind="{_esc(section.key)}">'
        + "".join(parts)
        + "</div>"
    )


def _body_html(parsed: Body, lang: str) -> str:
    """The HTML of everything that goes into the text area."""

    parts: list[str] = []
    for section in parsed.known:
        parts.append(_section_html(section))
    for paragraph in parsed.prose:
        parts.append(
            f'<div class="prose" style="margin:0 0 8px 0; font-size:{BODY_PX}px; '
            f'color:{FG}; line-height:{LINE_HEIGHT}%;">{_esc(paragraph)}</div>'
        )
    for section in parsed.lists:
        if section.label:
            parts.append(
                f'<div class="label" style="margin:0 0 3px 0; font-size:{LABEL_PX}px; '
                f"font-weight:600; color:{MUTED}; line-height:{LABEL_LINE_HEIGHT}%;\">"
                f"{_esc(section.label)}</div>"
            )
        items = "".join(
            f'<li style="margin:0 0 3px 0; font-size:{BODY_PX}px; color:{FG}; '
            f'line-height:{LINE_HEIGHT}%;">{_esc(item)}</li>'
            for item in section.items
        )
        parts.append(f'<ul class="list" style="margin:0 0 3px 0;">{items}</ul>')
    return "".join(parts)


def body_to_html(body: str, lang: str = "zh") -> str:
    """Turn the tutor's plain text into small, readable HTML.

    The result is the whole card body: first the notices and the "now"
    band, then the four sections in the order the card shows them.
    """

    parsed = parse_body(body, lang)
    parts: list[str] = []
    for notice in parsed.notices:
        parts.append(
            _band(notice, WARN_BG,
                  label=f'<span style="color:{WARN_FG}; font-weight:600;">⚠</span> ')
        )
    if parsed.context:
        now = NOW_LABEL.get(lang, NOW_LABEL["zh"])
        parts.append(
            _band(" ".join(parsed.context), SOFT,
                  label=f'<span style="color:{ACCENT}; font-weight:600;">'
                        f"{_esc(now)}</span>　")
        )
    parts.append(_body_html(parsed, lang))
    return f'<div style="{_ROOT_STYLE}">' + "".join(parts) + "</div>"


# --------------------------------------------------------------------------
# The source of an answer
# --------------------------------------------------------------------------
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
        return _esc(source)
    table = FOOTER_TEXT.get(lang, FOOTER_TEXT["zh"])
    label = table.get(kind, source)
    dot = FOOTER_DOT.get(kind, MUTED)
    return f'<span style="color:{dot};">●</span>&nbsp;{_esc(label)}'


# --------------------------------------------------------------------------
# The window
# --------------------------------------------------------------------------
def _font(px: int, weight: Any = QtGui.QFont.Weight.Normal) -> QtGui.QFont:
    """A font from the stack, at a pixel size."""

    font = QtGui.QFont()
    font.setFamilies(list(FONT_STACK))
    font.setPixelSize(px)
    font.setWeight(weight)
    font.setStyleStrategy(QtGui.QFont.StyleStrategy.PreferAntialias)
    return font


class _CardFrame(QtWidgets.QWidget):
    """A frameless, translucent, rounded window with a soft shadow.

    The shadow is painted by hand instead of being a
    ``QGraphicsDropShadowEffect``: an effect makes the window render through
    a different path in the compositor, and the text on screen then does not
    match what Qt draws itself.  The shadow is drawn once into a pixmap and
    reused, so a repaint costs one blit.
    """

    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.Tool
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
            | QtCore.Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_AlwaysStackOnTop, True)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self._cache: QtGui.QPixmap | None = None
        self._cache_size: tuple[int, int] | None = None

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = QtGui.QPainter(self)
        size = self.size()
        if self._cache is None or self._cache_size != (size.width(), size.height()):
            self._cache = self._render(size)
            self._cache_size = (size.width(), size.height())
        painter.drawPixmap(0, 0, self._cache)

    def _render(self, size: QtCore.QSize) -> QtGui.QPixmap:
        ratio = self.devicePixelRatioF()
        pixmap = QtGui.QPixmap(
            max(1, int(size.width() * ratio)), max(1, int(size.height() * ratio))
        )
        pixmap.setDevicePixelRatio(ratio)
        pixmap.fill(QtCore.Qt.GlobalColor.transparent)

        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)

        card = QtCore.QRectF(
            SHADOW_MARGIN,
            SHADOW_MARGIN,
            size.width() - 2 * SHADOW_MARGIN,
            size.height() - 2 * SHADOW_MARGIN,
        )

        # A soft shadow: a stack of rounded rectangles, each a little bigger
        # and a little fainter than the one before it.  The stack is moved a
        # little down and to the right, so the shadow falls like a drop
        # shadow instead of a halo.
        for step in range(SHADOW_STEPS, 0, -1):
            grow = step * SHADOW_STEP
            alpha = max(2, int(SHADOW_ALPHA / (step * 1.5)))
            shadow = QtCore.QRectF(card).adjusted(-grow, -grow, grow, grow)
            shadow.translate(1, 2)
            path = QtGui.QPainterPath()
            path.addRoundedRect(shadow, CARD_RADIUS + grow, CARD_RADIUS + grow)
            painter.setBrush(QtGui.QColor(58, 40, 20, alpha))
            painter.drawPath(path)

        path = QtGui.QPainterPath()
        path.addRoundedRect(card, CARD_RADIUS, CARD_RADIUS)
        painter.setBrush(QtGui.QColor(BG))
        painter.drawPath(path)
        painter.setPen(QtGui.QPen(QtGui.QColor(BORDER), 1.0))
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        painter.end()
        return pixmap


class QtHoverCard(QtCore.QObject):
    """The explainer card that follows the cursor.

    It is a ``QObject`` rather than a plain class so that it can carry
    signals: the card tells the application when the user dismissed it.
    """

    #: Emitted when the user clicks the card (or its close button).
    dismissed = QtCore.Signal()
    #: Emitted when the pin button is pressed.
    pin_toggled = QtCore.Signal(bool)

    def __init__(self, master: Any = None, lang: str = "zh") -> None:
        super().__init__()
        self.master = master
        self.lang = lang
        self.pinned = False
        self._signature: tuple | None = None
        self._body_text = ""
        self._card_size = (CARD_MAX_WIDTH, 200)
        # The height of the parts that come and go.  They are kept here
        # because ``isVisible()`` is false for every child while the card
        # itself is still hidden, and the card is measured before it is
        # shown.
        self._footer_height = 0
        self._image_height = 0

        self.win = _CardFrame()
        self.win.setObjectName("PraataoHoverCard")
        # Its own title, so the student can tell the card, the panel and
        # the settings apart in the task bar.
        self.win.setWindowTitle("Praatao 讲解卡" if self.lang == "zh" else "Praatao card")

        layout = QtWidgets.QVBoxLayout(self.win)
        layout.setContentsMargins(
            SHADOW_MARGIN + CARD_PAD,
            SHADOW_MARGIN + CARD_PAD,
            SHADOW_MARGIN + CARD_PAD,
            SHADOW_MARGIN + CARD_PAD,
        )
        layout.setSpacing(0)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(4)
        self.title_label = QtWidgets.QLabel("")
        self.title_label.setFont(_font(TITLE_PX, QtGui.QFont.Weight.DemiBold))
        self.title_label.setStyleSheet(f"color:{ACCENT}; background:transparent;")
        self.title_label.setWordWrap(True)
        # The width of the title is known, so the height of the wrapped text
        # is known too: the card never changes its size when it is drawn.
        self.title_label.setFixedWidth(TITLE_WIDTH)
        self.title_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop
        )
        header.addWidget(self.title_label)

        self.pin_button = QtWidgets.QToolButton()
        self.pin_button.setText("📍")
        self.pin_button.setToolTip("钉住这张卡片 / Pin this card")
        self.pin_button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.pin_button.setFixedSize(24, 24)
        self.pin_button.setStyleSheet(
            "QToolButton{background:transparent;border:none;font-size:13px;}"
            f"QToolButton:hover{{background:{SOFT};border-radius:10px;}}"
        )
        # The buttons are handled by the application, which polls the mouse
        # anyway: Windows gives the first click on an inactive window to
        # activating it, so a click that Qt never sees would leave the pin
        # button dead.
        header.addWidget(self.pin_button)

        self.close_button = QtWidgets.QToolButton()
        self.close_button.setText("✕")
        self.close_button.setToolTip("关闭 / Close")
        self.close_button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.close_button.setFixedSize(24, 24)
        self.close_button.setStyleSheet(
            "QToolButton{background:transparent;border:none;font-size:12px;"
            f"color:{MUTED};}}QToolButton:hover{{background:{SOFT};border-radius:10px;}}"
        )
        header.addWidget(self.close_button)

        layout.addLayout(header)
        layout.addSpacing(GAP_AFTER_TITLE)

        self.rule = QtWidgets.QFrame()
        self.rule.setFixedHeight(1)
        self.rule.setStyleSheet(f"background:{BORDER};")
        layout.addWidget(self.rule)
        layout.addSpacing(GAP_AFTER_RULE)

        self.body = QtWidgets.QTextBrowser()
        self.body.setOpenExternalLinks(False)
        self.body.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.body.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.body.setStyleSheet(
            "QTextBrowser{background:transparent;border:none;color:%s;}"
            "QScrollBar:vertical{background:transparent;width:10px;margin:0;}"
            "QScrollBar::handle:vertical{background:#DCD0BC;border-radius:5px;"
            "min-height:24px;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}"
            "QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical{background:none;}"
            % FG
        )
        self.body.document().setDocumentMargin(0)
        self.body.document().setDefaultFont(_font(BODY_PX))
        layout.addWidget(self.body)

        self.image_label = QtWidgets.QLabel()
        self.image_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background:transparent;")
        self.image_label.hide()
        layout.addWidget(self.image_label)

        layout.addSpacing(GAP_BEFORE_RULE)
        self.foot_rule = QtWidgets.QFrame()
        self.foot_rule.setFixedHeight(1)
        self.foot_rule.setStyleSheet(f"background:{BORDER};")
        layout.addWidget(self.foot_rule)
        layout.addSpacing(GAP_BEFORE_FOOTER)

        self.source_label = QtWidgets.QLabel("")
        self.source_label.setFont(_font(FOOT_PX))
        self.source_label.setStyleSheet(
            f"color:{MUTED}; background:transparent;"
        )
        self.source_label.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self.source_label.hide()
        layout.addWidget(self.source_label)

        # The shadow lives on the frame itself.
        self.win.hide()
        self.win.installEventFilter(self)
        # The title, the picture and the footer must not swallow clicks:
        # they have to reach the window so that the event filter below can
        # turn them into "dismiss".
        #
        # The body is the exception: it keeps its mouse events, so that
        # the wheel scrolls it and the scroll bar can be dragged.  The
        # application polls the mouse anyway, so a click on the text
        # still dismisses the card.
        for widget in (self.title_label, self.source_label,
                       self.image_label):
            widget.setAttribute(
                QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
            )

    # -- events -----------------------------------------------------
    def eventFilter(self, obj: Any, event: Any) -> bool:  # noqa: N802
        if obj is self.win and event.type() == QtCore.QEvent.Type.MouseButtonPress:
            # A click on the card dismisses it.  The application does the same
            # thing from its own mouse polling, because Windows gives the
            # first click on an inactive window to activating it.
            self.dismissed.emit()
        return super().eventFilter(obj, event)

    def pin_rect(self) -> tuple[int, int, int, int] | None:
        """The pin button's rectangle on screen."""

        return self._widget_rect(self.pin_button)

    def close_rect(self) -> tuple[int, int, int, int] | None:
        """The close button's rectangle on screen."""

        return self._widget_rect(self.close_button)

    def scroll_rect(self) -> tuple[int, int, int, int] | None:
        """The scroll bar's rectangle on screen.

        A click on the scroll bar is a click on the card, but it is not a
        click that means "go away": the student is reading on.
        """

        try:
            bar = self.body.verticalScrollBar()
            if not bar.isVisible():
                return None
            return self._widget_rect(bar)
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _widget_rect(widget: Any) -> tuple[int, int, int, int] | None:
        try:
            if not widget.isVisible():
                return None
            top_left = widget.mapToGlobal(widget.rect().topLeft())
            bottom_right = widget.mapToGlobal(widget.rect().bottomRight())
            return (
                top_left.x() - 2,
                top_left.y() - 2,
                bottom_right.x() + 3,
                bottom_right.y() + 3,
            )
        except Exception:  # noqa: BLE001
            return None

    # -- api --------------------------------------------------------
    def set_pinned(self, pinned: bool) -> None:
        self.pinned = bool(pinned)
        self.pin_button.setText("📌" if self.pinned else "📍")
        self.pin_button.setStyleSheet(
            f"QToolButton{{background:{SOFT};border:none;font-size:13px;}}"
            if self.pinned
            else "QToolButton{background:transparent;border:none;font-size:13px;}"
        )
        self.pin_toggled.emit(self.pinned)

    def is_visible(self) -> bool:
        return self.win.isVisible()

    def show(
        self,
        headline: str,
        body: str,
        *,
        anchor: tuple[int, int] | None = None,
        rect: tuple[int, int, int, int] | None = None,
        source: str = "",
        signature: tuple | None = None,
        image: Any = None,
    ) -> None:
        """Render and position the card."""

        if signature is not None and signature == self._signature and self.is_visible():
            self._reposition(anchor, rect)
            return

        self._signature = signature
        self._body_text = body or ""
        self.title_label.setText(headline or "")

        self.body.setHtml(body_to_html(self._body_text, self.lang))

        if image is not None:
            pixmap = self._as_pixmap(image)
            if pixmap is not None:
                scaled = pixmap.scaled(
                    CONTENT_WIDTH,
                    CARD_IMAGE_HEIGHT,
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation,
                )
                self.image_label.setPixmap(scaled)
                self.image_label.show()
                self._image_height = scaled.height()
            else:
                self.image_label.hide()
                self._image_height = 0
        else:
            self.image_label.hide()
            self._image_height = 0

        self._set_source(source)

        self._fit()
        self._scroll_to_top()
        self._reposition(anchor, rect)
        if not self.win.isVisible():
            self.win.show()
        self.win.raise_()

    def _set_source(self, source: str) -> None:
        """Put the source of the answer in the footer."""

        text = footer_text(source, self.lang)
        self.source_label.setText(text)
        self.source_label.setVisible(bool(text))
        self._footer_height = (
            self._text_height(self.source_label, text, CONTENT_WIDTH)
            if text else 0
        )

    def update_body(self, body: str, source: str | None = None) -> None:
        """Replace the body text (used when a model answer arrives later)."""

        self._body_text = body or ""
        self.body.setHtml(body_to_html(self._body_text, self.lang))
        if source is not None:
            self._set_source(source)
        self._fit()
        self._scroll_to_top()
        self._keep_on_screen()
        self.win.raise_()

    def set_image(self, image: Any) -> None:
        """Show a picture in the card (bytes from the image model).

        The picture arrives long after the card was shown, so it is added on
        its own: the text stays where it is and the card grows downwards.
        """

        pixmap = self._as_pixmap(image)
        if pixmap is None:
            return
        scaled = pixmap.scaled(
            CONTENT_WIDTH,
            CARD_IMAGE_HEIGHT,
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)
        self.image_label.show()
        self._image_height = scaled.height()
        self._fit()
        self._keep_on_screen()
        self.win.raise_()

    def _as_pixmap(self, image: Any) -> "QtGui.QPixmap | None":
        if isinstance(image, QtGui.QPixmap):
            return image
        if isinstance(image, (bytes, bytearray)):
            try:
                pixmap = QtGui.QPixmap()
                pixmap.loadFromData(bytes(image), "JPG")
                if pixmap.isNull():
                    pixmap.loadFromData(bytes(image))
                return None if pixmap.isNull() else pixmap
            except Exception:  # noqa: BLE001
                return None
        if isinstance(image, str):
            pixmap = QtGui.QPixmap(image)
            return None if pixmap.isNull() else pixmap
        # A PIL image: hand the bytes to Qt.
        try:
            import io

            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            pixmap = QtGui.QPixmap()
            pixmap.loadFromData(buffer.getvalue(), "PNG")
            return None if pixmap.isNull() else pixmap
        except Exception:  # noqa: BLE001
            return None

    def _fit(self) -> None:
        """Size the card to its content, within sane limits.

        The height comes from the text document itself: a ``QTextBrowser``
        knows how tall its wrapped HTML is, and that is the only number that
        is right for a proportional font with mixed Chinese and Latin.
        """

        self.body.setFixedWidth(CONTENT_WIDTH)
        document = self.body.document()
        document.setTextWidth(TEXT_WIDTH)
        text_height = int(document.size().height())

        title_height = self._title_height()
        footer_height = self._footer_height
        image_height = self._image_height

        # The header holds the title and the two buttons; the buttons are
        # the taller of the two.
        header_height = max(title_height, BUTTON_SIZE)

        chrome = (
            2 * CARD_PAD
            + header_height
            + GAP_AFTER_TITLE
            + 1
            + GAP_AFTER_RULE
            + image_height
            + GAP_BEFORE_RULE
            + 1
            + GAP_BEFORE_FOOTER
            + footer_height
        )
        room = max(60, CARD_MAX_HEIGHT - chrome)
        height = chrome + min(text_height, room)

        self._card_size = (CARD_MAX_WIDTH, height)
        # The body is given its height first: a text widget asks for the
        # whole document as its minimum size, and the window can only be as
        # small as the layout allows.
        body_height = min(text_height, room)
        if self.body.height() != body_height:
            self.body.setFixedHeight(body_height)
        width = CARD_MAX_WIDTH + 2 * SHADOW_MARGIN
        total = height + 2 * SHADOW_MARGIN
        if self.win.width() != width or self.win.height() != total:
            self.win.setFixedWidth(width)
            self.win.setFixedHeight(total)

    def _title_height(self) -> int:
        """How tall is the title when it is wrapped at its own width?

        The title has a known width, so the height of the wrapped text is
        known as well.  The label is not allowed to grow any further, or
        the layout would hand the extra pixels to it and the card would
        be a different size every time it is drawn.
        """

        text = self.title_label.text()
        if not text:
            return 0
        height = self.title_label.heightForWidth(TITLE_WIDTH)
        if height <= 0:
            height = self.title_label.sizeHint().height()
        self.title_label.setMaximumHeight(height)
        return height

    @staticmethod
    def _text_height(label: QtWidgets.QLabel, text: str, width: int) -> int:
        """How tall is this text when it is wrapped at ``width``."""

        if not text:
            return 0
        metrics = QtGui.QFontMetrics(label.font())
        rect = metrics.boundingRect(
            QtCore.QRect(0, 0, max(40, width), 0),
            int(QtCore.Qt.TextFlag.TextWordWrap),
            text,
        )
        return max(label.sizeHint().height(), rect.height())

    def _scroll_to_top(self) -> None:
        """Put the text back at the beginning."""

        try:
            cursor = self.body.textCursor()
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.Start)
            self.body.setTextCursor(cursor)
            self.body.verticalScrollBar().setValue(0)
        except Exception:  # noqa: BLE001
            pass

    def _reposition(
        self,
        anchor: tuple[int, int] | None,
        rect: tuple[int, int, int, int] | None,
    ) -> None:
        from ..overlay import clamp_rect

        width, height = self._card_size
        if rect is not None:
            x, y = clamp_rect(rect, width, height)
            x, y = self._keep_off(rect, x, y, width, height)
        elif anchor is not None:
            x, y = clamp_rect(
                (anchor[0], anchor[1], anchor[0], anchor[1]), width, height
            )
        else:
            x, y = 40, 40
        self.win.move(x - SHADOW_MARGIN, y - SHADOW_MARGIN)

    @staticmethod
    def _keep_off(
        target: tuple[int, int, int, int],
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> tuple[int, int]:
        """Never cover the control the card is talking about.

        The card normally stands beside the control, but on a narrow
        screen that is not always possible.  When it would, the card moves
        below the control instead.
        """

        left, top, right, bottom = target
        if not (x < right and left < x + width and y < bottom and top < y + height):
            return x, y
        from ..overlay import screen_size

        screen_w, screen_h = screen_size()
        below = bottom + 12
        if below + height <= screen_h - 8:
            return x, below
        above = top - 12 - height
        if above >= 8:
            return x, above
        return x, y

    def _keep_on_screen(self) -> None:
        """Keep the card on the screen when the content grows.

        The card grows downwards, so its top edge stays where it was: the
        reader does not have to chase the text when a late answer arrives.
        """

        from ..overlay import screen_size

        left, top, right, bottom = self.geometry()
        screen_w, screen_h = screen_size()
        width = right - left
        height = bottom - top
        new_left = min(left, max(8, screen_w - 8 - width))
        new_top = min(top, max(8, screen_h - 8 - height))
        if (new_left, new_top) != (left, top):
            self.win.move(new_left - SHADOW_MARGIN, new_top - SHADOW_MARGIN)

    def geometry(self) -> tuple[int, int, int, int]:
        """The card's rectangle on screen (the shadow is not part of it)."""

        top_left = self.win.mapToGlobal(
            QtCore.QPoint(SHADOW_MARGIN, SHADOW_MARGIN)
        )
        width, height = self._card_size
        return (
            top_left.x(),
            top_left.y(),
            top_left.x() + width,
            top_left.y() + height,
        )

    def raise_(self) -> None:
        """Put the card above the other overlay windows.

        The card must never take the focus.  It is a ``WindowDoesNotAcceptFocus``
        window, so ``activateWindow()`` would make Windows pass the focus on
        to the next window in the z-order - which is Praat, and that is how
        "Praat keeps jumping to the front while I am typing" happened.
        The window is raised with ``SWP_NOACTIVATE`` instead.
        """

        try:
            self.win.raise_()
            hwnd = int(self.win.winId())
        except Exception:  # noqa: BLE001
            return
        try:
            import win32gui

            win32gui.SetWindowPos(
                hwnd,
                win32gui.HWND_TOP,
                0,
                0,
                0,
                0,
                0x0010  # SWP_NOACTIVATE
                | 0x0040,  # SWP_SHOWWINDOW
            )
        except Exception:  # noqa: BLE001
            pass

    def set_lang(self, lang: str) -> None:
        """Switch the language of the section labels."""

        self.lang = lang
        try:
            self.body.setHtml(body_to_html(self._body_text, lang))
            self._fit()
        except Exception:  # noqa: BLE001
            pass

    def hide(self) -> None:
        self._signature = None
        if self.win.isVisible():
            self.win.hide()

    def destroy(self) -> None:
        try:
            self.win.close()
            self.win.deleteLater()
        except Exception:  # noqa: BLE001
            pass
