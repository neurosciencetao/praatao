"""Lesson steps for Praatao v0 — shaped by common Praat beginner pitfalls."""

from __future__ import annotations

from dataclasses import dataclass

from praat_bridge import PraatState


@dataclass
class Step:
    id: str
    title: str
    tip_short: str
    tip_long: str
    why_common: str
    action_hint: str


STEPS: list[Step] = [
    Step(
        id="start-praat",
        title="Start Praat",
        tip_short="Launch Praat so you see the Objects and Picture windows.",
        tip_long=(
            "Praat is not one window. Beginners mostly use:\n"
            "• Objects — your Sounds, TextGrids, etc.\n"
            "• Picture — for publication figures\n"
            "• View & Edit — waveform / spectrogram editor\n\n"
            "Praatao watches Praat windows and your selection, then suggests the next click."
        ),
        why_common="People open Praat and freeze because two empty windows look unrelated.",
        action_hint="Click “Launch Praat”, or start Praat yourself.",
    ),
    Step(
        id="load-sound",
        title="Load a sound file",
        tip_short="Open → Read from file… (or use Load demo sound).",
        tip_long=(
            "For ordinary lab recordings use Read from file… — this creates a Sound object.\n\n"
            "Avoid Open long sound file… unless the file is huge; LongSound behaves differently "
            "and confuses beginners.\n\n"
            "After loading, you should see something like “Sound demo_vowel” in Objects."
        ),
        why_common="Menus mix Open / Read / LongSound; students pick the wrong one and get stuck.",
        action_hint="Use the button below, or Praat menu Open → Read from file…",
    ),
    Step(
        id="select-sound",
        title="Select the Sound",
        tip_short="Click the Sound row in the Objects list so it is highlighted.",
        tip_long=(
            "The buttons on the right (View & Edit, Annotate, …) are dynamic: "
            "they depend on what is selected.\n\n"
            "If the right panel looks empty or wrong, you usually have nothing selected "
            "(or the wrong object type)."
        ),
        why_common="Dynamic menus make Praat feel broken when selection is empty.",
        action_hint="Click the Sound object once in Objects.",
    ),
    Step(
        id="view-edit",
        title="Open View & Edit",
        tip_short="With the Sound selected, click View & Edit on the right.",
        tip_long=(
            "This opens the Sound editor: waveform on top, analyses (spectrogram, pitch…) below.\n\n"
            "Many settings live in the editor menus (Spectrum, Pitch, Formant), "
            "not in the Objects window — a frequent source of “where did that button go?”."
        ),
        why_common="Users look for spectrogram controls in Objects instead of the editor.",
        action_hint="Click View & Edit in Praat’s Objects window.",
    ),
    Step(
        id="spectrogram",
        title="See a clear spectrogram",
        tip_short=(
            "If you already see a grey spectrogram under the waveform, you are done here — "
            "click Continue. Otherwise zoom in / adjust Spectrum → Spectrogram settings."
        ),
        tip_long=(
            "Common spectrogram pitfalls:\n"
            "• Too long a visible window → Praat may hide analyses (zoom in / View → Show analyses).\n"
            "• Washed-out grey → lower Dynamic range (often try ~40–50 dB) under "
            "Spectrum → Spectrogram settings…\n"
            "• Window length ~0.005 s ≈ broadband (formants); ~0.03 s ≈ narrowband (harmonics).\n\n"
            "You can also toggle Pitch / Formant overlays off to reduce clutter "
            "(Pitch → Show pitch, Formant → Show formants)."
        ),
        why_common="Tutorials constantly warn about dynamic range, zoom length, and cluttered overlays.",
        action_hint="When the spectrogram looks OK, click Continue →",
    ),
    Step(
        id="bonus-textgrid",
        title="Bonus: TextGrid gotcha",
        tip_short="To annotate: create TextGrid, then select Sound + TextGrid together before View & Edit.",
        tip_long=(
            "Famous Praat gotcha (many tutorials call this out):\n"
            "1) Select Sound → Annotate → To TextGrid…\n"
            "2) Multi-select both Sound and TextGrid (Ctrl+click)\n"
            "3) Click View & Edit — not “View & Edit alone” on only the TextGrid\n\n"
            "When labeling: type in the white text field at the top of the editor, "
            "not by trying to edit the yellow tier strip directly "
            "(students yell at Praat for this constantly)."
        ),
        why_common="Single-select TextGrid + wrong View button; typing into the yellow tier.",
        action_hint="Optional — try when you are ready to annotate.",
    ),
]


def match_step(state: PraatState, manual_advance: set[str]) -> Step:
    """Pick the first incomplete step given Praat state + manual confirms."""

    if not state.running:
        return STEPS[0]

    # Editor open ⇒ sound exists and View & Edit already done
    if state.editor_open:
        if "spectrogram" in manual_advance:
            return STEPS[5]
        return STEPS[4]

    if not state.has_sound:
        return STEPS[1]

    if state.has_sound and not state.sound_selected:
        return STEPS[2]

    return STEPS[3]


def step_index(step: Step) -> int:
    return next(i for i, s in enumerate(STEPS) if s.id == step.id)
