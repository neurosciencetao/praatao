# Architecture analysis

## The hard problem

Praatao needs three capabilities:

| Capability | Meaning | Difficulty |
|------------|---------|------------|
| **Sense** | Know what Praat is showing / what user just did | Hard |
| **Decide** | Map state → next tip / lesson step | Medium |
| **Render** | Draw coach marks over Praat without breaking interaction | Medium–Hard |

Rendering overlays is a solved pattern (Electron transparent windows, etc.). **Sensing Praat’s GUI state** is the bottleneck.

## Why sensing is hard

Praat’s GUI is a **cross-platform abstraction** with a **Windows Motif emulator** (`sys/motifEmulator.cpp`) mapping Motif-style widgets to Win32 `HWND`s. Many controls are standard buttons/labels, but:

- Layout and dynamic menus are Praat-specific
- Drawing areas (waveform, spectrogram) are custom graphics, not accessible document trees
- Object list selection state is not exposed as a public IPC “query GUI” API
- Accessibility / UI Automation coverage is incomplete for custom drawing surfaces

So “generic screen agent” approaches (OCR + vision LLM) work as a fallback, but are slower, flaky, and costly. Prefer **structured sensors** where possible.

## Sensing strategies (ranked for Praatao)

### A. Script / sendpraat probes (recommended core)

Praat can be controlled and partially queried from outside via:

- `praat --send script.praat` — run a script in the **GUI** instance
- `sendpraat` — message a running Praat
- Praat scripting queries: selected objects, object types, names, counts, editor state (with care)

**Idea:** Praatao periodically (or on hotkey / after detected window events) sends a tiny probe script that writes JSON to a temp file or stdout-like Info dump:

```praat
# probe_state.praat (sketch)
writeFileLine: "C:/Temp/praatao_state.json", "{""n"":" + string$(numberOfSelected()) + "}"
# extend: types, names, whether editor is open, etc.
```

**Pros:** Uses official API; exact object semantics.  
**Cons:** Must design probes carefully; editor scripting (`editor` / `endeditor`) is trickier; polling vs event-driven.

### B. Window geometry + title tracking

Use Win32 APIs (`EnumWindows`, `GetWindowText`, `GetWindowRect`) to find:

- “Praat Objects”
- “Praat Picture”
- Sound editor titles (often include object name)

Anchor overlay highlights to **relative regions** of known windows (e.g. dynamic button panel is roughly bottom of Objects window).

**Pros:** Fast, offline, no Praat script needed.  
**Cons:** Layout changes with DPI/theme/version; brittle across Praat versions; cannot know *which* object type is selected without (A) or vision.

### C. UI Automation / MSAA on native controls

Inspect button text (“View & Edit”, “Annotate…”) via UIA where HWND-backed controls expose names.

**Pros:** Can find clickable targets by name.  
**Cons:** Incomplete for drawing areas; Motif emulator quirks; version fragility.

### D. Computer vision / OCR / multimodal LLM

Screenshot Praat → detect buttons / waveform presence → generate tip.

**Pros:** Works when structured APIs fail; good for prototypes and “stuck user” help.  
**Cons:** Latency, cost, privacy (lab machines), nondeterminism; bad for precise click targets unless combined with (B)/(C).

### E. Fork / plugin Praat (long-term)

Add C++ hooks that emit UI events (selection changed, editor opened) to a local socket.

**Pros:** Best sensing.  
**Cons:** Maintenance burden; distribution of modified Praat; upstream merge cost.

**Recommendation:** Start with **A + B**, use **C** for highlight targeting, keep **D** as optional “Ask Praatao” fallback, defer **E**.

## Rendering strategies

### Overlay process (recommended for MVP)

Separate app (Electron / Tauri / native) that:

1. Creates frameless, transparent, always-on-top window(s)
2. Uses click-through (`setIgnoreMouseEvents(true, { forward: true })` in Electron) except when hovering tips
3. Draws spotlight rings, arrows, cards positioned from sensed window rects + relative anchors

Reference patterns: Lekhini, Visor, PolterGuide, Beacon (see `06-related-systems.md`).

### Side panel instead of overlay

A docked “coach” window next to Praat (no click-through issues). Weaker “point at the button” affordance but much easier to ship.

**Hybrid MVP:** side panel steps + optional overlay spotlight.

## Logical modules

