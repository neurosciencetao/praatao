# Sensing strategy: vision recognition or screen coordinates?

> **Decision record.** Answers the user question: *"should we use vision
> recognition or screen coordinates?"*
>
> **Status:** Accepted, 2026-11-04. Supersedes the ranking in
> [`01-architecture.md`](01-architecture.md) for the **hover** case.
> **Owner:** lead. **Evidence machine:** this workstation, Praat 6.4.12,
> Windows 11, Python 3.12.0.
>
> **ADR numbering.** This file inherits **ADR-001** (Electron/Tauri overlay +
> sendpraat probes), **ADR-002** (do not fork Praat yet) and **ADR-003**
> (Parselmouth is for offline demos only) from
> [`01-architecture.md`](01-architecture.md). The decision recorded here is
> **ADR-004**.

---

## Decision

**Use Windows UI Automation (option D) as the primary sensor for "which control
is under the cursor" and "where is it". Praat scripting via `--send` /
`sendpraat` (option F) stays as the semantic companion that answers "what does
Praat currently contain". Reject hardcoded relative coordinates (A), OCR (B) and
vision-language models (C) for the hover case.**

The hover path needs **UIA alone**. The selection-dependent button row
(`View & Edit`, `Play`, `Draw`, `Query`, ...) is exposed by UIA with exact
names and exact rectangles, so no probe and no relative anchor is needed to
find the control under the cursor.

Vision is kept as an **opt-in fallback**, for two narrow jobs: reading Praat's
own drawing areas (waveform, spectrogram, formants), and an explicit
"explain what is on my screen" help mode.

Measured on this machine, UIA gives us the answer in **1-5 ms** with exact
geometry and exact names, no inference, no cost, and nothing leaving the
machine. Vision would cost seconds and still not tell us that the widget under
the cursor is called `View & Edit`.

---

## 1. The problem

To answer *"what does the button under my mouse do?"*, Praatao needs two
independent facts:

| | Question | Needed for |
|---|----------|-----------|
| **(a) which** | Which control is under the cursor? | Lookup in the knowledge base, and the decision to show anything at all |
| **(b) where** | Where is that control on screen? | Drawing the highlight ring, and anchoring the hover card |

The two are not the same problem, and this is the source of most of the
confusion in the original question. Vision approaches try to answer both at
once, from pixels. Structured approaches answer (a) from *names* and (b) from
*geometry*.

---

## 2. Options considered

| # | Option | Gets (a) which | Gets (b) where | Verdict |
|---|--------|----------------|----------------|---------|
| **A** | Hardcoded / relative screen coordinates (what v0 did) | No | Yes, approximately | **Rejected for hover.** Breaks on DPI change, window resize, Praat version drift, translation. Acceptable only as a last-resort fallback anchor |
| **B** | Screenshot + OCR | No (fuzzy text) | Yes (bounding boxes) | **Rejected.** OCR on `View & Edit` vs `View && Edit` vs `View & Edit…` is a coin flip; OCR is also slow and needs a trained image |
| **C** | Screenshot + vision-language model | Fuzzily | Fuzzily | **Rejected for hover.** Non-deterministic, seconds of latency, per-token cost, sends lab screenshots off the machine. **Kept as an opt-in fallback** |
| **D** | **Windows UI Automation (accessibility tree)** | **Yes, exactly** | **Yes, exactly** | **Chosen as primary** |
| **E** | Fork Praat / patch Praat to emit UI events | Yes, ideally | Not directly | **Deferred.** Best fidelity, heaviest maintenance, and we should not need it: UIA already exposes the widget tree |
| **F** | Praat scripting (`--send`, `sendpraat`) | Semantic only ("a Sound is selected") | **No** | **Chosen as the semantic companion to D** |

The key observation about **F**: it senses *semantic* state, not GUI geometry.
`sendpraat` can tell us "a Sound called `demo_vowel` is selected"; it cannot
tell us where the *View & Edit* button is. The two are complementary, not
alternatives: **D answers the hover, F answers the context.**

---

## 3. Evidence measured on this machine

Everything in this section was measured on this workstation on **2026-11-04**,
against the Praat instance at `D:\Documents\Playground\praatao\Praat.exe`.
Raw artefacts: [`prototypes/v1/experiments/uia_probe_output.json`](../prototypes/v1/experiments/uia_probe_output.json)
and the ground truth already recorded in [`CONTRACTS.md`](CONTRACTS.md).

