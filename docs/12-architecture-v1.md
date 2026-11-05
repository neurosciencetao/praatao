# Praatao v1 architecture

> What is actually being built, as of 2026-11-04.
>
> **Interfaces:** [`CONTRACTS.md`](CONTRACTS.md) is the single source of truth
> for module APIs. This document describes the *shape* of the system and does
> not restate every signature.
> **Sensing decision:** [`10-sensing-strategy.md`](10-sensing-strategy.md) (ADR-002).
> **Package survey:** [`09-python-for-praat.md`](09-python-for-praat.md).

---

## 1. What v1 is

A **Windows-only companion process** that sits beside Praat and explains it.
The user hovers a control in Praat; Praatao shows a short card next to the
cursor and draws a ring around the control. A side panel runs a linear lesson
through a task ("open a sound, show a spectrogram, measure duration"), and an
optional, opt-in LLM can answer free-text questions.

Two design commitments shape everything below:

1. **The offline curated knowledge base is the primary path.** Labs often have
   no reliable network, so the explanation for a control must be available
   locally, in Chinese and English, with no network call. The LLM is an
   *optional expansion*, never a dependency.
2. **Praat stays the source of truth.** Praatao observes Praat. It does not
   re-implement acoustic analysis and does not drive Praat on the user's
   behalf (except in an explicit, user-requested "show me" demo).

---

## 2. Layers and module map

```
                    mouse  ──────────────┐
                     │                   │
                     ▼                   │
        ┌────────────────────────┐       │
        │  praatao.sensors.uia   │       │  what is under the cursor?
        │  (sensors/uia.py)      │       │  name + control type + exact rect
        └───────────┬────────────┘       │
                    │                    │
   Praat.exe ──►    │   ┌────────────────┴──────────────┐
   (--send probe) ─┴──►│  praatao.sensors.praat_state   │
                       │  (sensors/praat_state.py)     │  what does Praat contain?
                       │  PraatState                   │  objects, selection, tiers
                       └───────────────┬───────────────┘
                                       │
                                       ▼
        ┌──────────────────────────────────────────────────┐
        │  praatao.tutor.kb        (tutor/kb.py)           │  what does this
        │  praatao.tutor.lessons   (tutor/lessons.py)      │  control MEAN?
        │  praatao.tutor.advisor   (tutor/advisor.py)  ──► │  → Advice
        │  praatao.tutor.llm       (tutor/llm.py)         │  (optional, off)
        └───────────────────────┬──────────────────────────┘
                                │  Advice
                                ▼
        ┌──────────────────────────────────────────────────┐
        │  praatao.ui.hover      (ui/hover.py)             │  how do we say it?
        │  praatao.ui.spotlight  (ui/spotlight.py)         │
        │  praatao.ui.panel      (ui/panel.py)             │
        │  praatao.ui.overlay    (ui/overlay.py)  win32   │
        │  praatao.ui.hotkeys    (ui/hotkeys.py)          │
        └──────────────────────────────────────────────────┘

        content:  praatao/content/elements.yaml
                  praatao/content/lessons/*.yaml
```

**Hard layer boundaries** (from [`CONTRACTS.md`](CONTRACTS.md)):

- `ui/` must **not** import from `sensors/`. The UI receives plain data.
- `sensors/` must **not** import from `tutor/` or `ui/`.
- `tutor/` may read `sensors/` types, but only as data.

This is what keeps the knowledge base testable without a running Praat, and
what keeps the UI testable without a running Praat.

### 2.1 Module status

Status as of 2026-11-04 (files present in the working tree).