```
┌─────────────────────────────────────────────────────────┐
│                     Praatao Shell                        │
│  ┌──────────┐  ┌────────────┐  ┌─────────────────────┐ │
│  │ Sensor   │→ │ Tutor      │→ │ Overlay / Panel UI  │ │
│  │ Bridge   │  │ Engine     │  │ (React/Vue/Svelte)  │ │
│  └────┬─────┘  └─────┬──────┘  └──────────▲──────────┘ │
│       │              │                     │            │
│       │         ┌────▼──────┐              │            │
│       │         │ Lesson    │──────────────┘            │
│       │         │ Content   │  YAML/MD packs            │
│       │         └───────────┘                           │
│  ┌────▼─────────────────────────────────────────────┐  │
│  │ Praat process  ←--sendpraat / --send--→  probes   │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Sensor Bridge

- Locate Praat HWND(s)
- Run probe scripts / read state file
- Optional UIA hit-test for button labels
- Emit normalized `PraatState` events

### Tutor Engine

- Finite-state / rule matcher over `PraatState`
- Lesson progress (completed steps, skips)
- Later: student model (ITS-inspired)

### Overlay UI

- Tip cards (short / expanded)
- Anchored highlights
- Hotkeys: next, dismiss, expand, panic-hide

## State schema (draft)

```ts
type PraatState = {
  praatRunning: boolean;
  version?: string;
  windows: { id: string; title: string; bounds: Rect }[];
  objects: { id: number; type: string; name: string; selected: boolean }[];
  editor?: { open: boolean; objectName?: string; /* best-effort */ };
  lastActionAt: number;
};
```

## Security & classroom constraints

- Prefer localhost IPC / temp files under user profile
- No cloud screenshots by default
- If LLM used: explicit opt-in; strip audio; send UI metadata only when possible

## Failure modes to design for

| Failure | Mitigation |
|---------|------------|
| Probe script fails / Praat busy | Back off; fall back to window titles |
| Multi-monitor / DPI mismatch | Per-display overlays; physical pixels |
| User rearranges windows | Re-query bounds every frame / 200ms |
| Non-English Praat UI | Prefer object-type sensing over menu string match; localize tip packs |
| Praat version drift | Pin tested versions; CI smoke on Objects/Editor titles |

## Architecture decision record (proposed)

**ADR-001:** MVP = **Electron/Tauri overlay + sendpraat probes + YAML lessons**, Windows-first (this machine already has `Praat.exe`).  
**ADR-002:** Do not fork Praat until probes prove insufficient for P0 labs.  
**ADR-003:** Parselmouth is for **offline demos / content generation / batch checks**, not for driving the live GUI.

---

## Addendum (2026-11-04): what v1 actually uses

The v1 prototype settled two questions by measurement rather than by taste.
Full evidence is in [`10-sensing-strategy.md`](10-sensing-strategy.md) and
[`12-architecture-v1.md`](12-architecture-v1.md).

**ADR-004 (supersedes the sensing half of ADR-001):** *Sense the GUI with
Windows UI Automation, not with screen coordinates and not with a vision
model.* Praat's Windows GUI is drawn by a Motif emulator that maps its
widgets onto real HWNDs, so the accessibility tree exposes the buttons by
name with exact screen rectangles — `View & Edit`, `Play`, `Draw`, `Query`,
`Modify`, `Annotate`, `Analyse periodicity`, `Analyse spectrum`,
`Manipulate`, `Convert`, `Filter`, `Combine`, plus the menu bar and the
menu popups (whose item names carry the keyboard shortcuts). This gives
name *and* geometry in one call, with a measured hit-test cost of 1-5 ms.
Praat's own scripting (`--send`) is kept, but only for **semantics**
(what is selected, what objects exist), never for geometry.

**ADR-005 (supersedes the "Electron/Tauri" half of ADR-001):** *The v1 shell
is Python 3.12 + stdlib Tk + Win32 ex-styles, not Electron or Tauri.*
The overlay needs only three native capabilities — always-on-top,
click-through (`WS_EX_TRANSPARENT`), and per-pixel transparency
(`-transparentcolor`) — all of which Tk provides directly. A browser
runtime would add 150 MB and a rebuild step for no visible benefit at this
stage, and the whole point of the UIA route is that it is a *Windows-native*
path: the same skill set (UIA, Win32, Praat scripting) covers sensing and
rendering. Revisit if the overlay ever needs rich text, animation, or a
cross-platform shell.

**Consequence for `02-tech-stack.md`:** the Electron/Tauri row is superseded
by the Tk row. The YAML content model, the layered architecture, and the
Windows-first constraint are unchanged.

