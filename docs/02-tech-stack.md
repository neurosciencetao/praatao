# Tech stack guide

## Recommendation summary (MVP)

| Layer | Choice | Why |
|-------|--------|-----|
| Overlay / desktop shell | **Tauri 2** or **Electron** | Transparent always-on-top + web UI for tips |
| UI | **React** or **Svelte** | Fast iteration for expandable cards |
| Sensor / Praat bridge | **Python 3.11+** or **Rust/TS** calling CLI | Easy `subprocess` to `praat --send` |
| Lesson content | **YAML + Markdown** | Editable by phonetics teachers |
| Acoustic helpers (optional) | **Parselmouth** | Same algorithms as Praat, no GUI |
| Packaging | MSIX / portable zip | Lab machines often lack admin install |

**Pragmatic split for this repo’s Windows context:**

1. **Phase 0 spike:** Python sensor + simple always-on-top WinForms/PyQt tip window (fastest learning).
2. **Phase 1 product:** Tauri/Electron overlay + shared lesson packs.

## Language roles

### TypeScript / JavaScript

- Overlay UI, animations, expand/collapse tips
- IPC with native shell
- Lesson renderer (Markdown → HTML)

Learn: Electron BrowserWindow transparency & `setIgnoreMouseEvents`, or Tauri window APIs.

### Python

- Prototype sensors quickly
- Call `Praat.exe --send`
- Parselmouth for generating example spectrograms / validating measurements in docs
- Possible FastAPI local “tutor service” if overlay and sensor are separate processes

Libraries of interest:

- `pywin32` / `ctypes` — window enumeration
- `uiautomation` or `pywinauto` — control discovery
- `parselmouth` — Praat-in-Python (batch only)
- `pydantic` — `PraatState` schema

### Praat scripting language

Essential for probes and demo macros. Official tutorial: [Scripting](https://praat.org/manual/Scripting.html).

Must-learn sections:

- Object selection & querying
- `writeInfo` / files
- `praat --send` / sendpraat
- Editor scripting (`editor` / `endeditor`)

### C / C++ (optional later)

- sendpraat subroutine integration
- Praat fork / native plugin
- Only if you outgrow CLI messaging

### Rust (if Tauri)

- Window tracking, system tray, global hotkeys
- Safer packaging than Electron for small overlays

## Comparison: shell frameworks

| | Electron | Tauri | Native Qt/WPF |
|--|----------|-------|---------------|
| Transparent overlay | Mature examples | Supported; fewer public samples | Excellent |
| Bundle size | Large | Small | Medium |
| Web UI skill reuse | High | High | Low |
| Windows UIA from main | Node addons / PowerShell | Rust crates | Direct |
| Team familiarity | High in web | Growing | Depends |

For a research lab building a pedagogy tool, **Electron is fine** if iteration speed matters more than binary size. **Tauri** is attractive if you want a lean lab install.

## Praat-facing tooling

| Tool | GUI? | Role in Praatao |
|------|------|-----------------|
| `Praat.exe` | Yes | Target application |
| `praat --send` | Yes | Run probe/demo scripts in live instance |
| `praat --run` | No | Headless batch; tests |
| sendpraat | Messages GUI | Alternative to `--send` |
| Parselmouth | No | Content/examples/tests, not overlay sensing |
| praat-parselmouth papers | — | Cite when using Python acoustic pipeline |

Official: [Controlling Praat from another program](https://praat.org/manual/Scripting_8__Controlling_Praat_from_another_program.html), [CLI](https://praat.org/manual/Scripting_6_9__Calling_from_the_command_line.html).

## Content / authoring stack

- **YAML** lesson definitions
- **Markdown** long explanations (phonetic concepts)
- Optional: Obsidian / Notion export for course authors
- Screenshots / short GIFs stored under `content/media/`
- i18n: `en.json` / `zh-Hans.json` message catalogs

## AI components (optional, phase 2+)

| Use | Stack | Caution |
|-----|-------|---------|
| Explain this spectrogram region | Vision LLM + user opt-in screenshot | Hallucinated formants |
| Free-form “how do I annotate?” | RAG over lesson packs + Praat manual excerpts | Ground answers |
| Stuckness detection | Heuristics first (idle, repeated menu open) | Privacy |

Do **not** make LLM the primary step engine for P0 labs—use deterministic lesson graphs.

## Dev environment (suggested)

```
Windows 10/11
Praat (local Praat.exe already in repo root)
Node 20+   (overlay)
Python 3.11+ (sensor / Parselmouth)
Git
Optional: Inspect.exe (Windows SDK) for UIA exploration
```

## Learning path for the team (ordered)

1. Praat GUI Intro + one full lab task manually  
2. Praat scripting tutorial (objects, files, `--send`)  
3. Electron/Tauri transparent window sample  
4. Win32 find window + draw box on top  
5. Probe script → JSON state → tip appears  
6. YAML lesson pack for “Sound → View & Edit → Spectrogram”

## Anti-patterns

- Reimplementing spectrograms in the overlay “to simplify Praat” — splits the user’s mental model
- Relying only on vision agents for every step — fragile in classrooms
- Blocking the entire screen with a modal wizard — defeats “orientation while doing”
