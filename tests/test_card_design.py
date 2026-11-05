"""Tests for the design of the hover card.

The card is the one thing every student sees, so the things that can be
checked automatically are checked here:

* the structure of the HTML the card is built from (the order of the
  sections, the traps as a list, the text escaped);
* the size of the card (it stays a card, it does not become a panel);
* that a very long text does not break the layout;
* that the Qt card and the Tk card agree on what the body means.

PySide6 is optional, so the parts that need it are skipped when it is not
installed.
"""

from __future__ import annotations

import html
import re
import time
import unittest

from praatao.ui.hover import (
    Body as TkBody,
    Section as TkSection,
    footer_text as tk_footer_text,
    parse_body as tk_parse_body,
    source_kind as tk_source_kind,
)

try:  # pragma: no cover - PySide6 is optional
    from praatao.ui.qt.host import qt_available

    QT = qt_available()
except Exception:  # noqa: BLE001
    QT = False

if QT:  # pragma: no cover - depends on the machine
    from PySide6 import QtWidgets

    from praatao.ui.qt.hover import (
        CARD_MAX_HEIGHT,
        CARD_MAX_WIDTH,
        CONTENT_WIDTH,
        QtHoverCard,
        body_to_html,
        footer_text,
        parse_body,
        source_kind,
    )

BODY = """这是什么：打开 Sound 或 TextGrid 的编辑窗口。

怎么用：先在 Objects 窗口里选中物件，再点这个按钮。

概念：Praat 以物件为中心，档案变成 Sound 物件。

常见坑：
• 只选 TextGrid 时只有层级，没有波形。
• 只选 Sound 时只有波形，没有层级。

已选中 Sound demo_vowel，点这个可以打开编辑器。"""


class BodyStructureTests(unittest.TestCase):
    """The plain text of the advice becomes a structure."""

    def test_the_sections_are_found(self) -> None:
        parsed = parse_body(BODY, "zh")
        self.assertEqual(
            [section.key for section in parsed.known],
            ["what", "how", "concept", "pitfalls"],
        )
        self.assertEqual(
            [section.label for section in parsed.known],
            ["这是什么", "怎么用", "概念", "常见坑"],
        )

    def test_the_traps_are_a_list(self) -> None:
        parsed = parse_body(BODY, "zh")
        traps = parsed.known[-1]
        self.assertEqual(traps.key, "pitfalls")
        self.assertEqual(len(traps.items), 2)
        self.assertIn("只选 TextGrid", traps.items[0])

    def test_the_state_of_praat_becomes_the_now_band(self) -> None:
        parsed = parse_body(BODY, "zh")
        self.assertEqual(len(parsed.context), 1)
        self.assertIn("demo_vowel", parsed.context[0])
        self.assertEqual(parsed.notices, [])

    def test_a_notice_is_recognised(self) -> None:
        parsed = parse_body("（这个按钮现在是灰的。）\n\n" + BODY, "zh")
        self.assertEqual(len(parsed.notices), 1)
        self.assertIn("灰", parsed.notices[0])

    def test_a_body_without_sections_is_free_text(self) -> None:
        parsed = parse_body("这个按钮打开编辑器。\n\n（由模型生成。）", "zh")
        self.assertEqual(parsed.known, [])
        self.assertEqual(parsed.prose, ["这个按钮打开编辑器。"])
        self.assertEqual(len(parsed.notices), 1)

    def test_the_sections_come_in_the_cards_order(self) -> None:
        """Even when the body has them in another order."""

        scrambled = """概念：物件。

常见坑：
• 一个坑。

这是什么：东西。

怎么用：动作。"""
        parsed = parse_body(scrambled, "zh")
        self.assertEqual(
            [section.key for section in parsed.known],
            ["what", "how", "concept", "pitfalls"],
        )


