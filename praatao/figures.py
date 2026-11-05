"""Teaching figures, rendered **offline** with Parselmouth.

Praatao normally reads the running Praat window (see
:mod:`praatao.sensors`).  This module is the other half: it produces the
pictures a teacher needs without Praat running at all.  Parselmouth
(``praat-parselmouth``) is a pybind11 binding into Praat's own C/C++ code,
so every number in these figures is exactly the number Praat would print.

What it renders, all from one sound file:

============  ==========================================================
kind          what the student sees
============  ==========================================================
waveform      the samples of the Sound, amplitude against time
spectrogram   the Gaussian-window spectrogram, frequency in Hz, time in s
pitch         the F0 contour, in Hz, with the unvoiced frames left out
formants      F1 and F2 over time, in Hz
intensity     the Intensity contour, in dB relative to the hearing threshold
============  ==========================================================

Usage::

    python -m praatao.figures                  # the demo vowel, all five
    python -m praatao.figures --kind pitch     # just one
    python -m praatao.figures --sound my.wav --out-dir somewhere/

The style follows the tool: Praat's warm orange on a cream card, dark
ink for the text, and no chart junk.  The figures are sized so that the
axis labels stay readable when the picture is scaled down into a tooltip.

This module never opens, sends to, or otherwise touches a running Praat.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Sequence

__all__ = [
    "ACCENT",
    "BACKGROUND",
    "TEXT",
    "FIGURE_KINDS",
    "FIGURE_DIR",
    "available_figures",
    "figure_path",
    "render_figure",
    "main",
]

# -- the visual language of Praatao -------------------------------------
ACCENT = "#E8590C"       # Praat's warm orange
BACKGROUND = "#FDF6EC"   # cream card
TEXT = "#1F2933"         # ink
MUTED = "#7A6A58"        # secondary text
LINE = "#E7D9C4"         # hairlines and grid

#: The five figures the coach knows about.
FIGURE_KINDS: tuple[str, ...] = (
    "waveform",
    "spectrogram",
    "pitch",
    "formants",
    "intensity",
)

#: Where the rendered PNG files live.
FIGURE_DIR = Path(__file__).resolve().parent / "figures"

#: The demo sound the figures are built from.
DEMO_SOUND = (
    Path(__file__).resolve().parents[1]
    / "prototypes" / "v0" / "assets" / "demo_vowel.wav"
)

#: Analysis settings, all of them Praat's own defaults.
SPECTROGRAM_WINDOW = 0.005      # s, Praat's "Window length"
SPECTROGRAM_MAX_FREQUENCY = 5000.0   # Hz, Praat's "Maximum frequency"
FORMANT_WINDOW = 0.025          # s, Praat's "Window length"
FORMANT_CEILING = 5500.0        # Hz, Praat's "Formant ceiling"
FORMANT_COUNT = 5               # Praat's "Max. number of formants"
PITCH_FLOOR = 75.0              # Hz, Praat's "Pitch floor"
PITCH_CEILING = 600.0           # Hz, Praat's "Pitch ceiling"


# ----------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------
def _import_pyplot() -> Any:
    """Import ``matplotlib.pyplot``, keeping PySide6 out of the way.

    PySide6 (through shiboken) inspects every module that is imported
    after it, and its inspection of the ``six.moves`` helper that
    dateutil uses trips over a module without source code.  The patch
    below is undone as soon as the import is done, so nothing else in
    the program sees it.
    """

    import inspect

    original = inspect.getfile

    def safe_getfile(obj: Any) -> Any:
        if inspect.ismodule(obj) and not hasattr(obj, "__file__"):
            raise OSError("built-in module")
        return original(obj)

    inspect.getfile = safe_getfile
    try:
        import matplotlib.pyplot as plt
    finally:
        inspect.getfile = original
    return plt


def _require() -> tuple[Any, Any, Any]:
    """Import the three heavy dependencies, with a readable error."""

    try:
        import matplotlib
    except Exception as exc:  # pragma: no cover - depends on the machine
        raise RuntimeError(
            "matplotlib is needed for the teaching figures: pip install matplotlib"
        ) from exc
    matplotlib.use("Agg")
    plt = _import_pyplot()
    import numpy as np
    import parselmouth
    return plt, np, parselmouth


def _style() -> dict[str, Any]:
    """The rcParams that make a figure look like the rest of Praatao."""

    return {
        "figure.facecolor": BACKGROUND,
        "figure.edgecolor": BACKGROUND,
        "savefig.facecolor": BACKGROUND,
        "axes.facecolor": BACKGROUND,
        "axes.edgecolor": LINE,
        "axes.labelcolor": TEXT,
        "axes.titlecolor": ACCENT,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.labelsize": 11,
        "axes.linewidth": 1.0,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": LINE,
        "grid.linewidth": 0.7,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "text.color": TEXT,
        "font.size": 11,
        "font.family": "sans-serif",
        "legend.frameon": False,
        "legend.fontsize": 10,
        "lines.solid_capstyle": "round",
    }


def _figure(title: str, xlabel: str, ylabel: str, width: float = 6.0,
            height: float = 3.0, dpi: int = 150):
    """A figure with Praatao's colours and no chart junk."""

    plt, _np, _parselmouth = _require()
    with plt.rc_context(_style()):
        fig, ax = plt.subplots(figsize=(width, height), dpi=dpi)
    ax.set_title(title, pad=8)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    return fig, ax


