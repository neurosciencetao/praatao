# Roadmap & action steps

Ordered to reduce risk: **prove sensing**, then **prove overlay UX**, then **content scale**, then **evaluation**.

## Phase 0 — Framing (1–2 days) ✅ in progress

- [x] Name & concept writeup (`00-concept.md`)
- [x] Technical feasibility notes (`01`–`03`)
- [x] Literature & resource collection (`04`–`06`)
- [ ] Write 10 personal Praat pain points (from your experience) into `docs/pain-points.md`
- [ ] Pick P0 lesson: e.g. “WAV → View & Edit → Spectrogram → cursor measure duration”

## Phase 1 — Feasibility spikes (1–2 weeks)

Do these as throwaway prototypes under `prototypes/`.

### Spike A — sendpraat / `--send` probe

1. Script: read demo WAV into Praat GUI  
2. Script: dump selected object types to JSON file  
3. Python watcher prints state changes  

**Exit criteria:** External process knows “a Sound exists / is selected” without looking at the screen.

### Spike B — window-following overlay

1. Find HWND by title substring `Praat`  
2. Transparent always-on-top panel tracking Objects window bounds  
3. Draw one highlight rectangle at a **hard-coded relative** position  

**Exit criteria:** Highlight stays aligned while dragging the Objects window.

### Spike C — UIA button find

1. With Sound selected, search UIA tree for `View & Edit`  
2. Return bounding box → feed Spike B  

**Exit criteria:** Highlight snaps to real button (or document failure → rely on relative layout).

### Decision gate

| Outcome | Path |
|---------|------|
| A+B work, C flaky | Ship relative anchors + probes |
| C works well | Prefer UIA anchors |
| A fails badly | Consider Praat fork / heavier vision |

## Phase 2 — Vertical slice MVP (2–4 weeks)

Ship one guided tour end-to-end:

1. Lesson YAML for P0 task  
2. Sensor bridge service  
3. Overlay or hybrid side panel  
4. Expandable tip component (short / long Markdown)  
5. Hotkeys: Next, Expand, Hide, Quit  
6. Demo WAV + checklist worksheet PDF  

**Exit criteria:** A novice completes the tour without a human coach once.

## Phase 3 — Content & i18n (ongoing)

- Pack: TextGrid annotation basics  
- Pack: Pitch settings for intonation  
- Pack: Formant measurement cautions  
- EN + 简体中文 strings  
- Authoring README for TAs  

## Phase 4 — Classroom pilot

- 1 lab section, consent + simple survey  
- Metrics: time-to-spectrogram, completion, NASA-TLX or SUS-lite, open feedback  
- Compare to previous year worksheet-only if data exist  

## Phase 5 — Research / product forks

| Track | Goal |
|-------|------|
| Education paper | Design-based research on situated Praat tutoring |
| Engineering | Open-source Praatao; plugin lesson packs |
| AI assist | Opt-in “explain my screen” grounded on lesson RAG |
| Deep integration | Optional Praat patch for event hooks |

## Immediate next actions (this week)

1. **You:** Dump pain points & dream lesson list (15 min).  
2. **Dev:** Spike A in `prototypes/probe/` using local `Praat.exe`.  
3. **Dev:** Spike B minimal overlay (Python or Electron—pick one).  
4. **Content:** Draft YAML for one lesson (see `prototypes/content/`).  
5. **Read:** Styler ch. on opening files + spectrograms; Scripting 6.9.  

## Team skills to recruit / build

| Skill | Role |
|-------|------|
| Phonetics teaching | Lesson accuracy |
| Praat scripting | Probes & demos |
| Desktop UI (Electron/Tauri/Qt) | Overlay |
| Win32/UIA | Sensing |
| Evaluation / applied linguistics methods | Pilot study |

## Risk register

| Risk | Mitigation |
|------|------------|
| Cannot reliably sense selection | Invest in probe scripts; limit v1 to linear tours with “I did it” confirmation buttons |
| Overlay blocks clicks | Click-through default; careful hit regions |
| Lab PC install rights | Portable zip; no admin |
| Tip annoyance | Easy hide; progress save; density settings |
| Phonetic mis-explanations | Expert review checklist before packs ship |

## Definition of “project is real”

Not a slide deck—when **Spike A + B** are demos you can show a colleague in 3 minutes.