class HtmlTests(unittest.TestCase):
    """The card is typeset from HTML."""

    def test_the_html_has_the_sections_in_order(self) -> None:
        html = body_to_html(BODY, "zh")
        positions = []
        for label in ("这是什么", "怎么用", "概念", "常见坑"):
            found = html.find(label)
            self.assertNotEqual(found, -1, f"{label} is missing")
            positions.append(found)
        self.assertEqual(positions, sorted(positions))

    def test_the_traps_are_list_items(self) -> None:
        html = body_to_html(BODY, "zh")
        self.assertIn("<ul", html)
        self.assertEqual(html.count("<li"), 2)
        self.assertIn("只选 TextGrid", html)

    def test_the_text_is_escaped(self) -> None:
        html = body_to_html("这是什么：<script>alert(1)</script> & \"引号\"", "zh")
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("&amp;", html)

    def test_the_now_band_comes_first(self) -> None:
        html = body_to_html(BODY, "zh")
        self.assertLess(html.find("demo_vowel"), html.find("这是什么"))

    def test_the_english_body_works(self) -> None:
        html = body_to_html(
            "What it is: a button.\n\nCommon pitfalls:\n• first trap",
            "en",
        )
        self.assertIn("What it is", html)
        self.assertIn("Common pitfalls", html)
        self.assertIn("<li", html)

    def test_an_empty_body_is_an_empty_document(self) -> None:
        html = body_to_html("", "zh")
        self.assertIsInstance(html, str)
        self.assertNotIn("<li", html)


class SourceTests(unittest.TestCase):
    """The footer says where the answer came from."""

    def test_the_knowledge_base(self) -> None:
        self.assertEqual(source_kind("离线知识库 / offline knowledge base"), "kb")
        self.assertIn("知识库", footer_text("离线知识库 / offline knowledge base", "zh"))

    def test_the_model(self) -> None:
        self.assertEqual(source_kind("AI 生成 / AI generated - may be imperfect"), "llm")
        text = footer_text("AI 生成 / AI generated - may be imperfect", "zh")
        self.assertIn("大模型", text)
        self.assertIn("慢", text)

    def test_both(self) -> None:
        kind = source_kind("离线知识库 + AI / knowledge base + AI")
        self.assertEqual(kind, "kb+llm")
        self.assertIn("慢", footer_text("离线知识库 + AI / knowledge base + AI", "zh"))

    def test_an_unknown_source_is_shown_as_it_is(self) -> None:
        self.assertEqual(source_kind("来源"), "")
        self.assertEqual(footer_text("来源", "zh"), "来源")

    def test_no_source_no_footer(self) -> None:
        self.assertEqual(footer_text("", "zh"), "")


class TheTwoCardsAgreeTests(unittest.TestCase):
    """The Tk card and the Qt card must mean the same thing."""

    def test_the_same_sections(self) -> None:
        qt_parsed = parse_body(BODY, "zh")
        tk_parsed = tk_parse_body(BODY, "zh")
        self.assertEqual(
            [(s.key, s.label, s.text, s.items) for s in qt_parsed.known],
            [(s.key, s.label, s.text, s.items) for s in tk_parsed.known],
        )
        self.assertEqual(qt_parsed.context, tk_parsed.context)
        self.assertEqual(qt_parsed.notices, tk_parsed.notices)

    def test_the_same_footer(self) -> None:
        def plain(text: str) -> str:
            return html.unescape(re.sub(r"<[^>]+>", "", text)).replace("\xa0", " ").strip()

        for source in ("离线知识库 / offline knowledge base",
                       "AI 生成 / AI generated - may be imperfect",
                       "离线知识库 + AI / knowledge base + AI"):
            self.assertEqual(tk_source_kind(source), source_kind(source))
            self.assertEqual(
                plain(tk_footer_text(source, "zh")),
                plain(footer_text(source, "zh")),
            )

    def test_the_same_shapes(self) -> None:
        self.assertTrue(issubclass(TkBody, object))
        self.assertTrue(issubclass(TkSection, object))


