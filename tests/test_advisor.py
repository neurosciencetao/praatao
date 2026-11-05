"""Unit tests for :mod:`praatao.tutor.advisor` and :mod:`praatao.tutor.llm`.

The tests are deliberately self-contained: they use a fake knowledge base, a
fake LLM client and fake Praat state objects, so they never touch the real
``praatao.tutor.kb`` / ``praatao.sensors.*`` modules (which may still be under
construction) and never need the network.
"""

from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from praatao.tutor.advisor import Advice, Advisor
from praatao.tutor.llm import (
    LlmClient,
    LlmConfig,
    NullLlmClient,
    default_llm_client,
    describe_config,
)


# ----------------------------------------------------------------------
# fakes
# ----------------------------------------------------------------------
@dataclass
class FakeEntry:
    """Stand-in for :class:`praatao.tutor.kb.KnowledgeEntry`."""

    id: str
    aliases: list[str] = field(default_factory=list)
    title_en: str = ""
    title_zh: str = ""
    what_en: str = ""
    what_zh: str = ""
    how_en: str = ""
    how_zh: str = ""
    concept_en: str | None = None
    concept_zh: str | None = None
    pitfalls: Any = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)


class FakeKB:
    """Minimal knowledge base honouring the contract's API."""

    def __init__(self, entries: list[FakeEntry]) -> None:
        self._entries = list(entries)

    @staticmethod
    def _key(text: str) -> str:
        return " ".join(str(text or "").split()).strip().lower()

    def lookup(self, element_name: str, control_type: str | None = None) -> FakeEntry | None:
        key = self._key(element_name)
        if not key:
            return None
        for entry in self._entries:
            names = [entry.id, *entry.aliases]
            for name in names:
                if self._key(name) == key:
                    return entry
        for entry in self._entries:
            for keyword in entry.keywords:
                if keyword and keyword.lower() in key:
                    return entry
        return None

    def search(self, query: str, limit: int = 5) -> list[FakeEntry]:
        key = self._key(query)
        if not key:
            return []
        hits: list[FakeEntry] = []
        for entry in self._entries:
            haystack = " ".join(
                [entry.id, entry.title_en, entry.title_zh, entry.what_en, entry.what_zh,
                 entry.how_en, entry.how_zh, *entry.keywords, *entry.aliases]
            ).lower()
            if key in haystack or any(token in haystack for token in key.split()):
                hits.append(entry)
            if len(hits) >= limit:
                break
        return hits

    def entries(self) -> list[FakeEntry]:
        return list(self._entries)


class FakeLlm:
    """LLM double: returns a fixed answer, or raises on demand."""

    def __init__(self, answer: str = "FAKE-LLM-ANSWER", available: bool = True,
                 raises: bool = False) -> None:
        self.answer = answer
        self._available = available
        self._raises = raises
        self.calls: list[tuple[str, str]] = []

    def available(self) -> bool:
        return self._available

    def chat(self, system: str, user: str, timeout: float = 30.0) -> str | None:
        self.calls.append((system, user))
        if self._raises:
            raise RuntimeError("llm exploded")
        return self.answer

    def describe_config(self, lang: str = "zh") -> str:
        return "fake-llm"


def make_element(name: str, control_type: str = "ButtonControl",
                 window_title: str = "Praat Objects") -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        control_type=control_type,
        automation_id="",
        hwnd=0,
        rect=None,
        window_title=window_title,
        depth=0,
    )


def make_state(objects: list[Any] | None = None, selected: list[Any] | None = None,
               editor_open: bool = False, editor_object: str | None = None,
               tiers: list[str] | None = None, raw: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        running=True,
        version="6.4",
        objects=list(objects or []),
        selected=list(selected or []),
        editor_open=editor_open,
        editor_object=editor_object,
        textgrid_tiers=list(tiers or []),
        error=None,
        raw=dict(raw or {}),
    )


def make_sound(name: str = "demo_vowel", obj_id: int = 1, **extra: Any) -> SimpleNamespace:
    base = {"id": obj_id, "type": "Sound", "name": name}
    base.update(extra)
    return SimpleNamespace(**base)


def make_textgrid(name: str = "demo_tg", obj_id: int = 2) -> SimpleNamespace:
    return SimpleNamespace(id=obj_id, type="TextGrid", name=name)