### 3.1 Environment

| Fact | Value |
|------|-------|
| Praat version | **6.4.12 (May 2 2024)** (`Praat.exe --version`) |
| UI Automation client | **`uiautomation` 2.0.18** (yinkaisheng), Python **3.12.0** |
| Win32 helper | `pywin32` (`win32gui`) |
| Praat GUI framework | Cross-platform layer with a **Windows Motif emulator** (`sys/motifEmulator.cpp`) that maps Motif widgets onto real Win32 `HWND`s |

**This is the crux.** Because the Motif emulator creates *real* Win32 child
windows, those windows are real HWNDs with real accessible names, and Windows
exposes them through the UI Automation tree. Praat's GUI is therefore
**automatable**, which is not obvious from the outside and is the single most
important fact in this document.

### 3.2 Window classes

| Window | Title | Win32 class |
|--------|-------|-------------|
| Objects | `Praat Objects` | `PraatShell1 Praat` |
| Picture | `Praat Picture` | `PraatChildWindow1 Praat` |
| Sound editor | `2. Sound demo_vowel` | `PraatChildWindow1 Praat` |

Note the editor title: it is the **object-list label** (`2. Sound demo_vowel`),
not the bare object name. Code that strips the `N. ` prefix (see
`normalize_name` in `CONTRACTS.md`) must handle this.

### 3.3 The Objects window, control by control

Full tree walk of the Objects window: **22 named nodes** with nothing selected,
**46 named nodes** with a Sound selected (see §3.4), walk time **0.037 s**
(0.092 s on a second run). Every button below was found **by name**, with an
exact screen rectangle:

| Control type | Name | Screen rect (L, T, R, B) |
|--------------|------|--------------------------|
| ButtonControl | `Rename...` | (26, 641, 108, 661) |
| ButtonControl | `Copy...` | (116, 641, 198, 661) |
| ButtonControl | `Inspect` | (26, 671, 108, 691) |
| ButtonControl | `Info` | (116, 671, 198, 691) |
| ButtonControl | `Remove` | (26, 701, 108, 721) |
| ListControl | `Objects:` | (18, 77, 288, 625) |
| TextControl | `Objects:` | (21, 56, 288, 72) |
| MenuItemControl | `Praat` | (18, 31, 59, 50) |
| MenuItemControl | `New` | (59, 31, 97, 50) |
| MenuItemControl | `Open` | (97, 31, 140, 50) |
| MenuItemControl | `Save` | (140, 31, 178, 50) |
| MenuItemControl | `Help` | (499, 31, 538, 50) |

Object-list rows are `ListItemControl`, named with the list index:
`1. Sound demo_vowel` at (19, 78, 287, 91), `2. Sound demo_vowel` at
(19, 91, 287, 104).

### 3.4 The selection-dependent button row: UIA's strongest feature

When a **Sound is selected**, Praat replaces the Objects window's fixed button
row with a selection-specific one. **UIA exposes that row completely**, with
exact names and exact rectangles. This is the clearest demonstration that the
Motif emulator's widget tree is faithfully mirrored into the accessibility
tree, and it is what makes a *pure UIA* hover possible.

Measured on this machine, with a Sound selected, the Objects window tree has
**46 named nodes**. The 24 nodes that are absent when nothing is selected are
exactly the selection-specific controls:

