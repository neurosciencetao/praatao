"""Unit tests for :mod:`praatao.sensors.canvas`.

The tests never touch a real Praat: the drawing areas are described by
stand-ins, and the pictures are drawn by hand.  What is tested is the
geometry logic (which rectangle belongs to which window) and the offline
classification, because those are the two parts that must never be wrong.
"""

from __future__ import annotations

import unittest

try:  # pragma: no cover - Pillow is optional
    from PIL import Image
except Exception:  # noqa: BLE001
    Image = None  # type: ignore[assignment]

from praatao.sensors.canvas import (
    CANVAS_CLASSES,
    CanvasGuess,
    CanvasRegion,
    CanvasSensor,
    _object_name,
)


class ObjectNameTests(unittest.TestCase):
    """The title of a Praat window says which object is on screen."""

    def test_numbered_object_title(self) -> None:
        self.assertEqual(_object_name("2. Sound demo_vowel"), "Sound demo_vowel")

    def test_plain_title_is_kept(self) -> None:
        self.assertEqual(_object_name("Sound demo_vowel"), "Sound demo_vowel")

    def test_picture_window_has_no_object(self) -> None:
        self.assertEqual(_object_name("Praat Picture"), "")

    def test_empty_title(self) -> None:
        self.assertEqual(_object_name(""), "")


class RegionTests(unittest.TestCase):
    """Which drawing area is under the cursor."""

    def make(self, rect, title="Praat Picture", kind="picture") -> CanvasRegion:
        return CanvasRegion(
            hwnd=1,
            canvas_hwnd=1,
            window_title=title,
            window_kind=kind,
            rect=rect,
            object_name=_object_name(title),
        )

    def test_contains(self) -> None:
        region = self.make((100, 200, 500, 400))
        self.assertTrue(region.contains(150, 250))
        self.assertFalse(region.contains(50, 250))
        self.assertFalse(region.contains(150, 150))

    def test_size(self) -> None:
        region = self.make((100, 200, 500, 400))
        self.assertEqual(region.width, 400)
        self.assertEqual(region.height, 200)

    def test_region_at_picks_the_smallest_match(self) -> None:
        """A picture inside an editor: the smaller one wins."""

        sensor = CanvasSensor.__new__(CanvasSensor)
        big = self.make((0, 0, 1000, 800), title="2. Sound demo_vowel", kind="editor")
        small = self.make((100, 100, 300, 300), title="Praat Picture", kind="picture")
        sensor._regions = [big, small]
        sensor._cached_at = 1e12  # never expires during the test
        found = sensor.region_at(200, 200)
        self.assertIsNotNone(found)
        self.assertEqual(found.window_kind, "picture")

    def test_region_at_returns_none_outside(self) -> None:
        sensor = CanvasSensor.__new__(CanvasSensor)
        sensor._regions = [self.make((100, 200, 500, 400))]
        sensor._cached_at = 1e12
        self.assertIsNone(sensor.region_at(10, 10))


class ClassifyTests(unittest.TestCase):
    """The offline guess at what a Praat picture shows."""

    def setUp(self) -> None:
        self.sensor = CanvasSensor.__new__(CanvasSensor)

    @unittest.skipIf(Image is None, "Pillow is not installed")
    def test_none_gives_unknown(self) -> None:
        guess = self.sensor.classify(None)
        self.assertEqual(guess.kind, "unknown")
        self.assertEqual(guess.confidence, 0.0)

    @unittest.skipIf(Image is None, "Pillow is not installed")
    def test_dark_picture_looks_like_a_spectrogram(self) -> None:
        image = Image.new("RGB", (200, 120), (10, 10, 12))
        for x in range(0, 200, 7):
            for y in range(40, 80):
                image.putpixel((x, y), (240, 120, 30))
        guess = self.sensor.classify(image)
        self.assertEqual(guess.kind, "spectrogram")
        self.assertTrue(guess.is_spectrogram())
        self.assertGreater(guess.dark, 0.35)

    @unittest.skipIf(Image is None, "Pillow is not installed")
    def test_bright_picture_with_curves_looks_like_a_pitch_view(self) -> None:
        image = Image.new("RGB", (200, 120), (250, 250, 250))
        for x in range(0, 200, 11):
            image.putpixel((x, 60), (220, 30, 30))
            image.putpixel((x, 61), (30, 180, 60))
        guess = self.sensor.classify(image)
        self.assertIn(guess.kind, ("pitch", "waveform"))
        self.assertGreater(guess.bright, 0.55)


class CanvasConstantsTests(unittest.TestCase):
    def test_class_names_are_lowercase(self) -> None:
        for name in CANVAS_CLASSES:
            self.assertEqual(name, name.casefold())

    def test_guess_defaults(self) -> None:
        guess = CanvasGuess()
        self.assertEqual(guess.kind, "unknown")
        self.assertFalse(guess.is_spectrogram())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