#: Three fake entries with clearly different zh / en wording.
ENTRIES: list[FakeEntry] = [
    FakeEntry(
        id="view-and-edit",
        aliases=["View & Edit"],
        title_en="Open the sound editor",
        title_zh="打开声音编辑器",
        what_en="The sound editor shows the waveform and the analyses below it.",
        what_zh="声音编辑器显示波形，以及下方的各种分析图。",
        how_en="Select a Sound in the Objects window, then click View & Edit.",
        how_zh="先在 Objects 窗口里选中一个 Sound，然后点 View & Edit。",
        concept_en="Waveform and spectrogram live in the same editor.",
        concept_zh="波形和频谱图在同一个编辑器里。",
        pitfalls=[
            {"en": "The button does nothing when nothing is selected.",
             "zh": "没有选中对象时这个按钮点了也没反应。"},
        ],
        keywords=["editor", "waveform", "spectrogram", "view"],
    ),
    FakeEntry(
        id="to-textgrid",
        aliases=["To TextGrid...", "Annotate"],
        title_en="Create a TextGrid from a Sound",
        title_zh="从 Sound 创建 TextGrid",
        what_en="A TextGrid is a table of annotation tiers that belongs to a Sound.",
        what_zh="TextGrid 是标注层级表，它依附于一个 Sound。",
        how_en="Select the Sound, then use Annotate > To TextGrid.",
        how_zh="选中 Sound 之后，用 Annotate > To TextGrid。",
        concept_en="Tiers hold interval or point annotations.",
        concept_zh="层级里存放区间标注或点标注。",
        pitfalls=[],
        keywords=["textgrid", "annotation", "tier", "annotate"],
    ),
    FakeEntry(
        id="read-from-file",
        aliases=["Read from file..."],
        title_en="Read a sound file from disk",
        title_zh="从磁盘读入声音文件",
        what_en="Read from file creates a new Sound object from an audio file.",
        what_zh="Read from file 会从一个音频文件创建一个新的 Sound 对象。",
        how_en="Open > Read from file..., then pick a WAV file.",
        how_zh="Open > Read from file...，然后选一个 WAV 文件。",
        concept_en=None,
        concept_zh=None,
        pitfalls=[],
        keywords=["read", "file", "wav", "open"],
    ),
]


def make_kb() -> FakeKB:
    return FakeKB(ENTRIES)


