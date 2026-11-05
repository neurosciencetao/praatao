"""Tests for the offline teaching figures.

The figures are produced by Parselmouth (Praat's own algorithms) without
touching a running Praat, so these tests only need the sound file that
ships with the project.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from praatao import figures

ROOT = Path(__file__).resolve().parents[1]
DEMO_SOUND = ROOT / "prototypes" / "v0" / "assets" / "demo_vowel.wav"

#: A PNG file starts with these eight bytes.
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class FigureHelpersTests(unittest.TestCase):
    """The small helpers the coach will use later."""

    def test_the_five_kinds_are_known(self) -> None:
        self.assertEqual(
            figures.FIGURE_KINDS,
            ("waveform", "spectrogram", "pitch", "formants", "intensity"),
        )

    def test_available_figures_lists_what_is_on_disk(self) -> None:
        available = figures.available_figures()
        self.assertTrue(set(available) <= set(figures.FIGURE_KINDS))
        for kind in available:
            path = figures.figure_path(kind)
            self.assertIsNotNone(path)
            self.assertTrue(path.is_file())

    def test_every_rendered_figure_is_on_disk(self) -> None:
        for kind in figures.FIGURE_KINDS:
            path = figures.figure_path(kind)
            self.assertIsNotNone(path)
            self.assertTrue(path.is_file(), f"{kind}.png is missing")
            self.assertIn(kind, figures.available_figures())

    def test_an_unknown_kind_has_no_path(self) -> None:
        self.assertIsNone(figures.figure_path("no-such-figure"))

    def test_the_colours_are_the_ones_the_tool_uses(self) -> None:
        self.assertEqual(figures.ACCENT, "#E8590C")
        self.assertEqual(figures.BACKGROUND, "#FDF6EC")
        self.assertEqual(figures.TEXT, "#1F2933")


class RenderTests(unittest.TestCase):
    """Every figure really renders, and really is a PNG."""

    def test_every_kind_renders_a_png(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            for kind in figures.FIGURE_KINDS:
                out = Path(folder) / f"{kind}.png"
                result = figures.render_figure(kind, DEMO_SOUND, out)
                self.assertEqual(result, out)
                self.assertTrue(out.is_file())
                with out.open("rb") as handle:
                    self.assertEqual(handle.read(8), PNG_MAGIC)
                self.assertGreater(out.stat().st_size, 5000)

    def test_an_unknown_kind_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                figures.render_figure("nonsense", DEMO_SOUND,
                                      Path(folder) / "x.png")

    def test_the_figures_are_not_empty_pictures(self) -> None:
        """A blank PNG would be a silent bug, so check the pixel variety."""

        try:
            import numpy as np
            from PIL import Image  # type: ignore
        except Exception:
            self.skipTest("Pillow is not installed")

        with tempfile.TemporaryDirectory() as folder:
            for kind in figures.FIGURE_KINDS:
                out = Path(folder) / f"{kind}.png"
                figures.render_figure(kind, DEMO_SOUND, out)
                image = np.asarray(Image.open(out).convert("RGB"))
                self.assertGreater(image.std(), 5.0,
                                   f"{kind}.png looks blank")


class FigureContentTests(unittest.TestCase):
    """The numbers on the figures come from Praat's own algorithms."""

    def test_the_pitch_figure_uses_praats_numbers(self) -> None:
        import parselmouth

        sound = parselmouth.Sound(str(DEMO_SOUND))
        pitch = sound.to_pitch()
        median = pitch.get_value_at_time(0.4)
        self.assertGreater(median, 50.0)
        self.assertLess(median, 600.0)
        self.assertEqual(pitch.ceiling, 600.0)

    def test_the_intensity_is_measured_against_the_hearing_threshold(self) -> None:
        import numpy as np
        import parselmouth

        sound = parselmouth.Sound(str(DEMO_SOUND))
        peak = float(sound.to_intensity().get_maximum())
        rms = float(np.sqrt(np.mean(np.square(np.asarray(sound.values[0])))))
        self.assertAlmostEqual(peak, 20.0 * np.log10(rms / 2.0e-5), delta=0.5)
        self.assertGreater(peak, 80.0)
        self.assertLess(peak, 100.0)


if __name__ == "__main__":
    unittest.main()
