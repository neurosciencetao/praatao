# Learning resources (tutorials & manuals)

Curated for building Praatao **and** for learning Praat deeply enough to write good tips.

## Official Praat

| Resource | Link | Notes |
|----------|------|-------|
| Website | https://praat.org/ | Downloads, feature overview |
| Intro (in-app) | Praat → Help → Intro | Best first-day path |
| Full manual | https://praat.org/manual/ | Searchable web copy of Help |
| Scripting | https://praat.org/manual/Scripting.html | Required for probes |
| Users list | https://groups.io/g/Praat-Users-List | Community Q&A |
| Source | https://github.com/praat/praat | GUI / Motif emulator study |
| sendpraat page | https://praat.org/sendpraat.html | Downloads / docs |

## High-quality third-party guides

| Resource | Link | Best for |
|----------|------|----------|
| Will Styler — *Using Praat for Linguistic Research* | https://wstyler.ucsd.edu/praat/ | Research workflows, measurements, scripting intro (~85+ pages) |
| Hugo Quené — Tutorial on Phonetics and Speech Analysis | https://hugoquene.github.io/TPhSA-EN/ | Concept + Praat labs together (bookdown) |
| Beginner manuals (linked from Praat site) | https://www.fon.hum.uva.nl/praat/ | “Beginner’s manuals by others” |

## Parselmouth / Python

| Resource | Link |
|----------|------|
| Docs | https://parselmouth.readthedocs.io/ |
| Examples (Binder) | Linked from docs homepage |
| Paper PDF (author copy often circulating) | Search “Introducing Parselmouth” Jadoul |

## Overlay / desktop coaching engineering (learn by reading code)

| Project | Link | Steal ideas |
|---------|------|-------------|
| Lekhini | https://github.com/opensourcebharat/lekhini | Transparent click-through overlay, multi-monitor |
| Visor (analysis writeup) | https://github.com/yassinvila/Visor | Screenshot → LLM → overlay steps |
| PolterGuide | https://github.com/gaida123/polter-guide/ | Agentic overlay / ghost cursor (demo-level) |
| UIPin | https://github.com/sixtdreanight/UIPin | UI annotation + Windows UIA at pin point |
| Beacon | https://github.com/OtisLau/conuhacks | Task guidance overlays |

## Windows automation learning

- UI Automation overview (Microsoft Learn)
- Inspect.exe / Accessibility Insights for Windows — see what Praat exposes
- `pywinauto` docs — Python control of Win32 apps
- Electron docs: `BrowserWindow` `transparent`, `setIgnoreMouseEvents`

## Course / lab design references

When authoring Praatao lesson packs, mirror good lab pedagogy:

1. One learning objective per short tour  
2. Immediate practice on real audio  
3. Interpretation questions (“What does the dark band mean?”) inside expandable tips  
4. End with a checklist students can reuse without the overlay  

Quené’s tutorial structure (read → exercise → Praat practice → revisit) is a strong template.

## Suggested personal study sequence (陶老师 / collaborators)

**Week A — User empathy**

- [ ] Complete Praat Help Intro
- [ ] Do one Styler beginner measurement end-to-end
- [ ] List top 10 “I don’t know where to click” moments (seed lesson backlog)

**Week B — Automation**

- [ ] Write a `.praat` script that reads a WAV and prints duration to Info
- [ ] Run it with `Praat.exe --send` from PowerShell
- [ ] Enumerate Praat windows with a 20-line Python script

**Week C — Overlay spike**

- [ ] Transparent always-on-top window following Objects window bounds
- [ ] Hard-coded tip: “Click View & Edit”
- [ ] Replace hard-code with JSON probe

## Local notes folder

Put personal study notes / screenshots here as you learn:

- `docs/tutorials/notes/` (create as needed)
- `docs/papers/` — PDFs you are allowed to store locally (respect copyright; prefer DOI links + open versions)