# ----------------------------------------------------------------------
# advisor tests
# ----------------------------------------------------------------------
class AdvisorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.kb = make_kb()

    # -- known element ------------------------------------------------
    def test_known_element_uses_kb(self) -> None:
        advisor = Advisor(self.kb, llm=NullLlmClient(), lang="zh")
        advice = advisor.advise(make_element("View & Edit"), make_state())
        self.assertEqual(advice.source, "kb")
        self.assertIn(advice.entries[0], ENTRIES)
        self.assertIn("声音编辑器显示波形", advice.body)
        self.assertIn("选中一个 Sound", advice.body)
        self.assertIn("打开声音编辑器", advice.headline)

    def test_known_element_with_state_adds_context(self) -> None:
        advisor = Advisor(self.kb, llm=NullLlmClient(), lang="zh")
        sound = make_sound("demo_vowel")
        state = make_state(objects=[sound], selected=[sound])
        advice = advisor.advise(make_element("View & Edit"), state)
        self.assertEqual(advice.source, "kb")
        self.assertIn("demo_vowel", advice.body)
        self.assertIn("已选中 Sound demo_vowel", advice.body)

    # -- unknown element ----------------------------------------------
    def test_unknown_element_without_llm(self) -> None:
        advisor = Advisor(self.kb, llm=NullLlmClient(), lang="zh")
        advice = advisor.advise(make_element("Wobble the flux capacitor"), make_state())
        self.assertEqual(advice.source, "kb")
        self.assertTrue(advice.body.strip())
        self.assertIn("知识库里还没有这个控件的说明", advice.body)

    def test_unknown_element_with_llm(self) -> None:
        llm = FakeLlm(answer="The answer comes from the model.")
        advisor = Advisor(self.kb, llm=llm, lang="zh")
        advice = advisor.advise(make_element("Wobble the flux capacitor"), make_state())
        self.assertIn("llm", advice.source)
        self.assertIn("The answer comes from the model.", advice.body)
        self.assertTrue(llm.calls, "the LLM should have been consulted")
        # the prompt is grounded with the raw name and the state
        self.assertIn("Wobble the flux capacitor", llm.calls[0][1])

    def test_llm_failure_still_returns_advice(self) -> None:
        llm = FakeLlm(raises=True)
        advisor = Advisor(self.kb, llm=llm, lang="zh")
        advice = advisor.advise(make_element("Wobble the flux capacitor"), make_state())
        self.assertIsInstance(advice, Advice)
        self.assertTrue(advice.body.strip())
        self.assertNotIn("llm", advice.source)
        self.assertIn("知识库里还没有这个控件的说明", advice.body)

    def test_null_llm_client_is_offline(self) -> None:
        advisor = Advisor(self.kb, llm=NullLlmClient(), lang="zh")
        advice = advisor.advise(make_element("Wobble the flux capacitor"), make_state())
        self.assertEqual(advice.source, "kb")
        self.assertFalse(NullLlmClient().available())
        self.assertIsNone(NullLlmClient().chat("s", "u"))

    def test_advise_without_element_does_not_crash(self) -> None:
        advisor = Advisor(self.kb, llm=NullLlmClient(), lang="zh")
        advice = advisor.advise(None, make_state())
        self.assertIsInstance(advice, Advice)
        self.assertTrue(advice.body.strip())

    # -- language -----------------------------------------------------
    def test_languages_produce_different_bodies(self) -> None:
        element = make_element("View & Edit")
        state = make_state()
        zh = Advisor(self.kb, llm=NullLlmClient(), lang="zh").advise(element, state)
        en = Advisor(self.kb, llm=NullLlmClient(), lang="en").advise(element, state)
        self.assertNotEqual(zh.body, en.body)
        self.assertIn("声音编辑器显示波形", zh.body)
        self.assertNotIn("声音编辑器显示波形", en.body)
        self.assertIn("The sound editor shows the waveform", en.body)
        self.assertNotEqual(zh.headline, en.headline)

    def test_missing_language_falls_back_to_the_other(self) -> None:
        kb = FakeKB([FakeEntry(
            id="only-english",
            aliases=["Only English"],
            title_en="English title",
            title_zh="",
            what_en="English body",
            what_zh="",
            how_en="",
            how_zh="",
        )])
        advice = Advisor(kb, llm=NullLlmClient(), lang="zh").advise(
            make_element("Only English"), make_state()
        )
        self.assertIn("English body", advice.body)
        self.assertIn("English title", advice.headline)

    # -- context aware ------------------------------------------------
    def test_context_uses_only_real_state_fields(self) -> None:
        sound = make_sound("demo_vowel")
        state = make_state(objects=[sound], selected=[sound])
        advisor = Advisor(self.kb, llm=NullLlmClient(), lang="en")
        advice = advisor.advise(make_element("View & Edit"), state)
        self.assertIn("demo_vowel", advice.body)
        # nothing was invented: the state has no duration / rate / channels
        self.assertNotIn("duration", advice.body)
        self.assertNotIn("sampling rate", advice.body)

    def test_context_reports_details_that_exist(self) -> None:
        sound = make_sound("demo_vowel", duration=0.5, sampling_frequency=44100,
                           n_channels=1)
        state = make_state(objects=[sound], selected=[sound])
        advisor = Advisor(self.kb, llm=NullLlmClient(), lang="en")
        advice = advisor.advise(make_element("View & Edit"), state)
        self.assertIn("demo_vowel", advice.body)
        self.assertIn("0.5", advice.body)
        self.assertIn("44100", advice.body)

    def test_context_reads_details_from_raw(self) -> None:
        sound = make_sound("demo_vowel")
        state = make_state(
            objects=[sound],
            selected=[sound],
            raw={"objects": [{"id": 1, "type": "Sound", "name": "demo_vowel",
                              "duration": 1.25, "sampling_frequency": 48000,
                              "n_channels": 2}]},
        )
        advisor = Advisor(self.kb, llm=NullLlmClient(), lang="en")
        advice = advisor.advise(make_element("View & Edit"), state)
        self.assertIn("1.25", advice.body)
        self.assertIn("48000", advice.body)

    def test_to_textgrid_without_textgrid_warns(self) -> None:
        sound = make_sound("demo_vowel")
        state = make_state(objects=[sound], selected=[sound])
        advisor = Advisor(self.kb, llm=NullLlmClient(), lang="zh")
        advice = advisor.advise(make_element("To TextGrid..."), state)
        self.assertIn("还没有 TextGrid", advice.body)
        self.assertIn("选中一个 Sound", advice.body)

    def test_missing_source_object_is_named(self) -> None:
        state = make_state(objects=[], selected=[])
        advisor = Advisor(self.kb, llm=NullLlmClient(), lang="en")
        advice = advisor.advise(make_element("To Pitch..."), state)
        self.assertIn("Sound", advice.body)

    def test_unknown_control_still_gets_context_advice(self) -> None:
        # The control is not in the knowledge base, but the state is still
        # worth talking about.
        state = make_state(objects=[], selected=[])
        advisor = Advisor(self.kb, llm=NullLlmClient(), lang="en")
        advice = advisor.advise(make_element("Totally Unknown Button"), state)
        self.assertEqual(advice.source, "kb")
        self.assertIn("knowledge base has no entry", advice.body)

    def test_unknown_control_does_not_list_unrelated_entries(self) -> None:
        advisor = Advisor(self.kb, llm=NullLlmClient(), lang="en")
        advice = advisor.advise(make_element("Wobble the flux capacitor"), make_state())
        self.assertNotIn("Open the sound editor", advice.body)
        self.assertNotIn("Create a TextGrid from a Sound", advice.body)

    def test_open_editor_is_mentioned(self) -> None:
        state = make_state(objects=[], selected=[], editor_open=True,
                           editor_object="Sound demo_vowel")
        advisor = Advisor(self.kb, llm=NullLlmClient(), lang="zh")
        advice = advisor.advise(make_element("View & Edit"), state)
        self.assertIn("编辑器已打开", advice.body)
        self.assertIn("demo_vowel", advice.body)

    def test_no_state_means_no_state_talk(self) -> None:
        advisor = Advisor(self.kb, llm=NullLlmClient(), lang="zh")
        advice = advisor.advise(make_element("View & Edit"), None)
        self.assertNotIn("已选中", advice.body)
        self.assertNotIn("编辑器已打开", advice.body)

    # -- ask ----------------------------------------------------------
    def test_ask_lists_matched_entries(self) -> None:
        advisor = Advisor(self.kb, llm=NullLlmClient(), lang="en")
        advice = advisor.ask("How do I make a textgrid?")
        self.assertEqual(advice.source, "kb")
        self.assertIn("Create a TextGrid from a Sound", advice.body)
        self.assertTrue(advice.entries)

    def test_ask_with_llm_uses_both_sources(self) -> None:
        llm = FakeLlm(answer="Make a TextGrid with Annotate.")
        advisor = Advisor(self.kb, llm=llm, lang="en")
        advice = advisor.ask("How do I make a textgrid?")
        self.assertIn("llm", advice.source)
        self.assertIn("Make a TextGrid with Annotate.", advice.body)
        self.assertIn("Create a TextGrid from a Sound", advice.body)

    def test_ask_without_matches_still_answers(self) -> None:
        advisor = Advisor(self.kb, llm=NullLlmClient(), lang="zh")
        advice = advisor.ask("量子计算机的量子比特是什么？")
        self.assertEqual(advice.source, "kb")
        self.assertTrue(advice.body.strip())

    # -- status -------------------------------------------------------
    def test_status_reports_kb_size_and_llm_state(self) -> None:
        advisor = Advisor(self.kb, llm=NullLlmClient(), lang="zh")
        status = advisor.status()
        self.assertIn("3", status)
        self.assertIn("知识库", status)

        with_llm = Advisor(self.kb, llm=FakeLlm(), lang="zh")
        self.assertIn("已开启", with_llm.status())

    # -- state probe --------------------------------------------------
    def test_state_probe_is_used_when_no_state_given(self) -> None:
        class Probe:
            def __init__(self) -> None:
                self.calls = 0

            def snapshot(self, timeout: float = 3.0) -> Any:
                self.calls += 1
                sound = make_sound("probe_sound")
                return make_state(objects=[sound], selected=[sound])

        probe = Probe()
        advisor = Advisor(self.kb, state=probe, llm=NullLlmClient(), lang="en")
        advice = advisor.advise(make_element("View & Edit"))
        self.assertEqual(probe.calls, 1)
        self.assertIn("probe_sound", advice.body)

    def test_broken_probe_does_not_break_advice(self) -> None:
        class BrokenProbe:
            def snapshot(self, timeout: float = 3.0) -> Any:
                raise RuntimeError("no praat")

        advisor = Advisor(self.kb, state=BrokenProbe(), llm=NullLlmClient(), lang="zh")
        advice = advisor.advise(make_element("View & Edit"))
        self.assertIsInstance(advice, Advice)
        self.assertTrue(advice.body.strip())