| Control type | Raw name (as UIA reports it) | Screen rect (L, T, R, B) |
|--------------|------------------------------|--------------------------|
| ButtonControl | `Sound help` | (298, 61, 533, 81) |
| ButtonControl | `View & Edit` | (298, 86, 533, 106) |
| ButtonControl | `Play` | (298, 111, 533, 131) |
| PaneControl | `rowColumn` | (298, 136, 533, 160) |
| ButtonControl | `'\u202f\u202f   Draw  >'` | (300, 138, 531, 158) |
| PaneControl | `rowColumn` | (298, 161, 533, 185) |
| ButtonControl | `'\u202f\u202f   Query  >'` | (300, 163, 531, 183) |
| PaneControl | `rowColumn` | (298, 186, 533, 210) |
| ButtonControl | `'\u202f\u202f   Modify  >'` | (300, 188, 531, 208) |
| PaneControl | `rowColumn` | (298, 211, 533, 235) |
| ButtonControl | `'\u202f\u202f   Annotate  >'` | (300, 213, 531, 233) |
| PaneControl | `rowColumn` | (298, 236, 533, 260) |
| ButtonControl | `'\u202f\u202f   Analyse periodicity  >'` | (300, 238, 531, 258) |
| PaneControl | `rowColumn` | (298, 261, 533, 285) |
| ButtonControl | `'\u202f\u202f   Analyse spectrum  >'` | (300, 263, 531, 283) |
| ButtonControl | `To Intensity...` | (298, 286, 533, 306) |
| PaneControl | `rowColumn` | (298, 311, 533, 335) |
| ButtonControl | `'\u202f\u202f   Manipulate  >'` | (300, 313, 531, 333) |
| PaneControl | `rowColumn` | (298, 336, 533, 360) |
| ButtonControl | `'\u202f\u202f   Convert  >'` | (300, 338, 531, 358) |
| PaneControl | `rowColumn` | (298, 361, 533, 385) |
| ButtonControl | `'\u202f\u202f   Filter  >'` | (300, 363, 531, 383) |
| PaneControl | `rowColumn` | (298, 386, 533, 410) |
| ButtonControl | `'\u202f\u202f   Combine  >'` | (300, 388, 531, 408) |

Two naming details the implementation must handle:

- Each dynamic button is wrapped in a `PaneControl` named `rowColumn` (a Motif
  row-column widget), so the tree is one level deeper than a flat button list.
- The raw names carry **two leading U+202F** (narrow no-break space)
  characters, then spaces, then the label, then spaces, then a trailing `>`.
  The exact raw name of the Draw button is `'\u202f\u202f   Draw  >'`.
  `normalize_name()` in [`CONTRACTS.md`](CONTRACTS.md) strips all of that.

**Consequence for the architecture: the hover path needs UIA alone.** No
`--send` probe and no relative anchor is required to find `View & Edit`, because
UIA reports it by name and gives its exact rectangle, in the same tree walk
that identifies the control under the cursor. The semantic probe (F) is still
useful for *context* (which Sound is selected, what is in the Objects list), but
it is not a prerequisite for the hover.

**Caveat, measured:** the node count is a function of Praat's UI state, not a
constant. The same window reports **46** named nodes with a Sound selected and
**22** with nothing selected (the 22-node tree is the 5 fixed buttons, the
object list and the menus). The tree must therefore be re-read when the
selection changes, and a "missing" button is not by itself evidence that UIA
failed. See §3.9 for the one state in which the row really does disappear.

### 3.5 Menus, and the shortcuts that come for free

Menu bar items are `MenuItemControl`. Opening a menu spawns a **separate
top-level `HWND` of class `#32768`** (the standard Win32 menu window), and its
items are readable as `MenuItemControl` with the keyboard shortcut embedded
after a **TAB**:

Objects window, `Open` menu (measured):

```
Read from file...\tCtrl-O
Open long sound file...\tCtrl-L
Read separate channels from sound file...
Read from special sound file
Read Table from tab-separated file...
...
```

Sound editor, `Spectrogram` menu (measured):

```
Show spectrogram
Spectrogram settings...
Advanced spectrogram settings...
▼ Query spectrogram:
      Get frequency at frequency cursor
      Get spectral power at cursor cross\tF7
▼ Select frequency:
      Move frequency cursor to...
▼ Draw spectogram to picture window:
      Paint visible spectrogram...
▼ Extract to objects window:
      Extract visible spectrogram
      View spectral slice\tCtrl-L
```

Two things follow. First, **keyboard shortcuts come for free**: we never have to
maintain a separate shortcut table, and the tip card can say *"or press
`Ctrl-L`"*. Second, the menu tree is a ready-made **lesson outline**: the
teaching content for "how do I show a spectrogram" maps one-to-one onto the
`Spectrogram` menu.

Two content notes for the content team: Praat's own menu text contains a typo
(`Draw spectogram to picture window:`), and the `▼` prefixes are submenu
markers that `normalize_name` must strip.

### 3.6 The Sound editor, which is the main learner surface

