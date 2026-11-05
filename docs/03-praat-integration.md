# Praat integration reference

## Official entry points

| Resource | URL |
|----------|-----|
| Praat home | https://praat.org/ |
| Manual (web) | https://praat.org/manual/ |
| Scripting tutorial | https://praat.org/manual/Scripting.html |
| CLI / `--send` | https://praat.org/manual/Scripting_6_9__Calling_from_the_command_line.html |
| sendpraat | https://praat.org/manual/Scripting_8__Controlling_Praat_from_another_program.html |
| sendpraat subroutine | https://praat.org/manual/Scripting_8_1__The_sendpraat_subroutine.html |
| Source (GitHub) | https://github.com/praat/praat |
| GUI framework notes | https://deepwiki.com/praat/praat/5.1-gui-framework |

## Mental model of Praat for Praatao

Praat is not one window. Typical session:

1. **Objects** — list of data objects (Sound, TextGrid, Pitch, …)
2. **Picture** — drawing canvas for publication figures
3. **View & Edit** — per-object editors (Sound editor is the most common learner surface)
4. **Info** — text output from queries/scripts
5. **Script** — editor for Praat language

Dynamic menus/buttons change with **what is selected** in Objects. This is a primary teaching difficulty and a primary sensing signal.

## Controlling a live GUI instance

### `praat --send`

```bat
Praat.exe --send "C:\path\probe.praat"
```

- Runs in existing GUI Praat if running; else starts one
- Can open windows / use View & Edit (unlike `--run`)
- Best default for Praatao demos and probes

### `praat --run`

Headless; **cannot** open View & Edit windows. Use for CI tests and Parselmouth-like batch work.

### sendpraat

Sends script text to a **already running** Praat. Cannot start Praat by itself (use `--send` if you need start-or-attach).

Example conceptual message:

```text
Read from file: C:\data\a.wav
Play
```

## Probe design ideas

### Minimal: count & types of selected objects

Write a script that:

1. Queries `numberOfSelected()`
2. For each selected object, gets type and name
3. Writes `praatao_state.json` under `%LOCALAPPDATA%\praatao\`

### Detect editor open (approximate)

Heuristics:

- Window title contains object name + “Sound” / “TextGrid”
- Or script attempts `editor: name$` patterns (fragile—test per version)

### Safe demo macros

User-triggered only:

- “Show me”: `--send` script that selects Sound and executes `View & Edit`
- Prefer teaching the click first; offer “Do it for me” as secondary

## Parselmouth (Python) — what it is / isn’t

Paper: Jadoul et al. (2018), *Journal of Phonetics* — https://doi.org/10.1016/j.wocn.2018.07.001  
Docs: https://parselmouth.readthedocs.io/

| Can | Cannot |
|-----|--------|
| Call Praat algorithms from Python | Drive the Praat GUI |
| Batch feature extraction | Open View & Edit |
| Build Jupyter teaching demos | Replace sendpraat for overlay sensing |

Use Parselmouth for:

- Generating lesson illustrations
- Autograding extracted F0/formants in advanced modes
- Research pipelines that should stay reproducible outside the GUI

## GUI implementation facts (Windows)

- Cross-platform GUI layer; Windows uses **Motif emulator** → Win32 controls
- Buttons/checkboxes often real `HWND`s → partial UIA possible
- Spectrogram/waveform = drawing areas → need geometric anchors or vision

Implications for Praatao:

- Highlight “View & Edit” via UIA name match when possible
- Highlight spectrogram region via **fixed relative rectangle** inside editor window
- Never assume MSAA tree equals full semantic state—combine with object probes

## Version pinning

Praatao should record:

```yaml
tested_praat_versions:
  - "6.4.xx"   # match your local Praat.exe
```

UI strings and layout can shift. Keep a smoke checklist:

- [ ] Objects window found
- [ ] Read from file works via UI and via script
- [ ] View & Edit opens
- [ ] Probe JSON written within 500 ms

## Local binary in this repo

`Praat.exe` at project root (Windows). Prefer invoking with absolute path in prototypes:

```python
PRAAT = r"D:\Documents\Playground\praatao\Praat.exe"
```

## Useful scripting topics for onboarding content

Map lessons to official manual chapters:

| Learner task | Praat concepts |
|--------------|----------------|
| Open audio | Read from file, Sound object |
| View waveform | View & Edit |
| Spectrogram | Spectrum settings, window length |
| Pitch | Pitch settings, green contour |
| Formants | Formant settings, red speckles |
| Annotate | TextGrid, Annotate button, tiers |
| Measure | Cursor, Get commands, Info window |
| Figure for paper | Picture window, Paint |
| Automate | Scripting, forms |

## Integration test sketch

```
1. Start Praat if needed
2. --send clear_objects.praat
3. --send read_demo_wav.praat
4. Read state JSON → expect Sound selected or present
5. Overlay asserts tip id == "view-edit"
```
