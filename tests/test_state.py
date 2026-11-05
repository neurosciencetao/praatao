"""Tests for praatao.sensors.praat_state.

Unit tests never need Praat; live tests are skipped automatically when no
Praat GUI is running.

Run with::

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import os
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from praatao.sensors.praat_state import (  # noqa: E402
    PROBE_DIR,
    SNAPSHOT_PROBE,
    PraatObject,
    PraatState,
    PraatStateProbe,
    decode_probe_bytes,
    parse_editor_title,
    parse_object_list_item,
    parse_probe_output,
    praat_available,
    split_full_name,
    state_from_windows,
)

# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

#: A probe output as written by praatao/probes/snapshot.praat.
SAMPLE_PROBE = (
    "V\t6.4.12\r\n"
    "N\t2\r\n"
    "S\t1\tSound demo_vowel\r\n"
    "S\t2\tTextGrid marks_tones\r\n"
    "A\t0.8\t16000\t1\t0\t0.8\r\n"
    "T\t2\r\n"
    "I\t1\tmarks\r\n"
    "I\t2\ttones\r\n"
    "E\r\n"
)


class TestProbeParsing(unittest.TestCase):
    """Parsing of the tab-separated probe output."""

    def test_version_and_selection(self) -> None:
        parsed = parse_probe_output(SAMPLE_PROBE)
        self.assertEqual(parsed["version"], "6.4.12")
        self.assertTrue(parsed["complete"])
        self.assertEqual(len(parsed["selected"]), 2)
        self.assertEqual(parsed["selected_count"], 2)

    def test_selected_objects(self) -> None:
        parsed = parse_probe_output(SAMPLE_PROBE)
        first, second = parsed["selected"]
        self.assertIsInstance(first, PraatObject)
        self.assertEqual((first.id, first.type, first.name), (1, "Sound", "demo_vowel"))
        self.assertEqual((second.id, second.type, second.name), (2, "TextGrid", "marks_tones"))

    def test_tiers(self) -> None:
        parsed = parse_probe_output(SAMPLE_PROBE)
        self.assertEqual(parsed["tiers"], ["marks", "tones"])
        self.assertEqual(parsed["tier_count"], 2)

    def test_attributes(self) -> None:
        parsed = parse_probe_output(SAMPLE_PROBE)
        attrs = parsed["attributes"]
        self.assertAlmostEqual(attrs["duration"], 0.8)
        self.assertAlmostEqual(attrs["sampling_frequency"], 16000.0)
        self.assertEqual(attrs["channels"], 1)
        self.assertAlmostEqual(attrs["end_time"], 0.8)

    def test_incomplete_probe_is_tolerated(self) -> None:
        parsed = parse_probe_output("V\t6.4.12\r\nN\t0\r\n")
        self.assertFalse(parsed["complete"])
        self.assertEqual(parsed["selected"], [])
        self.assertEqual(parsed["version"], "6.4.12")

    def test_garbage_does_not_raise(self) -> None:
        parsed = parse_probe_output("nonsense\r\nS\tnotanumber\r\nS\t\t\r\n\t\t\r\n")
        self.assertEqual(parsed["selected"], [])

    def test_escapes_are_undone(self) -> None:
        parsed = parse_probe_output("S\t3\tSound a\\tb\\nc\\\\d\r\n")
        obj = parsed["selected"][0]
        self.assertEqual(obj.name, "a\tb\nc\\d")

    def test_empty_input(self) -> None:
        parsed = parse_probe_output("")
        self.assertEqual(parsed["version"], None)
        self.assertEqual(parsed["selected"], [])


class TestNameParsing(unittest.TestCase):
    """Splitting Praat full names and editor window titles."""

    def test_split_full_name(self) -> None:
        self.assertEqual(split_full_name("Sound demo_vowel"), ("Sound", "demo_vowel"))
        self.assertEqual(split_full_name("TextGrid marks_tones"), ("TextGrid", "marks_tones"))
        self.assertEqual(split_full_name("Sound my file.wav"), ("Sound", "my file.wav"))
        self.assertEqual(split_full_name("Sound"), ("Sound", ""))

    def test_parse_editor_title(self) -> None:
        self.assertEqual(parse_editor_title("2. Sound demo_vowel"), "Sound demo_vowel")
        self.assertEqual(parse_editor_title("1. TextGrid marks_tones"), "TextGrid marks_tones")
        self.assertEqual(parse_editor_title("12. Pitch vowels"), "Pitch vowels")

    def test_parse_editor_title_rejects_other_titles(self) -> None:
        self.assertIsNone(parse_editor_title("Praat Objects"))
        self.assertIsNone(parse_editor_title("Praat Picture"))
        self.assertIsNone(parse_editor_title(""))
        self.assertIsNone(parse_editor_title("Sound demo_vowel"))

    def test_parse_object_list_item(self) -> None:
        obj = parse_object_list_item("1. Sound demo_vowel")
        assert obj is not None
        self.assertEqual((obj.id, obj.type, obj.name), (1, "Sound", "demo_vowel"))
        self.assertIsNone(parse_object_list_item("Objects:"))


class TestQuickState(unittest.TestCase):
    """The window-title-only fast path."""

    def test_empty_window_list(self) -> None:
        state = state_from_windows([])
        self.assertFalse(state.running)
        self.assertFalse(state.editor_open)
        self.assertIsNone(state.editor_object)
        self.assertEqual(state.objects, [])
        self.assertEqual(state.selected, [])
        self.assertEqual(state.selected_types, [])
        self.assertEqual(state.selected_of("Sound"), [])

    def test_objects_window_only(self) -> None:
        state = state_from_windows([(1, "PraatShell1 Praat", "Praat Objects")])
        self.assertTrue(state.running)
        self.assertFalse(state.editor_open)
        self.assertIsNone(state.editor_object)

    def test_editor_window(self) -> None:
        state = state_from_windows(
            [
                (1, "PraatShell1 Praat", "Praat Objects"),
                (2, "PraatChildWindow1 Praat", "2. Sound demo_vowel"),
            ]
        )
        self.assertTrue(state.running)
        self.assertTrue(state.editor_open)
        self.assertEqual(state.editor_object, "Sound demo_vowel")

    def test_picture_window_is_not_an_editor(self) -> None:
        state = state_from_windows(
            [
                (1, "PraatShell1 Praat", "Praat Objects"),
                (3, "PraatChildWindow1 Praat", "Praat Picture"),
            ]
        )
        self.assertTrue(state.running)
        self.assertFalse(state.editor_open)

    def test_editor_window_alone_means_praat_runs(self) -> None:
        state = state_from_windows([(2, "PraatChildWindow1 Praat", "2. Sound demo_vowel")])
        self.assertTrue(state.running)
        self.assertTrue(state.editor_open)


class TestStateModel(unittest.TestCase):
    """The PraatState helpers."""

    def test_selected_types_and_selected_of(self) -> None:
        state = PraatState(
            running=True,
            version="6.4.12",
            objects=[
                PraatObject(1, "Sound", "demo_vowel"),
                PraatObject(2, "TextGrid", "marks"),
            ],
            selected=[
                PraatObject(1, "Sound", "demo_vowel"),
                PraatObject(2, "TextGrid", "marks"),
            ],
            editor_open=True,
            editor_object="Sound demo_vowel",
            textgrid_tiers=["marks"],
        )
        self.assertEqual(state.selected_types, ["Sound", "TextGrid"])
        self.assertEqual([o.id for o in state.selected_of("Sound")], [1])
        self.assertEqual([o.id for o in state.selected_of("TextGrid")], [2])
        self.assertEqual(state.selected_of("Pitch"), [])


class TestEncoding(unittest.TestCase):
    """Praat writes ANSI for ASCII and UTF-16 as soon as non-ASCII appears."""

    def test_ascii(self) -> None:
        self.assertEqual(decode_probe_bytes(b"V\t6.4.12\r\n"), "V\t6.4.12\r\n")

    def test_utf8(self) -> None:
        self.assertEqual(decode_probe_bytes("V\t6.4.12\r\n".encode("utf-8")), "V\t6.4.12\r\n")

    def test_utf16_with_bom(self) -> None:
        data = "V\t6.4.12\r\n".encode("utf-16-le")
        self.assertEqual(decode_probe_bytes(b"\xff\xfe" + data), "V\t6.4.12\r\n")

    def test_praat_utf16_bom_is_big_endian_marker(self) -> None:
        # Praat 6.4.12 on Windows writes FE FF but little-endian payload.
        data = "V\t6.4.12\r\n".encode("utf-16-le")
        self.assertEqual(decode_probe_bytes(b"\xfe\xff" + data), "V\t6.4.12\r\n")

    def test_ansi_fallback(self) -> None:
        self.assertIn("é", decode_probe_bytes("café".encode("cp1252")))


class TestPackagedProbe(unittest.TestCase):
    """The packaged probe template must exist and stay read-only."""

    def test_probe_template_exists(self) -> None:
        self.assertTrue(PROBE_DIR.is_dir(), PROBE_DIR)
        self.assertTrue(SNAPSHOT_PROBE.is_file(), SNAPSHOT_PROBE)

    def test_probe_template_has_placeholder(self) -> None:
        text = SNAPSHOT_PROBE.read_text(encoding="utf-8")
        self.assertIn("@OUT@", text)

    def test_probe_template_never_selects(self) -> None:
        text = SNAPSHOT_PROBE.read_text(encoding="utf-8")
        for forbidden in ("selectObject", "plusObject", "minusObject", "Remove"):
            self.assertNotIn(forbidden, text, forbidden)


# ---------------------------------------------------------------------------
# live tests
# ---------------------------------------------------------------------------


@unittest.skipUnless(praat_available(), "Praat not running")
class TestLiveProbe(unittest.TestCase):
    """Live tests against the running Praat instance."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.probe = PraatStateProbe()

    def test_snapshot_reports_running_and_sound(self) -> None:
        state = self.probe.snapshot(timeout=5.0)
        self.assertIsNone(state.error, state.error)
        self.assertTrue(state.running)
        self.assertTrue(state.version)
        self.assertTrue(state.objects, "no objects found")
        self.assertIn("Sound", [obj.type for obj in state.objects])

    def test_snapshot_objects_are_populated(self) -> None:
        state = self.probe.snapshot(timeout=5.0)
        self.assertTrue(state.objects)
        for obj in state.objects:
            self.assertIsInstance(obj, PraatObject)
            self.assertGreater(obj.id, 0)
            self.assertTrue(obj.type)

    def test_selected_of_sound(self) -> None:
        state = self.probe.snapshot(timeout=5.0)
        self.assertIsInstance(state.selected_of("Sound"), list)
        self.assertEqual(
            len(state.selected_of("Sound")),
            len([o for o in state.selected if o.type == "Sound"]),
        )

    def test_quick_is_fast_and_sees_the_editor(self) -> None:
        start = time.perf_counter()
        state = self.probe.quick()
        elapsed = (time.perf_counter() - start) * 1000.0
        self.assertLess(elapsed, 50.0, f"quick() took {elapsed:.1f} ms")
        self.assertTrue(state.running)
        if not state.editor_open:
            self.skipTest("no editor window is open in Praat")
        self.assertTrue(state.editor_object)

    def test_fast_reads_the_objects_window_without_a_script(self) -> None:
        """``fast()`` may not run a Praat script.

        A script closes whatever menu the user has open, so the hot path
        reads the Objects window through UI Automation instead.
        """

        calls: list[str] = []
        original = PraatStateProbe.send

        def spy(self, script, timeout=10.0):  # noqa: ANN001
            calls.append(str(script))
            return original(self, script, timeout)

        PraatStateProbe.send = spy  # type: ignore[method-assign]
        try:
            state = self.probe.fast()
        finally:
            PraatStateProbe.send = original  # type: ignore[method-assign]
        self.assertEqual(calls, [], "fast() ran a Praat script")
        self.assertTrue(state.running)
        self.assertTrue(state.objects, "no objects found")
        self.assertIn("Sound", [obj.type for obj in state.objects])
        self.assertTrue(state.selected, "no selected object found")
        self.assertTrue(state.version)

    def test_fast_is_fast_enough_for_the_hover_loop(self) -> None:
        start = time.perf_counter()
        self.probe.fast()
        elapsed = (time.perf_counter() - start) * 1000.0
        self.assertLess(elapsed, 400.0, f"fast() took {elapsed:.1f} ms")

    def test_send_runs_a_script(self) -> None:
        folder = Path(os.environ.get("TEMP", "."))
        script = folder / "praatao_selftest.praat"
        marker = folder / "praatao_selftest.txt"
        script.write_text(
            'appendFileLine: "%s", "ok"\n' % str(marker).replace("\\", "/"),
            encoding="utf-8",
        )
        try:
            self.assertTrue(self.probe.send(script, timeout=10.0))
        finally:
            for path in (script, marker):
                try:
                    path.unlink()
                except OSError:
                    pass

    def test_send_accepts_script_text(self) -> None:
        marker = Path(os.environ.get("TEMP", ".")) / "praatao_selftest_text.txt"
        text = 'appendFileLine: "%s", "ok"\n' % str(marker).replace("\\", "/")
        try:
            self.assertTrue(self.probe.send(text, timeout=10.0))
        finally:
            try:
                marker.unlink()
            except OSError:
                pass

    def test_send_of_missing_file_returns_false(self) -> None:
        missing = Path(os.environ.get("TEMP", ".")) / "praatao_does_not_exist.praat"
        self.assertFalse(self.probe.send(missing, timeout=2.0))

    def test_probe_never_raises(self) -> None:
        for call in (
            lambda: self.probe.snapshot(timeout=0.2),
            lambda: self.probe.quick(),
            lambda: self.probe.send("", timeout=1.0),
        ):
            try:
                call()
            except Exception as exc:  # pragma: no cover - the point of the test
                self.fail(f"probe raised {exc!r}")

    def test_dismiss_dialogs_is_harmless(self) -> None:
        self.assertGreaterEqual(self.probe.dismiss_dialogs(), 0)


@unittest.skipUnless(
    os.environ.get("PRAATAO_TEST_DIALOG_RECOVERY"),
    "set PRAATAO_TEST_DIALOG_RECOVERY=1 to run the dialog-recovery test",
)
class TestDialogRecovery(unittest.TestCase):
    """A failing Praat script must not leave Praat stuck."""

    def test_broken_script_leaves_praat_usable(self) -> None:
        """A failing Praat script must not leave Praat stuck."""
        probe = PraatStateProbe()
        broken = Path(os.environ.get("TEMP", ".")) / "praatao_broken.praat"
        broken.write_text("NoSuchCommandHere: 1\n", encoding="utf-8")
        try:
            # The launcher may or may not time out, depending on how Praat
            # reports the error; what matters is that Praat stays usable.
            probe.send(broken, timeout=3.0)
            time.sleep(0.4)
            probe.dismiss_dialogs()
            time.sleep(0.3)
            state = probe.snapshot(timeout=8.0)
            self.assertIsNone(state.error, state.error)
            self.assertTrue(state.running)
            self.assertTrue(state.objects)
        finally:
            try:
                broken.unlink()
            except OSError:
                pass


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
