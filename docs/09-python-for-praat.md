# "Python for Praat": does the package exist, and should we use it?

> Answers the user question (2026-11-04): *"there is a Python package called
> 'Python for Praat' - does it exist, can we use it?"*
>
> Every claim below was checked against PyPI and GitHub on **2026-11-04**.
> Exact commands are in [How to verify](#appendix-how-to-verify) at the end.

## Short answer

1. **No package named `python-for-praat` exists on PyPI.**
   `https://pypi.org/pypi/python-for-praat/json` returns **HTTP 404**.
   Nor does `praat-py` (the GitHub project of that name was never published to
   PyPI either).

2. The package almost certainly meant is **Parselmouth**
   (PyPI name `praat-parselmouth`, latest release **0.4.7**).
   It is the standard, well-maintained, well-cited way to call Praat's
   algorithms from Python.

3. **Parselmouth is useful, but it is the wrong tool for Praatao's live-overlay
   goal.** It wraps Praat's *algorithms*; Praatao needs to sense Praat's *GUI*.
   Parselmouth cannot open a window, cannot see a button, cannot read a
   selection, and cannot be told "the user is hovering over *View & Edit*".

4. Parselmouth still earns a place in the project, for **teaching figures**,
   **batch-analysis demos in Jupyter**, and **cross-checking** that a scripted
   pipeline reproduces what a student did by hand.

5. For the actual Praatao sensing problem we use **Windows UI Automation**
   (see [`10-sensing-strategy.md`](10-sensing-strategy.md)).

This restates **ADR-003** in [`01-architecture.md`](01-architecture.md):
*"Parselmouth is for offline demos / content generation / batch checks, not for
driving the live GUI."*

---

## 1. The name check

### 1.1 `python-for-praat` does not exist

| Check | Result |
|-------|--------|
| `GET https://pypi.org/pypi/python-for-praat/json` | **HTTP 404** |
| `GET https://pypi.org/pypi/praat-py/json` | **HTTP 404** |
| GitHub repository search for `python-for-praat` in the name | 2 hits, neither is a general "Python for Praat" package: [`mwv/praat_formants_python`](https://github.com/mwv/praat_formants_python) and [`lnplp/Python-Praat-formant-logging`](https://github.com/lnplp/Python-Praat-formant-logging) |

A wider sweep of plausible names, all confirmed **404** on PyPI:
`praat`, `praat-python`, `praat-python3`, `praat-api`, `praat-parser`,
`praat-script`, `praat-scripts`, `praatlib`, `praatutils`, `praat-mpi`,
`pympi-praat`, `parselmouth-praat`, `praat-interactive`, `praat-controller`,
`praat-ui`, `praat-gui`, `praat-bridge`, `praat-wrappers`.

The only `praat-*` name that resolved was **`praat-tools` 0.1.0**
(uploaded 2023-06-15, GitLab `athena-luka/praat-tools`), whose own description
reads: *"This project aims to become a comprehensive Python library to read and
write Praat object files"*. It is unfinished and much smaller in scope.

### 1.2 Two name-collision traps

Both of these install happily and are **not** what a Praat user wants:

| Name you may type | What actually installs |
|-------------------|-----------------------|
| `pip install parselmouth` | **An ad-provider SDK** ("An object oriented interface for ad provider services in python", v1.1.1). The phonetics library is `pip install praat-parselmouth`. |
| `pip install pympi` | **An unrelated MPI implementation** (`hpca-uji/pympi`, v1.4.12). The Praat-oriented MPI library is *not* published on PyPI under this name. (I could not verify a canonical repository URL for it from this machine, so treat the exact URL as unverified.) |

---

## 2. The real ecosystem

| Project | PyPI name (version) | GitHub | What it actually is | Drives the running Praat GUI? |
|---------|--------------------|--------|---------------------|-------------------------------|
| **Parselmouth** | `praat-parselmouth` (0.4.7) | [YannickJadoul/Parselmouth](https://github.com/YannickJadoul/Parselmouth) / [docs](https://parselmouth.readthedocs.io/) | pybind11 bindings **directly into Praat's own C/C++ code**, so algorithms and outputs are exactly the same as Praat's. GPL-3.0. | **No** |
| **PraatIO** | `praatio` (6.2.2) | [timmahrt/praatIO](https://github.com/timmahrt/praatIO) | Pure-Python reading/writing of TextGrid, KlattGrid, Praat IO files and tiered transcripts. MIT. Does not use Praat at all. | **No** |
| **praat-py** | *not on PyPI* | [JoshData/praat-py](https://github.com/JoshData/praat-py) | A **patch set + build scripts** that turn a source build of Praat into one that accepts `#lang=python` scripts. GPL-2+ (same terms as Praat). | It *is* a Praat binary, but it **replaces** Praat rather than attaching to a running one |
| **textgrid** | `textgrid` (1.6.1) | [kylebgorman/textgrid](https://github.com/kylebgorman/textgrid) | TextGrid + HTK `.mlf` manipulation. MIT. Repository is **archived**. | **No** |
| **praat-tools** | `praat-tools` (0.1.0) | GitLab `athena-luka/praat-tools` | Reader/writer for Praat object files (TextGrid, PitchTier, DurationTier). Early stage. | **No** |

### 2.1 Parselmouth in detail

- PyPI: `praat-parselmouth`, latest release **0.4.7**, uploaded 2025-11-27.
  GPL-3.0. Author Yannick Jadoul. 16 releases on PyPI.
- GitHub: 1297 stars, 132 forks, last push 2026-10-13, **not** archived.
- Docs: <https://parselmouth.readthedocs.io/>
- Paper: Jadoul, Y., Thompson, B., & de Boer, B. (2018). *Introducing Parselmouth:
  A Python interface to Praat.* **Journal of Phonetics**, 71, 1-15.
  <https://doi.org/10.1016/j.wocn.2018.07.001>

Its own README states the design intent precisely:

> "Parselmouth directly accesses Praat's C/C++ code (which means the algorithms
> and their output are exactly the same as in Praat) and provides efficient
> access to the program's data."

**The known limitation, stated plainly:** Parselmouth links the Praat *library*,
not the Praat *application*. There is no windowing system, no Motif emulator, no
`View & Edit` editor, no Objects list widget, no menu. Praat itself documents
the same split: `praat --run` is headless and "cannot open View & Edit
windows" (see [`03-praat-integration.md`](03-praat-integration.md)).

### 2.2 praat-py in detail

The README (Joshua Tauberer, "From my PhD days") is explicit about the
maintenance state and the build burden:

> "Praat-Py is a replacement for the Praat executable file you download from the
> Praat website. Because this project is no longer well maintained, there is no
> ready-to-go replacement file available. Praat-Py must be compiled from source
> files."

The repository contains `praat-py.patch`, `praat-win32-mingw.patch`,
`python.c`, `scripting.cpp`, `sendpraat_main.c` and `build_win32.sh` /
`build_linux.sh`. The documented build needs **Python 2.5 or 2.6** plus the
Praat sources patched in. Last push: 2024-06-11. 65 stars, 13 forks, no
licence file (README says "same terms as Praat itself, the GPL v2 or later").

Practical consequences for Praatao: it is a **fork of the application**, not a
library, so it also lands us in "we now maintain a Praat build" territory
(the thing ADR-002 in [`01-architecture.md`](01-architecture.md) says to avoid),
and it does not help with sensing a *running* Praat instance.

---

## 3. The category error: two different products

This is the heart of the answer, and the thing worth internalising before we
re-open the question.

|  | **Wrapper around Praat's algorithms** | **Wrapper around Praat's GUI** |
|---|---|---|
| Typical example | Parselmouth, praatio | (nothing standard on PyPI) |
| Gives you | `Sound`, `Pitch`, `Formant`, `TextGrid` objects; identical numeric output | Window titles, button names, button rectangles, menu trees, which widget is under the cursor |
| Cannot give you | Window positions, button labels, hover state, selection in the GUI | The actual acoustic analysis |
| Praatao's question it answers | *"What is a spectrogram? Show me one. What F0 did the student measure?"* | *"The user is hovering over **View & Edit**. What does that button do?"* |

Praatao's core interaction (see [`00-concept.md`](00-concept.md)) is
**"hover a button, then explain it"**. That is squarely the second column.
A library that never opens a window cannot answer it, no matter how good its
algorithms are.

So: **no PyPI package solves Praatao's actual problem.** The GUI-wrapping
ecosystem on Windows is the accessibility stack itself (UI Automation), which is
what v1 uses.

---

## 4. What Parselmouth *is* good for, in Praatao

These are real and worth doing. They sit **outside** the overlay, in the
content pipeline and in validation.

1. **Generating teaching figures.** Waveform, spectrogram, pitch contour and
   formant plots for lesson packs and worksheets, produced offline in a
   reproducible script and committed next to the YAML. Same rendering code path
   a student would use in Praat, so the figure and the screen agree.
2. **Batch-analysis demos in Jupyter.** "Here is the same measurement, as
   code." Useful for students who will write scripts, and for TAs who want a
   reproducible baseline.
3. **Cross-checking a student's work.** "The value you measured by hand in the
   Sound editor is F1 = 730 Hz; here is what Parselmouth gets on the same file."
   This turns the overlay's advice into something falsifiable, and it is also
   how we regression-test our own lesson content (e.g. "the lesson claims this
   filter band is 2000-5000 Hz; assert it against the object").
4. **Optional research track.** The `04-literature.md` and `07-roadmap.md`
   "research / product forks" track (autograding measurements) is the natural
   home for Parselmouth, if and when we get there.

**Not** for: sensing the running GUI, opening `View & Edit`, replacing
`sendpraat` probes, or anything on the hover path.

---

## 5. If we wanted a GUI-driving Python package anyway

For completeness, this is what a "Python that can drive a Windows GUI" looks
like. None of these are "Praat packages"; they are generic GUI-automation
libraries that we point at Praat.

| Tool | What it gives | Notes |
|------|---------------|-------|
| [`uiautomation`](https://github.com/yinkaisheng/Python-UIAutomation-for-Windows) (yinkaisheng) | Direct UI Automation client: element tree, `ControlFromPoint` hit test, `Invoke`/`Click` patterns, exact screen rects | **Installed on this machine: `uiautomation` 2.0.18, Python 3.12.0.** This is what v1 uses |
| [`pywinauto`](https://github.com/pywinauto/pywinauto) | Mature UIA + Win32 backends, richer selector/wait API | Heavier; good for app-driving tests rather than a 45 ms hover loop |
| [`pygetwindow`](https://github.com/pygetwindow/pygetwindow) | Window position and size only | No semantics at all; geometry only, no names |
| `ctypes` + `win32gui` / `pywin32` | Raw Win32: `EnumWindows`, `GetWindowText`, `GetClassName`, `GetWindowRect`, `SetWindowLong` for click-through overlays | The floor. Necessary for the overlay windows themselves |
| Praat's own `--send` / `sendpraat` | Semantic state of a running Praat: objects, selection, tiers | Not geometry. Complements UIA rather than replacing it (see [`10-sensing-strategy.md`](10-sensing-strategy.md)) |

Note the division of labour that falls out of this: **UIA for geometry and
names**, **`--send` for semantics**, **Win32 for drawing the overlay**.

---

## 6. Verdict for Praatao

| Question | Answer |
|----------|--------|
| Does `python-for-praat` exist on PyPI? | **No.** HTTP 404, verified 2026-11-04 |
| Should we depend on Parselmouth? | **Yes, but only for offline content generation, batch demos and cross-checks.** Never on the sensing path |
| Should we look for a "Python that drives the Praat GUI" package? | **Stop looking.** There isn't one, and the generic Windows GUI-automation libraries plus Praat's own scripting already cover it |
| What do we use to sense the GUI? | **Windows UI Automation** (`uiautomation`), per ADR-004 in [`10-sensing-strategy.md`](10-sensing-strategy.md) |
| Should we fork Praat (like praat-py) to add hooks? | **No, not in v1.** Deferred; see the residual-risk table in `10-sensing-strategy.md` |

---

## Appendix: how to verify

Everything above is reproducible with stock Python (no extra packages). Run
from anywhere.

### A.1 Does a PyPI name exist?

```python
import urllib.request, urllib.error, json

for name in ["python-for-praat", "praat-parselmouth", "praatio", "praat-py",
             "pympi", "parselmouth", "textgrid", "praat-tools"]:
    url = "https://pypi.org/pypi/%s/json" % name
    try:
        r = urllib.request.urlopen(url, timeout=20)
        d = json.loads(r.read().decode())
        print("OK  ", name, r.status, "| version:", d["info"]["version"],
              "|", d["info"]["summary"])
    except urllib.error.HTTPError as e:
        print("HTTP", name, e.code)      # 404 == does not exist
```

Expected for `python-for-praat` and `praat-py`: `HTTP 404`.

Equivalent with `curl`:

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://pypi.org/pypi/python-for-praat/json
# -> 404
```

### A.2 Full metadata for one project

```python
import urllib.request, json
d = json.loads(urllib.request.urlopen(
    "https://pypi.org/pypi/praat-parselmouth/json", timeout=25).read().decode())
i = d["info"]
print(i["version"], "|", i["summary"], "|", i["license"])
print(i["project_urls"])
```

### A.3 GitHub: project facts and the search

```bash
# repository metadata (stars, licence, last push)
curl -s https://api.github.com/repos/YannickJadoul/Parselmouth \
  | python -c "import json,sys; d=json.load(sys.stdin); print(d['stargazers_count'], d['license']['spdx_id'], d['pushed_at'])"

# is there anything named "python-for-praat"?
curl -s "https://api.github.com/search/repositories?q=python-for-praat+in:name&per_page=10" \
  | python -c "import json,sys; d=json.load(sys.stdin); print(d['total_count']); [print(i['full_name']) for i in d['items']]"
```

### A.4 Confirm the local toolchain we rely on

```bash
python -m pip show uiautomation
# -> Name: uiautomation / Version: 2.0.18 / Python 3.12
```

### A.5 Re-confirm Parselmouth cannot open a GUI window

```python
import parselmouth
snd = parselmouth.Sound("prototypes/v0/assets/demo_vowel.wav")
print(snd.to_spectrogram())      # works: this is the algorithm layer
# There is no parselmouth API that opens View & Edit, because Parselmouth
# links Praat's library and not its GUI (see the Parselmouth README above).
```