# ----------------------------------------------------------------------
# llm tests
# ----------------------------------------------------------------------
class LlmTests(unittest.TestCase):
    def setUp(self) -> None:
        """A fake DSH credential store, so the fallback is testable."""

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        creds = Path(self._tmp.name) / ".credentials.yaml"
        creds.write_text(
            "version: 1\n"
            "records:\n"
            "  some-account:\n"
            "    kind: grant\n"
            "refs:\n"
            "  MINIMAX_CN_API_KEY: sk-test-from-dsh\n",
            encoding="utf-8",
        )
        self.env = {"PRAATAO_TEST_CREDS": str(creds)}

    def test_unconfigured_client_is_unavailable(self) -> None:
        client = LlmClient(LlmConfig())
        self.assertFalse(client.available())
        self.assertIsNone(client.chat("system", "user"))

    def test_config_from_env(self) -> None:
        config = LlmConfig.from_env({
            "PRAATAO_LLM_ENDPOINT": "https://api.deepseek.com/v1",
            "PRAATAO_LLM_MODEL": "deepseek-chat",
            "PRAATAO_LLM_API_KEY": "sk-test",
            "PRAATAO_LLM_BACKEND": "openai",
        })
        self.assertEqual(config.endpoint, "https://api.deepseek.com/v1")
        self.assertEqual(config.model, "deepseek-chat")
        self.assertEqual(config.backend, "openai")
        self.assertTrue(config.is_configured())
        self.assertEqual(config.chat_url(), "https://api.deepseek.com/v1/chat/completions")

    def test_ollama_config_from_env(self) -> None:
        config = LlmConfig.from_env({
            "PRAATAO_LLM_ENDPOINT": "http://localhost:11434",
            "PRAATAO_LLM_MODEL": "qwen2.5",
            "PRAATAO_LLM_BACKEND": "ollama",
        })
        self.assertEqual(config.backend, "ollama")
        self.assertEqual(config.chat_url(), "http://localhost:11434/api/chat")

    def test_chat_never_raises_on_network_error(self) -> None:
        client = LlmClient(LlmConfig(
            endpoint="http://127.0.0.1:9/v1", model="x", api_key="k"))
        self.assertTrue(client.available())
        self.assertIsNone(client.chat("system", "user", timeout=1.0))

    def test_describe_config(self) -> None:
        off = LlmClient(LlmConfig())
        self.assertIn("LLM", off.describe_config("en"))
        on = LlmClient(LlmConfig(endpoint="https://api.deepseek.com/v1",
                                 model="deepseek-chat", api_key="sk"))
        text = on.describe_config("en")
        self.assertIn("deepseek-chat", text)
        self.assertNotIn("sk", text)

    def test_default_client_is_offline_without_any_credential(self) -> None:
        """With neither the environment nor a DSH credential, stay offline.

        On a machine that *does* have a DSH credential the default client is
        of course configured, so the "no credential anywhere" case is
        exercised through the configuration object itself.
        """

        config = LlmConfig.from_env({}, dsh_fallback=False)
        self.assertFalse(config.is_configured())
        self.assertFalse(LlmClient(config).available())
        self.assertIn("LLM", NullLlmClient().describe_config("en"))
        self.assertIn("LLM", describe_config("en"))

    def test_dsh_credential_is_the_fallback(self) -> None:
        """Without any PRAATAO_* variable, the DSH credential is used."""

        creds = Path(self.env["PRAATAO_TEST_CREDS"])
        config = LlmConfig.from_env(
            {"PRAATAO_TEST_CREDS": str(creds)}, dsh_path=creds
        )
        self.assertEqual(config.source, "dsh")
        self.assertEqual(config.endpoint, "https://api.minimaxi.com/v1")
        self.assertEqual(config.model, "MiniMax-M3.1-Flash")
        self.assertEqual(config.image_model, "image-01")
        self.assertEqual(config.api_key, "sk-test-from-dsh")

    def test_env_wins_over_the_dsh_credential(self) -> None:
        creds = Path(self.env["PRAATAO_TEST_CREDS"])
        config = LlmConfig.from_env(
            {
                "PRAATAO_LLM_ENDPOINT": "https://example.test/v1",
                "PRAATAO_LLM_MODEL": "my-model",
                "PRAATAO_LLM_API_KEY": "sk-explicit",
            },
            dsh_path=creds,
        )
        self.assertEqual(config.source, "env")
        self.assertEqual(config.endpoint, "https://example.test/v1")
        self.assertEqual(config.api_key, "sk-explicit")

    def test_dsh_fallback_can_be_switched_off(self) -> None:
        creds = Path(self.env["PRAATAO_TEST_CREDS"])
        config = LlmConfig.from_env({}, dsh_fallback=False, dsh_path=creds)
        self.assertFalse(config.is_configured())
        self.assertEqual(config.source, "env")

    def test_vision_is_opt_in(self) -> None:
        """Images may only be sent to the model when the user says so."""

        creds = Path(self.env["PRAATAO_TEST_CREDS"])
        off = LlmConfig.from_env({}, dsh_path=creds)
        self.assertFalse(off.allow_vision)
        client = LlmClient(off)
        self.assertFalse(client.supports_vision())
        self.assertIsNone(client.chat_with_image("s", "u", []))

        on = LlmConfig.from_env(
            {"PRAATAO_VISION": "1"}, dsh_path=creds
        )
        self.assertTrue(on.allow_vision)
        self.assertTrue(LlmClient(on).supports_vision())

    def test_null_client_shares_the_interface(self) -> None:
        null = NullLlmClient()
        self.assertFalse(null.available())
        self.assertIsNone(null.chat("s", "u"))
        self.assertIsNone(null.chat_with_image("s", "u", []))
        self.assertIsNone(null.generate_image("draw a cat"))
        self.assertIsInstance(null, LlmClient)

    def test_image_generation_is_opt_in(self) -> None:
        """Drawing a picture costs money and time: it stays opt-in."""

        creds = Path(self.env["PRAATAO_TEST_CREDS"])
        off = LlmConfig.from_env({}, dsh_path=creds)
        self.assertFalse(off.allow_imagegen)
        self.assertFalse(LlmClient(off).supports_image_generation())

        on = LlmConfig.from_env({"PRAATAO_IMAGEGEN": "1"}, dsh_path=creds)
        self.assertTrue(on.allow_imagegen)
        self.assertTrue(LlmClient(on).supports_image_generation())


