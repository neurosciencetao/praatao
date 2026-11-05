"""Praat's drawing areas: where they are, what is in them, and what to say.

The earlier assumption that Praat's canvases are invisible to the
accessibility tree was wrong.  They are exposed as

.. code-block:: text

    [PaneControl] 'drawingArea'  cls='PraatDrawingArea1 Praat'  rect=(76, 143, 1880, 1008)

so the **geometry** of every waveform, spectrogram, pitch and formant view is
known exactly - which is all that is needed to look at it.

What the picture *means* is a different matter.  Two routes exist:

**Locally (always on, nothing leaves the machine).**
    A small image analysis says what the picture looks like (a spectrogram? a
    waveform? a sparse curve?), and the knowledge base explains that kind of
    view and what to do next.

**With the model (opt-in).**
    The picture is sent to a vision-capable model, which can read the axis
    labels, the cursor position and the legend, and say something specific:
    "your spectrogram only shows 0.8 seconds, so the window length is too
    long to see the formant movement".

Sending a Praat picture to a server can send a participant's voice with it,
so the vision route is **off unless the user turns it on**
(``PRAATAO_VISION=1``).  The local route never touches the network.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

try:  # pragma: no cover - Pillow is optional
    from PIL import Image, ImageGrab
except Exception:  # noqa: BLE001
    Image = None  # type: ignore[assignment]
    ImageGrab = None  # type: ignore[assignment]

from .uia import PraatUI, UiaWindow, _rect_contains, _safe_rect, _text

__all__ = [
    "CanvasRegion",
    "CanvasGuess",
    "CanvasSensor",
    "CANVAS_CLASSES",
]

#: Win32/UIA class names of Praat's drawing areas.
CANVAS_CLASSES = ("praatdrawingarea1 praat", "drawingarea")

#: The local classification, best effort.
KINDS = ("spectrogram", "waveform", "pitch", "formants", "intensity", "unknown")


@dataclass(frozen=True)
class CanvasRegion:
    """One drawing area of one Praat window."""

    hwnd: int  # hwnd of the *window* that owns the canvas
    canvas_hwnd: int
    window_title: str
    window_kind: str  # 'picture' | 'editor' | ...
    rect: tuple[int, int, int, int]  # screen pixels
    object_name: str  # e.g. 'demo_vowel'

    @property
    def width(self) -> int:
        return self.rect[2] - self.rect[0]

    @property
    def height(self) -> int:
        return self.rect[3] - self.rect[1]

    def contains(self, x: int, y: int) -> bool:
        return _rect_contains(self.rect, x, y)


@dataclass(frozen=True)
class CanvasGuess:
    """What the picture looks like, according to local statistics."""

    kind: str = "unknown"
    confidence: float = 0.0
    coloured: float = 0.0
    dark: float = 0.0
    bright: float = 0.0

    def is_spectrogram(self) -> bool:
        return self.kind == "spectrogram"


def _object_name(title: str) -> str:
    """The name of the object a window shows, without the list number.

    Praat titles its windows ``<number>. <object name>``, so
    ``'2. Sound demo_vowel'`` becomes ``'Sound demo_vowel'`` - the same
    text the Objects list shows.
    """

    text = (title or "").strip()
    if "." in text:
        head, _, tail = text.partition(". ")
        if head.strip().isdigit():
            text = tail.strip()
    if text.lower().startswith("praat picture"):
        return ""
    return text


class CanvasSensor:
    """Find Praat's drawing areas and look at them."""

    #: How long a region list stays valid, in seconds.
    CACHE_TTL = 1.0
    #: How long the slow route (the accessibility tree) is tried again when
    #: the fast route found nothing and no new Praat window appeared.
    SLOW_TTL = 30.0
    #: Longest edge of a captured picture sent to a model.
    MAX_IMAGE_EDGE = 768

    def __init__(self, ui: PraatUI | None = None) -> None:
        self.ui = ui if ui is not None else PraatUI()
        self._regions: list[CanvasRegion] = []
        self._cached_at: float = 0.0
        self._slow_at: float = 0.0
        self._slow_windows: tuple = ()

    # ------------------------------------------------------------------
    # finding the canvases
    # ------------------------------------------------------------------
    def regions(self, refresh: bool = False) -> list[CanvasRegion]:
        """Every drawing area Praat currently shows.

        The drawing areas are found through the Win32 window tree, which
        costs well under a millisecond.  The accessibility tree would
        answer the same question, but walking it costs about 90 ms, and
        that walk used to happen on the interface thread once a second:
        the pointer froze for a tenth of a second, again and again.

        Two things are cached here, and both have to be:

        * the **result**, also when it is empty.  Praat often shows no
          drawing area at all (while the Objects window is the only
          window open, for instance), and an empty answer that is not
          cached sends every single tick through the slow route.
        * the **slow route**: when the fast route finds nothing, the
          accessibility tree is only walked when a new Praat window
          appeared (a new window is the only thing that can bring a new
          drawing area) or after :data:`SLOW_TTL` seconds.
        """

        now = time.monotonic()
        if not refresh and self._cached_at and (now - self._cached_at) < self.CACHE_TTL:
            return self._regions

        windows = self._windows()
        found = self._regions_via_win32(windows)
        if not found and (
            refresh
            or self._window_key(windows) != self._slow_windows
            or (now - self._slow_at) > self.SLOW_TTL
        ):
            found = self._regions_via_uia(windows)
            self._slow_at = now
            self._slow_windows = self._window_key(windows)
        self._regions = found
        self._cached_at = now
        return found

    @staticmethod
    def _window_key(windows: Sequence[Any]) -> tuple:
        """Which Praat windows are there (and how big are they)."""

        return tuple(sorted((w.hwnd, tuple(w.rect)) for w in windows))

    def _windows(self) -> list[Any]:
        """Every Praat window, once each."""

        windows: list[Any] = []
        seen: set[int] = set()
        for window in self.ui.windows() + self.ui.editor_windows():
            if window is None or window.hwnd in seen:
                continue
            seen.add(window.hwnd)
            windows.append(window)
        return windows

    def _regions_via_win32(self, windows: Sequence[Any] | None = None) -> list[CanvasRegion]:
        """The drawing areas, read from the Win32 window tree."""

        if win32gui_is_none():
            return []
        import win32gui

        found: list[CanvasRegion] = []
        for window in (self._windows() if windows is None else windows):
            canvases: list[int] = []

            def _collect(hwnd: int, _extra: object) -> None:
                try:
                    class_name = (win32gui.GetClassName(hwnd) or "").strip().casefold()
                except Exception:
                    return
                if class_name in CANVAS_CLASSES:
                    canvases.append(hwnd)

            try:
                win32gui.EnumChildWindows(window.hwnd, _collect, None)
            except Exception:  # pragma: no cover - defensive
                continue
            for hwnd in canvases:
                try:
                    rect = tuple(int(v) for v in win32gui.GetWindowRect(hwnd))
                except Exception:
                    continue
                if rect[2] - rect[0] < 40 or rect[3] - rect[1] < 40:
                    continue
                found.append(
                    CanvasRegion(
                        hwnd=window.hwnd,
                        canvas_hwnd=hwnd,
                        window_title=window.title,
                        window_kind=window.kind,
                        rect=rect,  # type: ignore[arg-type]
                        object_name=_object_name(window.title),
                    )
                )
        return found

    def _regions_via_uia(self, windows: Sequence[Any] | None = None) -> list[CanvasRegion]:
        """The drawing areas, read from the accessibility tree (slow)."""

        found: list[CanvasRegion] = []
        for window in (self._windows() if windows is None else windows):
            control = self.ui._control_from_window(window)
            if control is None:
                continue
            for node, _depth in self.ui._iter_controls(control, max_depth=6):
                class_name = _text(node, "ClassName").strip().casefold()
                if class_name not in CANVAS_CLASSES:
                    continue
                rect = _safe_rect(node)
                if rect is None or rect[2] - rect[0] < 40 or rect[3] - rect[1] < 40:
                    continue
                found.append(
                    CanvasRegion(
                        hwnd=window.hwnd,
                        canvas_hwnd=window.hwnd,
                        window_title=window.title,
                        window_kind=window.kind,
                        rect=rect,
                        object_name=_object_name(window.title),
                    )
                )
        return found

    def region_at(self, x: int, y: int) -> CanvasRegion | None:
        """The drawing area under the screen point ``(x, y)``."""

        best: CanvasRegion | None = None
        best_area = 0
        for region in self.regions():
            if not region.contains(x, y):
                continue
            area = region.width * region.height
            if best is None or area < best_area:
                best, best_area = region, area
        return best

    # ------------------------------------------------------------------
    # looking at the picture
    # ------------------------------------------------------------------
    def capture(
        self,
        region: CanvasRegion,
        *,
        activate: bool = False,
        rect: tuple[int, int, int, int] | None = None,
    ) -> "Image.Image | None":
        """Grab the drawing area as a picture.

        The grab reads the *screen*, so a window that is covered by another
        window yields the picture of whatever is in front of it.  With
        ``activate=True`` the Praat window is brought to the front first -
        that is intrusive, so it is off by default and the caller should
        only capture a canvas that the user is actually looking at.

        A window that sticks out of the screen is cropped to what is
        really there: the rest of the rectangle is not on the screen and
        would come out black.  ``rect`` overrides the rectangle, so that a
        caller can leave out the part of the canvas that another window
        (the side panel, say) covers.
        """

        if ImageGrab is None or Image is None:
            return None
        if activate:
            self.ui._activate(_WindowShim(region.hwnd))
            time.sleep(0.35)
        bbox = self._visible_bbox(rect or region.rect)
        if bbox is None:
            return None
        try:
            shot = ImageGrab.grab(bbox=bbox, all_screens=True)
        except Exception:
            return None
        if shot is None:
            return None
        return self._shrink(shot)

    def classify_at(self, image: "Image.Image | None", y_fraction: float) -> CanvasGuess:
        """Classify the *row* the pointer is on, not the whole picture.

        Praat stacks several views in one picture: the waveform on top,
        then the spectrogram, then the pitch curve and the formants.  The
        pointer says which one the student means, so only that row is
        looked at.

        Praat draws the waveform in blue-green, the pitch curve in green,
        the formants in red and the intensity in blue.  That is what the
        row is told apart by.
        """

        if image is None:
            return CanvasGuess()
        try:
            import colorsys

            width, height = image.size
            band = max(4, int(height * 0.03))
            centre = int(max(0.0, min(1.0, y_fraction)) * height)
            top = max(0, centre - band)
            bottom = min(height, centre + band)
            if bottom <= top:
                return CanvasGuess()
            crop = image.crop((0, top, width, bottom)).convert("RGB")
        except Exception:
            return CanvasGuess()

        total = 0
        dark = 0
        bright = 0
        hues = {"red": 0, "green": 0, "blue": 0, "teal": 0}
        for r, g, b in crop.getdata():
            total += 1
            level = (r + g + b) / 3.0
            if level < 90:
                dark += 1
            elif level > 200:
                bright += 1
            h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
            if s > 0.3 and v > 0.3:
                deg = h * 360.0
                if deg < 20 or deg >= 330:
                    hues["red"] += 1
                elif deg < 160:
                    hues["green"] += 1
                elif deg < 200:
                    hues["teal"] += 1
                else:
                    hues["blue"] += 1
        if not total:
            return CanvasGuess()

        dark_ratio = dark / total
        coloured = sum(hues.values())
        coloured_ratio = coloured / total
        saturated = max(1, coloured)
        shares = {key: hues[key] / saturated for key in hues}

        if shares["teal"] > 0.75:
            # The waveform: a filled band, blue-green.
            return CanvasGuess("waveform", min(0.9, 0.45 + shares["teal"]),
                               coloured_ratio, dark_ratio, bright / total)
        if coloured_ratio < 0.002:
            # Nothing but white paper and axes: the student is not over
            # a curve at all.
            return CanvasGuess("unknown", 0.2, coloured_ratio, dark_ratio,
                               bright / total)
        if shares["red"] > 0.5:
            # The formants are red dots.
            return CanvasGuess("formants", min(0.9, 0.45 + shares["red"]),
                               coloured_ratio, dark_ratio, bright / total)
        if shares["blue"] > 0.25:
            # Praat draws the pitch curve (and the intensity curve) in
            # blue; the red dots are the formants.
            return CanvasGuess("pitch", min(0.9, 0.45 + shares["blue"]),
                               coloured_ratio, dark_ratio, bright / total)
        return CanvasGuess("unknown", 0.25, coloured_ratio, dark_ratio,
                           bright / total)

    def capture_and_classify(
        self,
        region: CanvasRegion,
        x: int,
        y: int,
        *,
        activate: bool = False,
        rect: tuple[int, int, int, int] | None = None,
    ) -> tuple["Image.Image | None", CanvasGuess]:
        """Grab the drawing area and say what is under the pointer."""

        if ImageGrab is None or Image is None:
            return None, CanvasGuess()
        if activate:
            self.ui._activate(_WindowShim(region.hwnd))
            time.sleep(0.35)
        bbox = self._visible_bbox(rect or region.rect)
        if bbox is None:
            return None, CanvasGuess()
        try:
            shot = ImageGrab.grab(bbox=bbox, all_screens=True)
        except Exception:
            return None, CanvasGuess()
        if shot is None:
            return None, CanvasGuess()
        # The row is classified on the *full* picture: a one-pixel curve
        # would disappear in the smaller picture that goes to the model.
        span = max(1, bbox[3] - bbox[1])
        fraction = (y - bbox[1]) / float(span)
        guess = self.classify_at(shot, fraction)
        return self._shrink(shot), guess

    def _visible_bbox(
        self, rect: tuple[int, int, int, int]
    ) -> tuple[int, int, int, int] | None:
        """The part of ``rect`` that is really on a screen."""

        try:
            import win32api

            for monitor in win32api.EnumDisplayMonitors():
                info = win32api.GetMonitorInfo(monitor[0])
                area = info["Monitor"]
                left = max(rect[0], area[0])
                top = max(rect[1], area[1])
                right = min(rect[2], area[2])
                bottom = min(rect[3], area[3])
                if right - left > 20 and bottom - top > 20:
                    return (left, top, right, bottom)
        except Exception:
            pass
        left, top, right, bottom = rect
        if right - left < 20 or bottom - top < 20:
            return None
        return rect

    def _shrink(self, image: "Image.Image") -> "Image.Image":
        """Scale a picture down so that it is cheap to send to a model."""

        width, height = image.size
        longest = max(width, height)
        if longest <= self.MAX_IMAGE_EDGE:
            return image
        factor = self.MAX_IMAGE_EDGE / float(longest)
        return image.resize((max(1, int(width * factor)), max(1, int(height * factor))))

    def is_visible(self, region: CanvasRegion) -> bool:
        """Is this drawing area actually the topmost thing at its centre?

        A canvas that is hidden behind another window cannot be captured
        meaningfully, so the caller can skip it instead of showing nonsense.
        """

        if win32gui_is_none():
            return True
        import win32gui

        left, top, right, bottom = region.rect
        cx, cy = (left + right) // 2, (top + bottom) // 2
        try:
            hwnd = win32gui.WindowFromPoint((cx, cy))
        except Exception:
            return True
        if not hwnd:
            return True
        try:
            pid = win32gui.GetWindowThreadProcessId(hwnd)[1]
            owner_pid = win32gui.GetWindowThreadProcessId(region.hwnd)[1]
        except Exception:
            return True
        return pid == owner_pid

    # ------------------------------------------------------------------
    # local classification
    # ------------------------------------------------------------------
    def classify(self, image: "Image.Image | None") -> CanvasGuess:
        """Say what the picture looks like, using pixel statistics only.

        The result is a *guess*, and the tutor words it that way.  It is
        cheap, offline and never leaves the machine.
        """

        if image is None:
            return CanvasGuess()
        try:
            small = image.convert("RGB").resize((160, 90))
            pixels = list(small.getdata())
        except Exception:
            return CanvasGuess()

        total = max(1, len(pixels))
        coloured = 0
        dark = 0
        bright = 0
        for r, g, b in pixels:
            if abs(r - g) > 22 or abs(g - b) > 22:
                coloured += 1
            level = (r + g + b) / 3.0
            if level < 90:
                dark += 1
            elif level > 200:
                bright += 1
        coloured_ratio = coloured / total
        dark_ratio = dark / total
        bright_ratio = bright / total

        if dark_ratio > 0.35:
            # A black canvas with a colour ramp on it: Praat's spectrogram.
            return CanvasGuess("spectrogram", 0.55 + 0.3 * coloured_ratio,
                               coloured_ratio, dark_ratio, bright_ratio)
        if bright_ratio > 0.55 and coloured_ratio > 0.08:
            # Bright background with coloured curves: pitch / formants.
            return CanvasGuess("pitch", 0.4, coloured_ratio, dark_ratio, bright_ratio)
        if bright_ratio > 0.55:
            # Bright background with a dense band in the middle: a waveform.
            return CanvasGuess("waveform", 0.45, coloured_ratio, dark_ratio, bright_ratio)
        return CanvasGuess("unknown", 0.2, coloured_ratio, dark_ratio, bright_ratio)


class _WindowShim:
    """Adapts a raw hwnd to the small interface :meth:`PraatUI._activate` needs."""

    def __init__(self, hwnd: int) -> None:
        self.hwnd = hwnd
        self.title = ""
        self.kind = ""


def win32gui_is_none() -> bool:
    """Is pywin32's ``win32gui`` unavailable?"""

    try:
        import win32gui  # noqa: F401
    except Exception:
        return True
    return False