def _save(fig, out_path: Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=fig.dpi)
    import matplotlib.pyplot as plt
    plt.close(fig)
    return out_path


def _note(ax, text: str) -> None:
    """A small grey note in the top right corner of the plot.

    The note sits on a cream patch so that it stays readable over the
    dark part of a spectrogram too.
    """

    ax.text(0.985, 0.94, text, transform=ax.transAxes, ha="right", va="top",
            fontsize=9.5, color=MUTED,
            bbox=dict(facecolor=BACKGROUND, edgecolor="none", alpha=0.85,
                      pad=2.0))


# ----------------------------------------------------------------------
# The five figures
# ----------------------------------------------------------------------
def _waveform(sound, np, out_path: Path) -> Path:
    """The samples of the Sound, amplitude against time."""

    fig, ax = _figure("Waveform", "Time (s)", "Amplitude (Pa)")
    samples = np.asarray(sound.values[0], dtype=float)
    fs = float(sound.sampling_frequency)
    times = np.arange(samples.size) / fs

    # The Praat-style envelope: one column of the picture shows the whole
    # swing of the waveform in that slice of time.
    columns = 420
    edges = np.linspace(0, samples.size, columns + 1).astype(int)
    lows = np.array([samples[a:b].min() if b > a else 0.0
                     for a, b in zip(edges[:-1], edges[1:])])
    highs = np.array([samples[a:b].max() if b > a else 0.0
                      for a, b in zip(edges[:-1], edges[1:])])
    centres = (edges[:-1] + edges[1:]) / 2.0 / fs
    ax.fill_between(centres, lows, highs, color=ACCENT, linewidth=0.0,
                    alpha=0.9)
    ax.plot(centres, (lows + highs) / 2.0, color=ACCENT, linewidth=0.8)

    limit = max(1e-6, float(np.abs(samples).max()))
    ax.set_ylim(-limit * 1.08, limit * 1.08)
    ax.set_xlim(float(times[0]), float(times[-1]) + 1.0 / fs)
    _note(ax, f"{fs:.0f} Hz, {samples.size} samples, "
              f"{sound.get_total_duration():.2f} s")
    return _save(fig, out_path)