The editor window `2. Sound demo_vowel` (rect 68, 92, 1888, 1044) is fully
exposed: **29 named nodes**, walk time **0.034 s**.

| Control type | Names |
|--------------|-------|
| MenuItemControl | `File`, `Edit`, `Time`, `Play`, `Sound`, `Analyses`, `Spectrogram`, `Pitch`, `Intensity`, `Formants`, `Pulses`, `Help` |
| ButtonControl | `all`, `in`, `out`, `sel`, `bak` (the selection buttons) |
| ButtonControl | `Column left`, `Column right` (scrollbars) |
| CheckBoxControl | `Group` |
| PaneControl | `drawingArea` |

This is the payoff: the editor menus are *exactly* the concepts a phonetics
student is learning (`Spectrogram`, `Pitch`, `Intensity`, `Formants`, `Pulses`).
A hover card on `Formants` can explain formants, not just the button.

### 3.7 The Picture window

Menu bar items `File`, `Edit`, `Margins`, `World`, `Select`, `Pen`, `Font`,
`Help`, each with an exact rect. The `File` menu popup contains the drawing
commands (`Text...`, `Draw line...`, `Paint rectangle...`, `Axes...`,
`Measure`).

### 3.8 What UIA cannot see: the content of the drawing areas

This is the honest boundary of the approach, and it is small.

The waveform / spectrogram / formant canvases appear in the tree **only as a
generic `PaneControl` named `drawingArea`** (editor: rect 76, 143, 1880, 1008;
Picture window: rect 1276, 54, 2476, 1254). There is no name, no text, no
"there is a spectrogram here". The canvas is custom-drawn by Praat, so it has
no accessible representation of any kind.

**Correction (2026-11-04).** An earlier note in this file, and in the README,
said the drawing areas were *invisible* to UIA. That was wrong, and it
mattered: because the canvas *is* in the tree, with an exact rectangle, the
overlay can (a) highlight it, (b) grab a picture of it, and (c) ask a
vision-capable model what is in it. What UIA cannot give is the **content**
of the canvas, not its **position**.

Note also that the `drawingArea` rect is **not trustworthy as geometry**: in the
recorded dump the Picture window's `drawingArea` rect (1276, 54, 2476, 1254) is
**larger than the window itself** (1265, 0, 1903, 983). The Motif emulator
reports the scrollable canvas extent, not the visible region. Anything that
wants to highlight a region *inside* a canvas must use relative anchors and
must not trust this rect. For the same reason a screen grab of a canvas has
to be clipped to the monitors: the part of the rect that is off-screen comes
out black.

### 3.9 Latency, invocation, and the modal-dialog trap

**Hit test latency.** `uiautomation.ControlFromPoint(x, y)` is the hover
hot path. Measured median over 10 samples at five points inside the Sound
editor: **1.0 ms, 2.0 ms, 2.2 ms, 4.0 ms, 4.9 ms**. Every hit resolved to the
correct element (`form`, `drawingArea`, the window title, a `ListItemControl`).

**Invocation.** The UIA `Invoke` pattern works on Praat buttons. The
`View & Edit` button was invoked in an earlier run
(`prototypes/v1/experiments/uia_probe3.py`) and it **really opened the editor**;
the same pattern is used to dismiss Win32 message boxes.

### 3.9.1 The trap: a failing probe blocks, and leaves a message box behind

A *failing* Praat script raises a modal message box. Measured over three
repetitions on 2026-11-04, with the same failing script each time:

| Step | Result |
|------|--------|
| The `--send` call that carries the failing script | **Blocks.** Hung past 10 s in 2 of 3 runs; returned after 5.7 s in the third |
| Message box left on screen | Present in 2 of 3 runs; absent in the third |
| A **later** `--send` (trivial script) while the box is up | **Succeeds**: 0.14 - 0.21 s, marker file written, no extra Praat process |
| `ControlFromPoint` while the box is up | Still correct: `Rename...` in 4.8 ms, `form` in 2.4 ms |
| Objects tree while the box is up | Still readable, but rendered in its **"no selection"** form: **22** named nodes instead of **46** |
| `dismiss_dialogs()` | Closes the box (`closed=1`), after which Praat is responsive again |

Three conclusions, and the third one matters most:

1. **The failing probe itself blocks**, so every probe call needs a hard
   timeout. "Probe timed out" therefore means "the script I sent failed", which
   is a very different diagnosis from "Praat is busy".
2. **The message box does not freeze the script channel.** A later `--send`
   still runs and still writes its output. The box is a nuisance, not a lockout.
3. **The box changes the UI state that UIA sees.** While it is up, the Objects
   window renders the "no selection" button row, so `View & Edit` and the
   dynamic buttons are simply *not there* (22 nodes instead of 46). A hover
   that suddenly cannot find `View & Edit` is therefore a symptom of an open
   error box, not a UIA failure.

**Correction to an earlier draft of this document.** A previous version claimed
that a modal box "collapses the UIA tree to a single node" and that "every
later `--send` blocks until timeout". Both claims were artefacts of the
measuring script, not behaviour of Praat or of UIA: the first came from a
helper being called with its depth argument in the wrong position, the second
from observing only the *failing* call and assuming later calls behaved the
same. The table above is the corrected measurement.

### 3.9.2 Which window class is which

These three classes are easy to confuse and must not be mixed up:

| Class | What it is | Action for Praatao |
|-------|------------|---------------------|
| `#32768` | **Menu popup** window (Praat's `Open`, `Spectrogram`, ... menus) | Read its items; close it again. Never a dialog |
| `#32770` | **Win32 message box**: the "Message" box Praat pops for script and command errors | The modal that blocks `--send`. Dismiss it |
| `PraatShell1 Praat` | The **Objects window** (`Praat Objects`) | Never dismiss |
| `PraatChildWindow1 Praat` | Praat's own child windows: the **Picture window** and the **editors** (`2. Sound demo_vowel`) | Never dismiss. A class-prefix rule alone would wrongly target these |

**On the error box class.** On this machine the error box is consistently
**`#32770`** with title `Message`, holding an `OK` `ButtonControl` and the
error text in a `TextControl`. It was measured this way for both script-syntax
errors and Praat command errors, and reproduced after every dismissal. A
`PraatChildWindow1 Praat` error window has been reported from another
observation of this session, so the detector below accepts **both** classes and
filters on the title as well. Either way the title filter is what protects the
Picture window and the editors from being dismissed.

### 3.9.3 The mitigation: `dismiss_dialogs()`

A Python-side helper that unblocks Praat, implemented in
`praatao.sensors.praat_state` (see [`CONTRACTS.md`](CONTRACTS.md)):

```
For each visible top-level window owned by the Praat process:
    if class == "#32770"                      # Win32 message box  (measured)
    or class.startswith("Praat")              # Praat-drawn message window (reported)
        and title in ("Message", "Error"):
            find its "OK" ButtonControl and Invoke() it
```

Three rules that the implementation must respect:

1. **Never match on the class prefix alone.** `PraatChildWindow1 Praat` is the
   class of the Picture window and the editors. The title filter
   (`Message` / `Error`) is mandatory, otherwise Praatao would close the user's
   Picture window or sound editor.
2. **Never match class `#32768`.** That is a menu popup, not a dialog.
3. **Dismiss only after a timeout, never speculatively.** The helper is the
   *response* to a probe timeout, so that a healthy Praat is never disturbed.

### 3.10 Measured summary

| Measurement | Value | How |
|-------------|-------|-----|
| UIA hit test (`ControlFromPoint`) | **1.0 - 4.9 ms** (median) | 10 samples x 5 points in the Sound editor |
| UIA tree walk, Objects window (Sound selected) | **0.037 - 0.092 s**, **46** named nodes | `GetChildren` recursion, max depth 8 |
| UIA tree walk, Objects window (nothing selected) | same walk, **22** named nodes | same |
| UIA tree walk, Sound editor | **0.034 s**, **29** named nodes | same |
| Praat `--send` (successful, trivial script) | **0.14 - 0.21 s** | repeated |
| Praat `--send` (failing script) | **blocks**: hung past 10 s in 2 of 3 runs, 5.7 s in the third | 3 repetitions |
| Praat `--send` (later call, while an error box is up) | **still succeeds**, 0.14 - 0.21 s | 3 repetitions |
| Hit test while an error box is up | still **2.4 - 4.8 ms**, correct element | measured |
| `dismiss_dialogs()` | closes the box, Praat responsive again | verified |
| Popup menu enumeration | items readable with embedded shortcuts | `#32768` popup HWNDs |


---

## 4. Why UIA beats vision for the hover case

**Exact geometry.** The highlight ring lands on the button, every time, at any
DPI, at any window position. Vision gives an approximate box; UIA gives the
real one. A ring that is off by 4 pixels teaches the student the wrong thing.

**Exact names.** `View & Edit` is `View & Edit`. OCR will also produce
`View && Edit`, `View & Edit...`, `View & Edit` in a different font size, or
nothing at all when the button is clipped. The lookup key becomes a dictionary
hit instead of a fuzzy match.

**Zero latency, zero cost, offline.** 1-5 ms versus seconds. No API key, no
token bill, no network. University labs often have no or poor internet
(`00-concept.md`, design principle 5).

**Privacy.** Nothing about the student's screen leaves the machine, ever, in the
default path. A screenshot sent to a model is a screenshot of whatever else was
on screen at that moment.

**Keyboard shortcuts come for free.** The popup menu item names already carry
`Ctrl-O`, `Ctrl-L`, `F7`. We get "or press F7" without maintaining a shortcut
table.

**It is deterministic and testable.** `python -m unittest` can assert
"the element under (300, 400) in the Sound editor is named X". Vision assertions
are flaky by construction.

---

## 5. Where vision still earns its keep

Vision is the wrong tool for the hover, but it is not useless. Four honest
cases:

1. **Reading Praat's own drawing areas.** The waveform, spectrogram and formant
   views are custom-drawn and appear only as an anonymous `drawingArea`
   (§3.8). No accessibility API can tell you "the spectrogram is on" or "this
   region is the F2 formant". If we ever want to answer *"why does my
   spectrogram look like that?"*, vision (or a Parselmouth-based analysis of
   the audio, see [`09-python-for-praat.md`](09-python-for-praat.md)) is the
   only route. **This is the single strongest case for keeping a vision path.**
   *Implemented (2026-11-04):* the canvas sensor finds the drawing areas,
   grabs them, and (opt-in, `PRAATAO_VISION=1`) asks MiniMax M3.1 Flash to
   read the picture. Measured: 3 s for a small picture, 16 s for a
   1200x1200 spectrogram, so the picture is shrunk to 768 px first and the
   answer is delivered into the open card rather than awaited.