| Module | Path | Owner | Status | What it does |
|--------|------|-------|--------|--------------|
| Paths | `praatao/paths.py` | lead | **done** | `ROOT`, `PRAAT_EXE`, `CONTENT_DIR`, `ELEMENTS_FILE`, `LESSONS_DIR`, `STATE_DIR`, `ensure_state_dir()` |
| UIA sensor | `praatao/sensors/uia.py` | uia | **done** | `normalize_name`, `classify_window`, `Element`, `UiaWindow`, `PraatUI` (windows, objects/picture/editor windows, `window_at_point`, `tree`, `element_at_point`, `find`, `find_all`, `invoke`, `open_menu`), `praat_available()` |
| State sensor | `praatao/sensors/praat_state.py` | state | **done** | `PraatObject`, `PraatState`, `PraatStateProbe` (`send`, `snapshot`, `quick`), plus `split_full_name`, `parse_editor_title`, `parse_probe_output`, `state_from_windows`. Verified working against a live Praat: object list, selected objects and editor-open state all come back |
| Knowledge base | `praatao/tutor/kb.py` | lead | **done** | `KnowledgeEntry`, `KnowledgeBase` (`load`, `entries`, `by_id`, `lookup`, `search`, `stats`), `normalize_key`, `load_default()` |
| Lessons | `praatao/tutor/lessons.py` | content + lead | **done** | `Highlight`, `LessonStep`, `Lesson`, `LessonLibrary`, `LessonRunner` (`start`, `next_step`, `advance`, `sync`, `progress`), `step_matches` |
| Advisor | `praatao/tutor/advisor.py` | lead | **done** | `Advice`, `Advisor` (`advise`, `advise_canvas`, `ask`, `status`); KB first, LLM as fallback, answers delivered asynchronously through `on_llm` / `on_image` |
| LLM client | `praatao/tutor/llm.py` | ai | **done** | `LlmConfig` (from env, with a DSH-credential fallback), `LlmClient` (chat, chat-with-image, image generation), `NullLlmClient`, `default_llm_client` |
| Canvas sensor | `praatao/sensors/canvas.py` | lead | **done** | `CanvasRegion`, `CanvasGuess`, `CanvasSensor` (`regions`, `region_at`, `capture`, `classify`) |
| Hover card (Tk) | `praatao/ui/hover.py` | lead | **done** | `HoverCard.show / hide / set_pinned / is_visible / geometry` |
| Hover card (Qt) | `praatao/ui/qt/hover.py` | lead | **done** | `QtHoverCard.show / update_body / set_image / set_pinned / is_visible / geometry`, `body_to_html` |
| Spotlight | `praatao/ui/spotlight.py` | lead | **done** | `Spotlight.show(rect) / hide` |
| Spotlight (Qt) | `praatao/ui/qt/spotlight.py` | lead | **done** | `QtSpotlight.show(rect) / hide / is_visible` |
| Side panel | `praatao/ui/panel.py` | lead | **done** | `SidePanel.set_lessons / set_lesson / set_state / set_answer / toggle` |
| Side panel (Qt) | `praatao/ui/qt/panel.py` | lead | **done** | `QtSidePanel`, same interface as the Tk one |
| Qt host | `praatao/ui/qt/host.py` | lead | **done** | `QtHost` (event loop, `after`, thread bridge), `qt_available()` |
| Overlay helpers | `praatao/ui/overlay.py` | lead | **done** | `set_click_through`, `set_no_activate`, `keep_on_top`, `cursor_pos`, `screen_size`, `clamp_rect` |
| Hotkeys | `praatao/ui/hotkeys.py` | lead | **done** | `Hotkeys.poll()` via `GetAsyncKeyState`, no extra dependencies |
| Content packs | `praatao/content/` | content | **done** | `elements.yaml` (**288** bilingual entries, 352 aliases) + `elements/*.yaml` (fragments per topic) + `lessons/*.yaml` (6 packs, 49 steps) + `index.yaml`. Authoring guide: `docs/13-content-guide.md`, checkers: `tools/check_elements.py`, `tools/check_lessons.py`, merge: `tools/merge_elements.py` |
| Launcher | `run.py` (root) | lead | **done** | wires the runtime loop together; tolerates a half-built checkout (each sensor import is guarded); `--ui qt|tk` chooses the front-end |
| Entry point | `Start-Praatao.cmd` (root) + `tools/make_shortcut.py` | lead | **done** | the desktop shortcut the student clicks: starts Praat when it is not running, then the coach; the script writes the `.lnk` (desktop and start menu), `Ctrl+Alt+X` stops the coach again |
| Settings | `praatao/settings.py` + `praatao/ui/qt/settings.py` | lead | **done** | the student's own choices: language, whether the model may be used, whether a picture of the drawing area may be sent. Stored in `%LOCALAPPDATA%\praatao\settings.json`, applied at once, opened with `Ctrl+Alt+S` |
| Beginner launcher | `praatao/launcher.py` | lead | **done** | `ensure_praat()` (start Praat and bring it to front), `Toast` (the greeting window), `Tray` (the icon in the system tray, where the panel, the settings and the way out live), `no_console()` (detach from the console window), `log_line()` (the banner goes to `%LOCALAPPDATA%\praatao\coach.log` when nobody can see the console) |
| Packaged build | `tools/packaging/Praatao.spec` + `tools/packaging/build.py` | lead | **done** | PyInstaller, windowed and onedir: `dist/Praatao/Praatao.exe` starts without a console window, `Praat.exe` sits next to it, and the shortcut points at it |
| Offline figures | `praatao/figures.py` + `praatao/figures/` | content | **done** | teaching figures rendered with **Parselmouth** (Praat's own algorithms, no running Praat involved): waveform, spectrogram, pitch, formants, intensity. `available_figures()` and `figure_path(kind)` are the door for the card |
| The board | `docs/architecture-board.html` | lead | **done** | one page that shows how the data flows, with the measured numbers (see also `docs/15-performance.md`) |

**Note on the shell.** v1 was first implemented with **Python stdlib Tk plus
Win32 extended window styles** (`WS_EX_NOACTIVATE` for focus stealing, Tk's
`-transparentcolor` for the spotlight's transparent hole), not the
Electron/Tauri shell proposed in [`01-architecture.md`](01-architecture.md)
ADR-001. This formally supersedes the "Electron/Tauri" half of ADR-001: see
the addendum in that file, **ADR-005**.

**Note on the Qt front-end (2026-11-04).** The Tk card is click-through (so
that Praat keeps receiving the clicks), which means it can never have a pin
button, and it cannot hold a picture. The card was therefore rebuilt with
**PySide6**: a frameless, translucent, rounded window with a soft shadow, a
title, a pin button, a close button, styled section headings and room for a
picture. The Tk implementation stays as a fallback and is selected
automatically when PySide6 is missing. Two Qt details cost real debugging
time:

- A `QGraphicsDropShadowEffect` makes the compositor draw the window through
  a different path, and the text on screen then does not match what Qt draws
  itself. The shadow is painted by hand instead.
- The card is a `Qt.Tool` window that never takes focus, so a resize does
  not reliably invalidate the pixels on screen: `repaint()` (not `update()`)
  is needed after the height is measured.

One implementation note that cost real debugging time: **Tk rebuilds the HWND
when a withdrawn toplevel is deiconified**, so every extended-window-style bit
must be applied *after* the window is mapped, not in the constructor. Setting
`WS_EX_LAYERED` by hand on a window that Tk has not configured makes it render
invisible, so the layer flag is left to Tk's own `-transparentcolor` support.

**Who owns the mouse (2026-11-04).** The application, not the card, decides
what a click means. Windows gives the first click on an *inactive* window to
activating that window, so a pin button inside a tool window that never takes
focus would never see its first click. The application polls the mouse anyway,
so it hit-tests the point itself: over the pin button → pin, over the close
button → close, over the card → dismiss, anywhere else → the user is working
in Praat, so dismiss (unless the card is pinned).

Three things that taking the acceptance screenshots forced into the open:

* **The mouse button is watched every 10 ms, not every 45 ms.** The main tick
  runs at 45 ms and does a UI Automation hit test; a quick click can be over
  before the tick comes round, and then the click is simply lost. The button
  state is read by its own cheap timer.
* **The pointer being on our own card is not "the pointer left Praat".** The
  pin button lives on the card, so a hover that treated the card as foreign
  would dismiss the card just before the user could reach the pin. The hover
  keeps the card while the pointer is on it.
* **One timer per callback.** `QtHost.after` used to own a single `QTimer`,
  so a second `after` call replaced the first one. Every callback now gets
  its own timer, so the hover tick and the mouse poll run side by side.

**A Praat script closes whatever menu the user has open (2026-11-04).** This
was measured, not guessed: a trivial `writeFileLine` script, sent through
`Praat.exe --send`, makes the open "Open" menu disappear. The state probe
used to run such a script every 0.9 s, so the coach closed the user's menu
all the time.

The hot path therefore reads the state **without any script**: the window
titles for the editor, and the Objects window through UI Automation for the
object list and the selection (`SelectionPattern` on the list box). That
costs 17 ms and disturbs nothing. `PraatStateProbe.snapshot()` (the script
one) is now only used for the few things a script is needed for, and only
while the user is visibly idle: no menu popup open, and the mouse standing
still for 1.5 s. A probe that is still in flight when the coach stops is
waited for (`quit()` joins the thread), so no script can land after the
coach is gone.

**A UIA hit test over the menu bar closes the open menu too (2026-11-04).**
This one was found by bisecting the hover loop: with the hit test
disabled the menu survived, with it enabled the menu died within a second.
`auto.ControlFromPoint` over a menu bar item dismisses the popup that item
has open.

So the hover loop keeps away from the global hit test while a menu is
open. `PraatUI.open_popup_items()` reads the items straight from the
popup's own control tree (a tree walk is harmless; only the hit test is
not), the app picks the item whose rectangle contains the pointer, and
that item is explained. When the pointer is on the menu bar instead of on
an item, the coach does nothing at all and leaves the menu alone.

**The coach only explains Praat (2026-11-04).** The geometric fallback
("is the point inside a Praat rectangle?") is not enough: another
application can cover that rectangle, and then the control under the
cursor belongs to *that* application. `PraatUI._praat_in_front()` checks
the frontmost window at the point (`WindowFromPoint`) and accepts Praat's
own popups (a `#32768` menu, the `MouseInc` "pip" tooltip) by their owner.
When something else is in front, the hit test returns nothing and the
coach stays quiet.

**Bringing Praat to the front (2026-11-04).** Windows' foreground lock
refuses `SetForegroundWindow` when another process owns the foreground and
the user did not just click. `AttachThreadInput` to the foreground thread
lifts that restriction, so a background tool can still take the focus.
`PraatUI._activate()` uses it, which is what lets the click-to-activate
problem be solved for menu bars.

**The coach must not steal the keyboard (2026-11-05).** Three measured
mechanisms made Praat jump to the front while the student was typing
somewhere else:

1. `Praat.exe --send` (the deep state probe) **activates the Praat
   window**. The probe therefore only runs while Praat already has the
   focus (`praat_has_focus()`), and `snapshot(require_focus=True)`
   refuses to send anything otherwise.
2. A **UIA hit test over a Praat control activates Praat**. So the hit
   test only happens while Praat is in front, and the whole hover loop
   stands down when it is not.
3. `QtHoverCard.raise_()` called `activateWindow()`. The card is a
   `WindowDoesNotAcceptFocus` window, so Windows passed the focus on to
   the next window in the z-order, which was Praat. The card and the
   panel are now raised with `SetWindowPos(..., SWP_NOACTIVATE)`.

The rule that falls out of it, and that the whole application now
follows:

> The coach only touches Praat while Praat is the application in front.

While the student works in another program the coach reads nothing from
Praat at all: no hit test, no picture grab, no script. `tests/
test_foreground.py` protects that rule.

---

## 3. Runtime loops

### 3.1 The hover loop (the core interaction)

```
 ┌─ every 45 ms (run.py: POLL_MS) ─────────────────────────────────────┐
 │                                                                       │
 │  1. cursor_pos()                        ui/overlay.py                │
 │  2. PraatUI.element_at_point(x, y)       sensors/uia.py   [1-5 ms]   │
 │  3. normalize_key(el.name)               tutor/kb.py                  │
 │        └─ dedupe: same key + card visible → skip the rest           │
 │  4. kb.lookup(key, el.control_type)      tutor/kb.py        [<1 ms]  │
 │  5. state = cached PraatState snapshot   sensors/praat_state.py      │
 │  6. Advisor.advise(element, state)       tutor/advisor.py            │
 │  7. HoverCard.show(headline, body,       ui/hover.py                 │
 │                    anchor, rect, source, signature)                 │
 │     Spotlight.show(el.rect)              ui/spotlight.py             │
 │                                                                       │
 └───────────────────────────────────────────────────────────────────────┘
```

Rules that matter:

- **Step 3 is the gate.** If the normalised key is unchanged and the card is
  already visible, the tick does nothing. This is what keeps the idle cost
  near zero and stops the card flickering on every mouse move.
- **Step 5 never triggers a probe.** The hover path reads a *cached*
  snapshot. See §5.
- **Step 6 may be a pure KB lookup.** If the element is unknown, the card
  shows a "no entry for this control" state rather than guessing.
- **Re-use, not re-create.** The card and the ring are shown and hidden; they
  are not rebuilt per tick, so there is no flicker and no focus change.
- **A click dismisses the card.** If the user clicks inside Praat they are
  acting, not reading, so the card is dismissed unless it is pinned.
- **The card must never move the mouse.** It follows the cursor but is
  click-through; a pinned card is the only interactive one.

### 3.2 The lesson loop

```
 ┌─ on every state refresh (background thread, ~0.9 s) ─────────────────┐
 │                                                                       │
 │  1. PraatStateProbe.snapshot(timeout=3.0)  sensors/praat_state.py    │
 │        (runs in a worker thread; the result is queued)               │
 │  2. LessonRunner.sync(state)            tutor/lessons.py             │
 │        └─ does the current step's `detect` rule now match?           │
 │  3. if it matches → advance; else → stay, but update the "waiting"    │
 │     hint in the side panel                                            │
 │  4. SidePanel.set_lesson(title, body, progress)     ui/panel.py     │
 │  5. if the step has a `highlight` → resolve the target element and   │
 │     draw the spotlight                                               │
 │                                                                       │
 └───────────────────────────────────────────────────────────────────────┘
```

- `detect` rules are declarative and read Praat *semantics* (object types
  present, selected types, editor open), never screen pixels.
- The runner never clicks anything. A step advances when the **state** says
  the student did it, not when the overlay says so.
- A step that cannot be detected still works as a checklist item: the student
  can press "Next" manually (`LessonRunner.advance`, also the `Ctrl+Alt+N`
  hotkey).
- The panel also carries explicit controls: pick a lesson, next, previous,
  restart, hide, and a free-text question box.

### 3.3 Hotkeys

Polled with `GetAsyncKeyState` (`praatao/ui/hotkeys.py`), so no extra
dependencies and no global keyboard hook:

| Hotkey | Action |
|--------|--------|
| `Ctrl+Alt+P` | show / hide the side panel |
| `Ctrl+Alt+N` | next lesson step |
| `Ctrl+Alt+Q` | focus the question box in the side panel |
| `Ctrl+Alt+H` | hide everything (card and ring) |
| `Ctrl+Alt+R` | restart the current lesson |
| `F1` | pin / unpin the hover card |
| `Esc` | unpin and dismiss the card |

---

## 4. Data contracts (summary)

Full definitions live in [`CONTRACTS.md`](CONTRACTS.md). The shapes that cross
layer boundaries:

| Shape | Produced by | Carries | Consumed by |
|-------|-------------|---------|-------------|
| `Element` | `sensors.uia` | raw UIA name, control type, automation id, hwnd, screen rect, window title, depth; `key` (normalised), `contains_point` | `tutor.advisor`, `ui.hover` |
| `UiaWindow` | `sensors.uia` | hwnd, title, win32 class, rect, `kind` (`objects` / `picture` / `editor` / `other`) | `tutor.advisor`, `ui` |
| `PraatState` | `sensors.praat_state` | running, version, objects, selected, editor_open, editor_object, textgrid_tiers, error | `tutor.advisor`, `tutor.lessons` |
| `Advice` | `tutor.advisor` | headline, body, `source` (`kb` / `llm` / `kb+llm`), element_key, entries | `ui.hover`, `ui.panel` |
| `KnowledgeEntry` | `tutor.kb` | id, aliases, bilingual title/what/how/concept, pitfalls, keywords | `tutor.advisor` |
| `Lesson` / `LessonStep` | `tutor.lessons` | detect rule, highlight target, bilingual tip and detail | `tutor.advisor`, `ui.panel` |

Two rules that the UI depends on:

1. **Names are normalised before matching.** `normalize_name()` strips
   U+202F / NBSP, collapses spaces, removes a trailing `>`, a trailing `:` and
   a trailing `\t<shortcut>`, and drops the `N. ` list index. This is not
   cosmetic: the raw UIA names genuinely look like
   `'   Draw  >'` and `'Read from file...\tCtrl-O'`.
2. **Matching is longest-alias-wins, then keyword fallback.** A control whose
   name is not in the knowledge base falls back to keyword search, and then to
   an explicit "unknown control" state. It never invents an explanation.

Content packs are YAML so that a phonetics teacher can edit them without
touching Python:

- `praatao/content/elements.yaml` — one entry per UI control, with
  `aliases`, `control_types`, bilingual `title` / `what` / `how` / `concept`,
  `pitfalls`, `keywords`.
- `praatao/content/lessons/*.yaml` — ordered steps with a `detect` block, a
  `highlight` target, and a bilingual `tip` + `detail`.

---

## 5. Performance budget

### 5.1 The numbers

**Target: a hover card visible within 60 ms of the pointer arriving at a
control.** Comfortably achievable, because the expensive parts are cheap.

| Stage | Budget | Measured on this machine |
|-------|--------|---------------------------|
| Wait for the next cursor tick | ≤ 45 ms | `run.py: POLL_MS = 45` (≈ 22 Hz) |
| UIA hit test (`element_at_point`) | ≤ 10 ms | **1.0 - 4.9 ms** (median, 10 samples x 5 points) |
| `normalize_key` + KB lookup | ≤ 5 ms | in-memory index, well under 1 ms |
| Read the cached state snapshot | ≤ 2 ms | dictionary read |
| Build the advice | ≤ 5 ms | string assembly |
| Render + position the card and the ring | ≤ 10 ms | Tk |
| **Total** | **≤ 60 ms** | |

The 45 ms tick is the dominant term, which is why the hit test had to be cheap
enough to run on every tick. It is: at 1-5 ms it uses roughly 10% of one core
while the pointer moves, and the dedupe on the normalised key means the
expensive half (KB lookup, advice, render) runs only when the control under
the cursor actually changes.

### 5.2 The probe interval, and why the state probe is throttled and cached

The hover path must **never** wait for Praat.

- A `--send` probe costs **0.14 - 0.21 s** on a responsive Praat (measured
  repeatedly). At one probe per hover event that is ~5 calls/second: it would
  peg a core, spam Praat with scripts, and blow the 60 ms budget by 3x.
- A `--send` probe can also **block for a long time**: if the script it carries
  fails, Praat raises a modal error box and the call does not come back (measured:
  blocked past 10 s in 2 of 3 runs). A blocking probe on the UI thread would
  freeze the whole overlay.

Therefore:

| Rule | Value | Reason |
|------|-------|--------|
| Probe interval | **0.9 s** (`run.py: STATE_INTERVAL`) | Fast enough that "the student just selected a Sound" shows up almost immediately; slow enough to be invisible to Praat |
| Probe execution | **background thread**, never the UI thread | A hung probe must not freeze the card |
| Probe timeout | **hard, 3 s** (`probe.snapshot(timeout=3.0)`) | `subprocess.TimeoutExpired`, swallowed, never raised |
| On timeout | keep the last snapshot, mark it **stale**, and run `dismiss_dialogs()` | A timeout usually means the script we sent failed, and left a message box behind |
| Hover path | reads the **cached** snapshot only | Guarantees the 60 ms budget |
| Stale threshold | > 5 s → the card shows "state unknown" rather than possibly-wrong context | Better to say nothing than to mislead |
| Eager refresh | the lesson runner may request a fresh snapshot when a step is close to matching | Lesson progress should feel immediate; the cost is still off the UI thread |
| Cheap path | `PraatStateProbe.quick()` reads window titles only, < 5 ms | Enough for "is an editor open?" without any script at all |

At 0.9 s the probe costs about 1 `--send` per second, i.e. roughly 20% of one
core and one Praat script per second. That is the right order of magnitude for
a companion tool that is meant to be invisible.

**The cache is invalidated** whenever: the Objects window disappears or
reappears, the selected object set changes, the editor opens or closes, or the
cache exceeds the stale threshold.

---

## 6. The LLM layer: optional, off by default, grounded

### 6.1 Off by default

`praatao/tutor/llm.py` reads its configuration from the environment and
reports itself **unavailable** when it is not configured. With no environment
variables set, `default_llm_client()` returns a `NullLlmClient` and **every
call returns `None` instead of raising**. The overlay then runs entirely on the
curated knowledge base.

| Variable | Meaning |
|----------|---------|
| `PRAATAO_LLM_ENDPOINT` | e.g. `https://api.deepseek.com/v1` |
| `PRAATAO_LLM_MODEL` | e.g. `deepseek-chat` |
| `PRAATAO_LLM_API_KEY` | API key |
| `PRAATAO_LLM_BACKEND` | `openai` (default) or `ollama` |

`LlmClient` speaks to any OpenAI-compatible endpoint and to Ollama. The
default per-request timeout is 30 s, and errors are written to stderr at most
once per minute so a failing endpoint cannot spam the console.

### 6.2 Grounding rules

These are enforced in `Advisor._system_prompt()` and `Advisor._user_prompt()`,
not merely intended:

1. **The LLM never sees audio, ever.** It is not given the sound file, not
   given a waveform, not given a spectrogram image. It sees only *text*: the
   control's raw name and control type, a summary of the Praat state, and
   excerpts from the knowledge base.
2. **It must answer only from the supplied context.** The system prompt says
   so explicitly, in both languages: *"Answer only from the given context;
   never invent numbers, menu paths or object names."*
3. **It must admit uncertainty.** *"say so when you are unsure"*, and the user
   prompt ends with *"say whether you are certain"*.
4. **It must be short.** Capped at roughly 120 words / 120 characters,
   because it is a hover card, not an essay.
5. **It is not consulted for the hover path at all.** The LLM is used for
   `Advisor.ask()` (the free-text box in the side panel) and as a
   *fallback* when the knowledge base has no entry. A normal hover is
   answered from the KB, at zero latency and zero cost.
6. **Its output is labelled.** `Advice.source` is `kb`, `llm` or `kb+llm`, and
   the UI shows which. A student can always tell a curated explanation from a
   generated one.
7. **Failure is silent and safe.** Any exception in the LLM path is swallowed
   and the answer falls back to the KB. An LLM outage must not break a lesson.

### 6.3 Why it stays optional

- Labs frequently have no or unreliable network (design principle 5 in
  [`00-concept.md`](00-concept.md)).
- A wrong explanation of a phonetic concept is worse than no explanation.
  The KB is reviewed by a phonetics expert; a model is not.
- Cost and latency are irrelevant for 95% of the interactions, which are
  "what does this button do".

---

## 7. Failure modes

Ordered by severity. The first one is the one that actually bites in practice.

| # | Failure | How we detect it | What the user sees | Mitigation |
|---|---------|------------------|---------------------|------------|
| 1 | **A failing probe leaves a modal error box on screen.** A failing script or a failing Praat command raises a message box (class `#32770`, title `Message`). The `--send` call that carries the failing script **blocks** (hung past 10 s in 2 of 3 measured runs), and while the box is up the Objects window renders its "no selection" button row, so `View & Edit` and the dynamic buttons are absent from the tree. | The probe hits its hard timeout without a result, and a message window is visible | "Praat is showing a message box"; the overlay stays responsive | **Never block the UI thread on a probe.** On timeout, call `dismiss_dialogs()`: enumerate visible windows owned by the Praat process whose class is `#32770` (or starts with `Praat`) **and** whose title is `Message` / `Error`, then Invoke their `OK` button and retry the probe once. See §3.9 of [`10-sensing-strategy.md`](10-sensing-strategy.md) for the class table and the exact predicate |
| 2 | **Praat is not running** | `PraatUI.available()` is False; no `Praat Objects` window | The side panel says "start Praat"; no hover cards | Re-check every ~1 s; go idle gracefully. Never crash, never spawn Praat without being asked |
| 3 | **UIA element goes stale** (window closed or rebuilt) | The element's `hwnd` is no longer a valid window, or the tree walk returns fewer nodes | The card hides; no stale ring is left behind | Re-resolve by name once, then drop the cache and hide. The ring and the card are always cleared together |
| 4 | **Probe times out** for any other reason | `subprocess.TimeoutExpired` after the hard timeout | "State unknown" instead of possibly-wrong context | Keep the last good snapshot, mark it stale, **never block the UI thread**. A timeout usually means the script we sent failed (failure 1), so check for the message box before concluding anything else |
| 5 | **LLM down or unconfigured** | `LlmClient.available()` is False, or the call raises / times out | Nothing. The KB answer is shown instead, labelled `kb` | The LLM is strictly optional at every level. `NullLlmClient` is the explicit "off" switch |
| 6 | **A popup menu is open** | A top-level `#32768` window exists (Praat menus are separate HWNDs) | The card explains the menu item under the cursor, including its shortcut | Read the items from the popup's own tree, **never with a hit test**: a hit test over the menu bar dismisses the menu. Cache the item list for 0.3 s at most, and only while the popup is open. `#32768` is a **menu**, never a dialog |
| 7 | **DPI change or display change** | Cached rects no longer match the window rect; display metrics change | The ring may jump for one frame, then re-snap | Invalidate every cached rect and re-read on the next tick; keep the overlay per-display; never cache rects across a display change |
| 8 | **The selection-dependent button row changes.** The Objects window reports 46 named nodes with a Sound selected and 22 with nothing selected, so a control can legitimately be absent. | The wanted button is not in the tree, and the semantic probe says nothing is selected | No tip for that control, which is correct behaviour | Re-read the tree when the selection changes; never cache the button set across a selection change. **UIA exposes the full row when something is selected**, so no relative anchor or probe is needed to find `View & Edit` |
| 9 | **Non-English Praat UI** | Control names are not in the alias table | A generic "I don't know this control yet" card | Match on control type and object semantics first, then name; ship an alias table per UI language; detect the Praat UI language at startup |
| 10 | **Hotkey fires while the user is typing** | The panel has keyboard focus | Nothing happens | Ignore hotkeys when a text field has focus |
| 11 | **Praat is upgraded while Praatao is running** | Smoke-test assertions fail, or names stop matching | "This Praat version is not tested" | Pin tested versions; run a smoke test on startup that asserts the presence of `Praat Objects`, `Open`, `View & Edit` |
| 12 | **Another application covers Praat** | The frontmost window at the pointer is not a Praat window | Nothing. The coach does not explain the other application | Check the frontmost window (`WindowFromPoint`), not just the rectangle. Praat's own popups (menu `#32768`, "pip" tooltip) count as Praat through their owner |
| 13 | **The student is typing in another program** | Praat does not own the foreground window | Nothing. The coach does not touch Praat at all | A hit test and a Praat script both activate Praat, so the hover loop and the deep probe stand down while `praat_has_focus()` is false |

**Window classes, so we never dismiss the wrong thing:**

| Class | What it is | May `dismiss_dialogs()` close it? |
|-------|------------|-----------------------------------|
| `#32768` | Praat menu popup | **No** |
| `#32770` | Win32 message box: Praat's "Message" error dialog | Yes, if the title is `Message` / `Error` |
| `PraatShell1 Praat` | The Objects window | **No** |
| `PraatChildWindow1 Praat` | The Picture window and the editors | **No** |

A rule that matches on the class prefix alone would close the student's Picture
window or sound editor. The title filter is mandatory.

---

## 8. What v1 deliberately does *not* do

Each of these is a decision, not an omission.

- **It does not drive Praat.** No clicking buttons on the user's behalf, no
  scripted "demo" sequences, no ghost cursor. `PraatUI.invoke()` exists, but it
  is used only for an explicit, user-initiated "show me" action, and never on
  the hover path. (`00-concept.md` non-goals: no autonomous ghost cursor.)
- **It does not fork or patch Praat.** No custom build, no event hooks. If we
  ever need them, that is ADR-002 risk 2 in
  [`10-sensing-strategy.md`](10-sensing-strategy.md).
- **It is not cross-platform.** UI Automation is Windows-only. macOS and Linux
  need a different sensing layer, and are out of scope for v1.
- **It does not take screenshots in v1.** No automatic capture, no cloud
  upload, no screen recording. Vision is a future, opt-in fallback.
- **It does not touch the audio.** Praatao never reads the sound file and never
  sends audio anywhere. It sees UI metadata and Praat's object list, nothing
  else.
- **It does not require an LLM.** The offline KB is the product; the model is a
  convenience.
- **It does not autograde measurements.** A separate research track
  (`07-roadmap.md` Phase 5), and if it happens it will use Parselmouth
  (`09-python-for-praat.md`), not the overlay.
- **It is not a classroom server.** No accounts, no networked sessions, no
  progress tracking across machines in v1.

---

## 9. How to run it

### The everyday entry point

The launcher the student actually uses is a **desktop shortcut**:
`Praatao 助教` (also in the start menu). It points at
`Start-Praatao.cmd` in the repository root, which

1. finds a Python (3.12 first, then `py -3`),
2. starts `Praat.exe` from the repository root when Praat is not running
   yet (it waits five seconds for the window to appear),
3. runs `run.py` with whatever arguments were passed on,
4. pauses with a message when the coach stops with an error.

`tools/make_shortcut.py` creates that shortcut (and the start menu entry)
with `win32com`. Two quirks are worth remembering: pywin32's late bound
`WScript.Shell` mangles a path that contains Chinese characters, so the
shortcut is written under an ASCII name and renamed afterwards; and a
command line typed into a non-UTF-8 console arrives with the Chinese
already broken, so the script keeps the name in its source instead of in
the arguments.

`Ctrl+Alt+X` stops the coach, so the console window it was started from
does not have to be found.

### The launcher underneath

The launcher is **`run.py` at the repository root**.

```bash
# Start Praatao next to an open Praat
python run.py

# Options (as implemented in run.py)
python run.py --lang zh        # language for tips: zh (default) | en
python run.py --no-llm         # never contact a language model
python run.py --selftest       # print what the sensors can see, then exit
```

`--selftest` is the quickest way to check a new machine: it prints the Praat
windows it can find, the named elements it can read (with normalised names and
rectangles), the current Praat state, and the size of the knowledge base, then
exits without opening any window.

On startup `run.py` prints a banner with the knowledge-base size, the number
of lessons, whether the UIA sensor and the state probe are available, and
whether the LLM is configured or disabled.

Environment:

```bash
# Optional: enable the LLM expansion. Without these, everything is KB-only.
export PRAATAO_LLM_ENDPOINT=https://api.deepseek.com/v1
export PRAATAO_LLM_MODEL=deepseek-chat
export PRAATAO_LLM_API_KEY=sk-...
export PRAATAO_LLM_BACKEND=openai
```

Tests (plain `unittest`, no pytest dependency):

```bash
python -m unittest discover -s tests -v
```

Tests that need a live Praat must skip automatically when `Praat.exe` is not
running, using `unittest.skipUnless(praat_available(), "Praat not running")`
(`praatao.sensors.uia.praat_available()`).

Runtime state (probe files, caches) is written under
`%LOCALAPPDATA%\praatao`, overridable with `PRAATAO_STATE_DIR`.

---

## 10. Open questions for the lead

1. **Does the Tk shell supersede ADR-001** (Electron/Tauri) in
   [`01-architecture.md`](01-architecture.md)? If so, amend that file.
2. **The ADR numbering is now consistent.** `01-architecture.md` holds ADR-001
   (Electron/Tauri + probes + YAML), ADR-002 (do not fork Praat) and ADR-003
   (Parselmouth is offline-only); the sensing decision is **ADR-004** in
   [`10-sensing-strategy.md`](10-sensing-strategy.md). Nothing left to renumber.
3. **Which is the canonical lesson for the classroom pilot?** The candidates
   are "open a sound → View & Edit → spectrogram → cursor measurement" and
   "annotate a TextGrid".
4. **Does the LLM ever get to answer a *hover* (not an explicit question)?**
   The current design says no. Keeping it that way keeps the hover free,
   instant, and private.
5. **Should `dismiss_dialogs()` auto-dismiss, or only report?** The current
   design dismisses the error box and retries the probe. That unblocks the
   student, but it also closes a dialog the student may have been about to
   read. A "report and let the student decide" mode may be friendlier.