def _spectrogram(sound, np, out_path: Path) -> Path:
    """The spectrogram: frequency in Hz against time in seconds."""

    fig, ax = _figure("Spectrogram", "Time (s)", "Frequency (Hz)")
    spec = sound.to_spectrogram(
        window_length=SPECTROGRAM_WINDOW,
        maximum_frequency=SPECTROGRAM_MAX_FREQUENCY,
    )
    power = np.asarray(spec.as_array(), dtype=float)
    top = float(power.max())
    with np.errstate(divide="ignore"):
        decibels = 10.0 * np.log10(np.maximum(power, 1e-30) / top)
    decibels = np.clip(decibels, -70.0, 0.0)

    image = ax.imshow(
        decibels,
        origin="lower",
        aspect="auto",
        interpolation="nearest",
        extent=(float(spec.xmin), float(spec.xmax),
                float(spec.ymin), float(spec.ymax)),
        cmap="magma",
        vmin=-70.0,
        vmax=0.0,
    )
    ax.grid(False)
    ax.set_ylim(0.0, min(SPECTROGRAM_MAX_FREQUENCY, spec.ymax))
    bar = fig.colorbar(image, ax=ax, pad=0.02, fraction=0.045)
    bar.set_label("dB below the maximum", fontsize=9, color=MUTED)
    bar.ax.tick_params(labelsize=8, colors=MUTED)
    bar.outline.set_visible(False)
    _note(ax, f"Gaussian window {SPECTROGRAM_WINDOW * 1000:.0f} ms "
              f"(about {1.298 / SPECTROGRAM_WINDOW:.0f} Hz wide)")
    return _save(fig, out_path)


def _pitch(sound, np, out_path: Path) -> Path:
    """The F0 contour, in Hz."""

    fig, ax = _figure("Pitch contour (F0)", "Time (s)", "Fundamental frequency (Hz)")
    pitch = sound.to_pitch(pitch_floor=PITCH_FLOOR, pitch_ceiling=PITCH_CEILING)
    frames = pitch.get_number_of_frames()
    times = np.array([pitch.get_time_from_frame_number(i)
                      for i in range(1, frames + 1)])
    values = np.array([pitch.get_value_in_frame(i)
                       for i in range(1, frames + 1)])
    voiced = np.isfinite(values) & (values > 0.0)
    ax.plot(times[voiced], values[voiced], color=ACCENT, linewidth=2.0)

    if voiced.any():
        median = float(np.median(values[voiced]))
        ax.set_ylim(0.0, max(median * 1.8, PITCH_FLOOR * 2.0))
        _note(ax, f"median F0 {median:.0f} Hz, floor {PITCH_FLOOR:.0f}, "
                  f"ceiling {PITCH_CEILING:.0f} Hz")
    else:
        _note(ax, "no voiced frames")
    ax.set_xlim(float(sound.xmin), float(sound.xmax))
    return _save(fig, out_path)


def _formants(sound, np, out_path: Path) -> Path:
    """F1 and F2 over time, in Hz."""

    fig, ax = _figure("Formants (F1 and F2)", "Time (s)", "Frequency (Hz)")
    formants = sound.to_formant_burg(
        time_step=0.01,
        max_number_of_formants=FORMANT_COUNT,
        maximum_formant=FORMANT_CEILING,
        window_length=FORMANT_WINDOW,
    )
    times = np.linspace(float(sound.xmin), float(sound.xmax), 400)
    colours = (ACCENT, "#1B6CA8")
    medians = []
    for number, colour in ((1, colours[0]), (2, colours[1])):
        values = np.array([formants.get_value_at_time(number, float(t))
                           for t in times])
        ok = np.isfinite(values) & (values > 0.0)
        ax.plot(times[ok], values[ok], color=colour, linewidth=2.0)
        if ok.any():
            medians.append((number, float(np.median(values[ok]))))
            # Praat writes the name of the curve at its right end.
            ax.text(float(times[ok][-1]) + 0.01 * float(sound.xmax),
                    float(values[ok][-1]), f"F{number}", color=colour,
                    fontsize=11, va="center")

    ax.set_ylim(0.0, 3500.0)
    ax.set_xlim(float(sound.xmin), float(sound.xmax) * 1.06)
    if medians:
        _note(ax, "median " + ", ".join(f"F{n} {v:.0f} Hz" for n, v in medians))
    return _save(fig, out_path)