class ImageGenTests(unittest.TestCase):
    """The drawn teaching picture."""

    def setUp(self) -> None:
        self.pictures: list[bytes] = []

        class DrawingLlm(FakeLlm):
            def supports_image_generation(self) -> bool:
                return True

            def generate_image(self, prompt: str, **kwargs: Any) -> bytes | None:
                self.prompts = getattr(self, "prompts", [])
                self.prompts.append(prompt)
                return b"FAKE-PICTURE"

        self.llm = DrawingLlm()
        self.advisor = Advisor(FakeKB([]), llm=self.llm, lang="zh")

    def test_picture_is_drawn_after_the_answer(self) -> None:
        self.advisor.advise(
            make_element("Totally Unknown Button"),
            on_llm=lambda _advice: None,
            on_image=self.pictures.append,
        )
        # The model call and the picture call are both on worker threads.
        for _ in range(100):
            if self.pictures:
                break
            import time

            time.sleep(0.02)
        self.assertEqual(self.pictures, [b"FAKE-PICTURE"])
        prompt = getattr(self.llm, "prompts", [""])[0]
        self.assertIn("no text", prompt)
        self.assertIn("no letters", prompt)

    def test_no_picture_without_the_callback(self) -> None:
        advice = self.advisor.advise(
            make_element("Totally Unknown Button"),
            on_llm=lambda _advice: None,
        )
        self.assertTrue(advice.body)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