2. **"Is the student looking at the right thing?"** Screenshot QA in
   development: assert that the Objects window shows a Spectrogram panel.
3. **Cross-platform.** macOS and Linux have no UI Automation. If Praatao ever
   targets them, the sensing layer has to be replaced. Vision is the portable
   fallback (and on macOS, the accessibility API would be the equivalent of
   what we use here).
4. **"I am stuck" help mode.** An explicit, opt-in button: *"describe what you
   are looking at"*. Here latency and cost do not matter, and a picture is
   genuinely the right input. This must never fire automatically.
   *Implemented (2026-11-04):* the image model (`image-01`) can draw a small
   teaching diagram for a control the knowledge base does not cover, and the
   picture is dropped into the open card when it arrives (measured: 14 s).

The rule: **vision is opt-in and out of the hover path.** It never blocks a
hover card, and it never uploads a screenshot without an explicit user action.
The one exception to "never uploads" is the drawing-area route, which is why
it is behind `PRAATAO_VISION=1` and off by default: a Praat picture can be a
participant's voice.

---

## 6. Trade-off table

| Dimension | UIA (chosen) | OCR | Vision-language model | Hardcoded coordinates |
|-----------|--------------|-----|----------------------|----------------------|
| Geometry accuracy | Exact (measured rects) | Approximate | Approximate | Approximate, drifts |
| Name reliability | Exact string | Noisy | Fuzzy / paraphrased | n/a |
| Latency to answer | **1-5 ms** | ~100-500 ms | 1-10 s | 0 |
| Cost per event | Free | Free (local) | Per token | Free |
| Works offline | Yes | Yes | No | Yes |
| Data leaves the machine | No | No | **Yes** | No |
| Determinism | High | Medium | Low | High |
| Fails when | Praat not running, or the widget is not exposed | Low contrast, custom fonts, small text | Anything, unreliably | DPI change, resize, version drift, translation |
| Cross-platform | **No** (Windows only) | Yes | Yes | Yes |
| Can read Praat's canvas | **No** | No | **Yes** | No |