@unittest.skipUnless(QT, "PySide6 is not installed")
class CardSizeTests(unittest.TestCase):
    """The card is a card, not a panel."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def make_card(self) -> "QtHoverCard":
        card = QtHoverCard(None, lang="zh")
        self.addCleanup(card.destroy)
        return card

    def show(self, card: "QtHoverCard", body: str, headline: str = "标题") -> None:
        card.show(headline, body, anchor=(100, 100), rect=(100, 100, 200, 130),
                  source="离线知识库 / offline knowledge base", signature=("k", "s"))

    def test_the_card_stays_within_its_limits(self) -> None:
        card = self.make_card()
        self.show(card, BODY)
        width, height = card._card_size
        self.assertLessEqual(width, CARD_MAX_WIDTH)
        self.assertLessEqual(height, CARD_MAX_HEIGHT)
        self.assertGreaterEqual(width, 240)
        self.assertGreaterEqual(height, 100)

    def test_a_short_body_makes_a_small_card(self) -> None:
        card = self.make_card()
        self.show(card, "这是什么：一个按钮。")
        width, height = card._card_size
        self.assertLess(height, 260)
        self.assertGreaterEqual(height, 100)

    def test_a_very_long_body_does_not_break_the_layout(self) -> None:
        card = self.make_card()
        long_body = ("这是什么：" + "Praat 的编辑窗口。" * 400 + "\n\n"
                     "常见坑：\n" + "\n".join(f"• 第 {i} 个坑。" for i in range(60)))
        self.show(card, long_body)
        width, height = card._card_size
        self.assertLessEqual(width, CARD_MAX_WIDTH)
        self.assertLessEqual(height, CARD_MAX_HEIGHT)
        self.assertGreaterEqual(width, 240)
        # The text is still there, even if the card cannot show it all.
        self.assertIn("第 59 个坑", card.body.toPlainText())

    def test_a_very_long_title_does_not_break_the_layout(self) -> None:
        card = self.make_card()
        self.show(card, BODY, headline="一" * 200)
        width, height = card._card_size
        self.assertLessEqual(width, CARD_MAX_WIDTH)
        self.assertLessEqual(height, CARD_MAX_HEIGHT)

    def test_the_card_does_not_cover_the_control(self) -> None:
        card = self.make_card()
        rect = (300, 300, 460, 340)
        self.show(card, BODY)
        card._reposition((380, 320), rect)
        left, top, right, bottom = card.geometry()
        self.assertFalse(left < rect[2] and rect[0] < right
                         and top < rect[3] and rect[1] < bottom)

    def test_the_text_column_is_not_too_wide(self) -> None:
        """Chinese text needs a measure: about 30 characters per line."""

        self.assertLessEqual(CONTENT_WIDTH, 400)
        self.assertGreaterEqual(CONTENT_WIDTH / 13.0, 22.0)

    def test_a_render_is_fast(self) -> None:
        """The card must not make the coach feel slow."""

        card = self.make_card()
        samples = []
        for index in range(12):
            start = time.perf_counter()
            card.show(f"标题 {index}", BODY, anchor=(100, 100),
                      rect=(100, 100, 200, 130), source="离线知识库",
                      signature=("k", index))
            samples.append((time.perf_counter() - start) * 1000)
        samples.sort()
        median = samples[len(samples) // 2]
        self.assertLess(median, 25.0, f"a render took {median:.1f} ms")


class TypographyTests(unittest.TestCase):
    """Chinese typography: the rules the card follows."""

    def test_the_font_stack_has_a_cjk_font(self) -> None:
        from praatao.ui.qt.hover import FONT_STACK

        joined = " ".join(FONT_STACK).lower()
        self.assertTrue(
            any(name in joined for name in
                ("yahei", "pingfang", "noto sans cjk", "source han", "hiragino"))
        )

    def test_the_line_height_is_comfortable_for_chinese(self) -> None:
        from praatao.ui.qt.hover import LINE_HEIGHT

        self.assertGreaterEqual(LINE_HEIGHT, 150)
        self.assertLessEqual(LINE_HEIGHT, 170)

    def test_the_labels_of_both_languages_are_the_same(self) -> None:
        from praatao.ui.qt.hover import SECTION_LABELS

        self.assertEqual(len(SECTION_LABELS["zh"]), len(SECTION_LABELS["en"]))
        self.assertEqual(len(set(SECTION_LABELS["zh"])), len(SECTION_LABELS["zh"]))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
