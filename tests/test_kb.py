"""Tests for the knowledge base loader and matching rules."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from praatao.tutor.kb import KnowledgeBase, KnowledgeEntry, normalize_key

SAMPLE = """
version: 1
entries:
  - id: view-and-edit
    aliases: ["View & Edit"]
    control_types: [ButtonControl]
    title: {en: "Open the sound editor", zh: "打开声音编辑器"}
    what: {en: "Opens the editor for the selected object.", zh: "打开当前选中对象的编辑器。"}
    how: {en: "Select a Sound first, then click this button.", zh: "先选中一个 Sound，再点这个按钮。"}
    concept: {en: "Time and frequency views.", zh: "时间域与频域视图。"}
    pitfalls:
      - {en: "Nothing selected yet.", zh: "还没有选中任何对象。"}
    keywords: [editor, waveform, 编辑器]
  - id: read-from-file
    aliases: ["Read from file..."]
    title: {en: "Read a sound file", zh: "读取音频文件"}
    what: {en: "Loads a WAV file as a Sound object.", zh: "把 WAV 文件读成 Sound 对象。"}
    how: {en: "Pick a file, then click OK.", zh: "选择文件，点确定。"}
    keywords: [open, wav, load, 打开]
"""


class NormalizeKeyTests(unittest.TestCase):
    def test_collapses_whitespace(self):
        self.assertEqual(normalize_key("  Analyse   spectrum "), "analyse spectrum")

    def test_strips_cascade_marker(self):
        self.assertEqual(normalize_key("\u202f\u202f   Draw  >"), "draw")

    def test_strips_list_index(self):
        self.assertEqual(normalize_key("1. Sound demo_vowel"), "sound demo_vowel")

    def test_keeps_ellipsis(self):
        self.assertEqual(normalize_key("Read from file..."), "read from file...")

    def test_folds_case(self):
        self.assertEqual(normalize_key("View & Edit"), "view & edit")


class KnowledgeBaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        path = Path(self.tmp.name) / "elements.yaml"
        path.write_text(SAMPLE, encoding="utf-8")
        self.kb = KnowledgeBase.load(path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_loads_entries(self):
        self.assertEqual(len(self.kb), 2)
        self.assertIsNotNone(self.kb.by_id("view-and-edit"))

    def test_lookup_exact(self):
        entry = self.kb.lookup("View & Edit")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.id, "view-and-edit")

    def test_lookup_normalized_cascade(self):
        entry = self.kb.lookup("\u202f\u202f   Draw  >")
        self.assertIsNone(entry)  # no draw entry in the fixture

    def test_lookup_by_id(self):
        entry = self.kb.lookup("read-from-file")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.id, "read-from-file")

    def test_lookup_ignores_case_and_space(self):
        self.assertEqual(self.kb.lookup("  view & edit  ").id, "view-and-edit")

    def test_lookup_by_keyword(self):
        entry = self.kb.lookup("Open the editor")
        self.assertIsNotNone(entry)

    def test_unknown_returns_none(self):
        self.assertIsNone(self.kb.lookup("Quantum flux capacitor"))

    def test_search_finds_entry(self):
        results = self.kb.search("load a wav file")
        self.assertTrue(results)
        self.assertEqual(results[0].id, "read-from-file")

    def test_bilingual_fields(self):
        entry = self.kb.by_id("view-and-edit")
        self.assertEqual(entry.title("zh"), "打开声音编辑器")
        self.assertEqual(entry.title("en"), "Open the sound editor")
        self.assertEqual(entry.pitfall_texts("zh"), ["还没有选中任何对象。"])

    def test_stats(self):
        stats = self.kb.stats()
        self.assertEqual(stats["entries"], 2)
        self.assertTrue(stats["bilingual"])


class MissingFileTests(unittest.TestCase):
    def test_missing_file_gives_empty_kb(self):
        kb = KnowledgeBase.load(Path("does-not-exist.yaml"))
        self.assertEqual(len(kb), 0)
        self.assertIsNone(kb.lookup("anything"))


class EntryTests(unittest.TestCase):
    def test_empty_entry_is_safe(self):
        entry = KnowledgeEntry(id="x")
        self.assertEqual(entry.title("zh"), "")
        self.assertEqual(entry.pitfall_texts("en"), [])


if __name__ == "__main__":
    unittest.main()