def _intensity(sound, np, out_path: Path) -> Path:
    """The Intensity contour, in dB relative to the hearing threshold."""

    fig, ax = _figure("Intensity", "Time (s)", "Intensity (dB SPL)")
    intensity = sound.to_intensity()
    times = np.array([intensity.get_x_of_column(i)
                      for i in range(1, intensity.nx + 1)])
    values = np.array(intensity.as_array())[0]
    ax.plot(times, values, color=ACCENT, linewidth=2.0)
    ax.fill_between(times, values, float(values.min()) - 1.0,
                    color=ACCENT, alpha=0.12)

    peak = float(values.max())
    ax.set_ylim(float(values.min()) - 1.0, peak + 3.0)
    ax.set_xlim(float(sound.xmin), float(sound.xmax))
    _note(ax, f"peak {peak:.1f} dB, 0 dB = the hearing threshold")
    return _save(fig, out_path)


_RENDERERS = {
    "waveform": _waveform,
    "spectrogram": _spectrogram,
    "pitch": _pitch,
    "formants": _formants,
    "intensity": _intensity,
}


# ----------------------------------------------------------------------
# The public entry points
# ----------------------------------------------------------------------
def render_figure(kind: str, sound_path: str | Path, out_path: str | Path,
                  **options: Any) -> Path:
    """Render one teaching figure and return the path of the PNG.

    ``kind`` is one of :data:`FIGURE_KINDS`.  ``sound_path`` is any sound
    file Parselmouth can read.  ``out_path`` is where the PNG goes; its
    parent folder is created if needed.
    """

    if kind not in _RENDERERS:
        raise ValueError(
            f"unknown figure {kind!r}; expected one of {', '.join(FIGURE_KINDS)}"
        )
    _plt, np, parselmouth = _require()
    sound = parselmouth.Sound(str(sound_path))
    return _RENDERERS[kind](sound, np, Path(out_path))


def available_figures() -> list[str]:
    """The kinds of figure that have actually been rendered.

    The coach uses this to decide whether it may offer a picture: a kind
    that is not in the list has no PNG on disk yet.
    """

    if not FIGURE_DIR.is_dir():
        return []
    found = []
    for kind in FIGURE_KINDS:
        if (FIGURE_DIR / f"{kind}.png").is_file():
            found.append(kind)
    return found


def figure_path(kind: str) -> Path | None:
    """The PNG of one figure, or ``None`` when it has not been rendered.

    The path is returned even when the file is missing, so that a caller
    can tell "no such kind" from "not rendered yet": ``None`` means the
    kind is unknown.
    """

    if kind not in FIGURE_KINDS:
        return None
    return FIGURE_DIR / f"{kind}.png"


def main(argv: Sequence[str] | None = None) -> int:
    """Render the figures for one sound file."""

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sound", default=str(DEMO_SOUND),
                        help="the sound file to analyse")
    parser.add_argument("--out-dir", default=str(FIGURE_DIR),
                        help="where the PNG files go")
    parser.add_argument("--kind", action="append", choices=list(FIGURE_KINDS),
                        help="render only this kind (may be repeated)")
    args = parser.parse_args(argv)

    sound_path = Path(args.sound)
    if not sound_path.is_file():
        print(f"no such sound file: {sound_path}", file=sys.stderr)
        return 2
    out_dir = Path(args.out_dir)
    kinds = args.kind or list(FIGURE_KINDS)

    for kind in kinds:
        out_path = out_dir / f"{kind}.png"
        render_figure(kind, sound_path, out_path)
        print(f"{kind:<13} -> {out_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