UIA loses exactly one row: it cannot read the drawing areas. Everything else
it wins, and it wins by orders of magnitude.

---

## 7. Residual risks and mitigations

| # | Risk | Severity | Evidence / likelihood | Mitigation |
|---|------|----------|----------------------|------------|
| 1 | **A failing probe leaves a modal error box on screen, and the box hides the selection-dependent button row.** A failing script or a failing Praat command raises a message box; the `--send` call that carries the failing script blocks, and while the box is up the Objects window renders its "no selection" row, so `View & Edit` and the dynamic buttons are absent from the tree. | **High** | Measured, 3 repetitions (§3.9.1) | Hard timeout on every probe. On timeout, run `dismiss_dialogs()`: enumerate visible windows owned by the Praat process whose class is `#32770` (or starts with `Praat`) **and** whose title is `Message` / `Error`, and Invoke their `OK` button. Never block the UI thread on a probe |
| 2 | **Motif-emulator UIA quirks.** The tree is an emulator artefact, not a designed accessibility contract. Names carry stray characters (two leading U+202F, a trailing `>`), dynamic buttons sit inside `rowColumn` panes, and list rows carry an `N. ` index. | High | Already observed (§3.3, §3.4) | `normalize_name()` in `CONTRACTS.md` strips U+202F/NBSP, trailing `>`, trailing `:`, and the `	<shortcut>` suffix. Never match on raw strings. Treat `rowColumn` as a container, not a target |
| 3 | **The button row is state-dependent.** The Objects window reports 46 named nodes with a Sound selected and 22 with nothing selected, so a "missing" button is usually a state change, not a UIA failure. | Medium | Measured (§3.4) | Re-read the tree when the selection changes; never cache the button set across a selection change; if a control is not found, check whether Praat has a modal box up (risk 1) before concluding anything |
| 4 | **Praat version drift.** A new Praat release renames buttons, moves them, changes the layout. | Medium | Certain over time | Pin tested versions (`docs/03-praat-integration.md`); a smoke test that asserts the presence of `View & Edit`, `Open`, `Praat Objects`; degrade to "no tip" rather than "wrong tip" |
| 5 | **Non-English Praat UI.** Button names become `查看和编辑` etc. | Medium | Certain for non-English installs | Match on `control_type` + **object type + state**, not on button text; localise the tip packs; ship an alias table per UI language; detect the Praat UI language at startup |
| 6 | **DPI and multi-monitor.** UIA rects are in physical pixels; a 150% display or a second monitor changes them. | Medium | Common in lab setups | Re-read rects every time the pointer moves to a different window; keep overlays per-display; never cache rects across a display change; use `GetDpiForWindow` if the overlay shows drift |
| 7 | **Popup menus are separate `HWND`s** (class `#32768`). They are not children of the window you opened them from, and they vanish on `ESC`. | Medium | Measured (§3.5) | Treat a `#32768` popup as a first-class window in the hit test; enumerate it on demand and close it again; never cache popup items. **Never treat `#32768` as a dialog** |
| 8 | **Window-class confusion.** `#32768` is a menu popup, `#32770` is the error message box, `PraatShell1 Praat` is the Objects window, `PraatChildWindow1 Praat` is the Picture window and the editors. | Medium | Measured (§3.9.2) | A `dismiss_dialogs()` that matches on the class prefix alone would close the user's Picture window or sound editor. The **title** filter (`Message` / `Error`) is mandatory, and the legal titles must be excluded explicitly |
| 9 | **Click-through overlay vs. UIA focus.** An always-on-top overlay window can steal UIA focus or appear in the tree. | Low | Not yet observed in v1 | Overlay windows are `WS_EX_TRANSPARENT | WS_EX_LAYERED`, `overrideredirect`, never focused; filter overlay-owned HWNDs out of the tree walk |
| 10 | **Praat is not running / has been upgraded under us.** | Low | Certain | Detect on every poll; go idle; re-detect periodically |
| 11 | **Vision fallback is unavailable offline.** | Low | Only if the user opts in | The fallback degrades to "not available" with a clear message; the curated KB path never depends on it |
| 12 | **Praat's own tooltip ("pip") steals the hit test and the clicks.** When the cursor rests on an object-list row, Praat opens a small tooltip window whose UIA name is `PipWindow`, whose Win32 class is `MouseInc` and whose window text is `PipWindow`. It sits **on top of** the row, and it can become the **foreground** window, in which case it swallows clicks entirely. | **High** | Measured while building v1: the tooltip made the object-list hit test return `PipWindow` instead of the list item, and it made every menu-bar click a no-op | The sensor treats a tooltip as "no control there" and resolves the real control geometrically against the window's named elements. Before any click, the sensor posts `ESC` **to the tooltip window itself** (a real ESC keystroke would land on the Objects window and clear Praat's object selection) and waits for it to go away. Never match a tooltip class as if it were a control |

## 8. ADR-004

> **Numbering.** This record continues the sequence in
> [`01-architecture.md`](01-architecture.md): **ADR-001** (Electron/Tauri
> overlay + sendpraat probes + YAML lessons), **ADR-002** (do not fork Praat
> until probes prove insufficient), **ADR-003** (Parselmouth is for offline
> demos only), and **ADR-004** (this record: the sensing strategy for the
> hover case).

### ADR-004: Sensing strategy for the hover case

**Status:** Accepted (2026-11-04)

**Context.** Praatao must answer *"the user is hovering over a control in
Praat: which one, and where is it?"* in order to show a tip anchored to that
control. The options were hardcoded relative coordinates, OCR, a
vision-language model, Windows UI Automation, forking Praat, and Praat's own
scripting interface.

**Decision.**

1. The **primary sensor is Windows UI Automation**, via the `uiautomation`
   package. It supplies both the control identity (exact name, control type,
   window) and the exact screen rectangle, measured at 1-5 ms per hit test on
   this machine. **The hover path needs UIA alone**: the selection-dependent
   button row (`View & Edit`, `Play`, `Draw`, `Query`, ...) is exposed by UIA
   with exact names and rects, so no probe and no relative anchor is needed to
   find it.
2. **Praat scripting (`--send` / `sendpraat`) is the semantic companion**, not
   an alternative. It answers "what does Praat contain" (objects, selection,
   open editor, TextGrid tiers), never "where is the button". It runs on a
   background thread and is never on the hover path, because a probe costs
   0.14-0.21 s and a failing one can block for a long time.
3. **Hardcoded coordinates (A), OCR (B) and vision (C) are rejected for the
   hover path.** Relative coordinates survive only as a fallback for regions
   *inside* Praat's custom-drawn canvases, where no accessibility element
   exists at all.
4. **Vision is retained as an opt-in fallback only**: for reading Praat's
   drawing areas, for development-time screenshot QA, for a future
   macOS/Linux port, and for an explicit "describe my screen" help mode. It
   never runs automatically, never blocks a hover card, and never uploads a
   screenshot without an explicit user action.
5. **A Praat error box is treated as a first-class failure mode.** Probes are
   hard-timeouted; on timeout, `dismiss_dialogs()` clears the modal message
   box and the probe is retried. The window classes must be told apart:
   `#32768` is a menu popup, `#32770` is the Win32 error message box,
   `PraatShell1 Praat` is the Objects window and `PraatChildWindow1 Praat` is
   the Picture window and the editors. Only a window whose title is `Message`
   or `Error` may be dismissed.
6. **Forking Praat (E) is deferred.** UIA exposes the full widget tree,
   including the dynamic buttons, so there is no sensing gap that a fork
   would close.

**Consequences.**

- v1 is **Windows-only**. A macOS/Linux port needs a different sensing layer
  (accessibility API, or eventually vision).
- The knowledge base must be keyed on **normalized** UIA names, with aliases
  and a keyword fallback (`CONTRACTS.md`).
- Lesson content can quote keyboard shortcuts for free, because popup menu item
  names embed them.
- We accept a dependence on a Praat-version-specific UI string set, mitigated by
  a version-pinned smoke test that fails loudly rather than silently showing
  the wrong tip.
- We accept that the Objects window's button set changes with the selection
  (46 named nodes with a Sound selected, 22 without), so the tree is re-read
  on selection change rather than cached.

**Measured basis.** §3 of this document, on this machine, 2026-11-04.
