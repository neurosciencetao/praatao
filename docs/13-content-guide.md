# 13 — Content guide

> How to write and extend the Praatao content packs, and how the matching
> between a Praat control and a teaching note actually works.
>
> Audience: whoever adds a new UI element, a new lesson pack, or a new
> language. Read [CONTRACTS.md](CONTRACTS.md) §"praatao.content.elements
> schema" and §"praatao.content.lessons schema" for the frozen API; this
> document is the working guide.

---

## 1. What lives where

| Path | What it holds | Owner |
|------|---------------|-------|
| `praatao/content/elements.yaml` | The UI-element dictionary: one entry per Praat control or command | content teammate |
| `praatao/content/elements/*.yaml` | Fragments of the same dictionary, one topic per file (Objects window, menus, editors, workflows, concepts). They are merged into the main file by `tools/merge_elements.py`; the loader also reads them directly, so a fragment works before it is merged | content teammate |
| `praatao/content/lessons/*.yaml` | Lesson packs: ordered steps with detection, highlight and teaching text | content teammate |
| `praatao/content/lessons/index.yaml` | The catalogue: which lesson files exist, in what order, with bilingual titles | content teammate |

Everything else (the sensors, the overlay, the advisor) is code and must not
depend on any string that only exists here. If a control has no entry, the
overlay stays silent about it; it must never crash or invent an explanation.

---

## 2. `elements.yaml` — the element dictionary

### 2.1 File shape

```yaml
version: 1
entries:
  - id: view-and-edit                 # stable kebab-case key, never reused
    aliases: ["View & Edit"]         # EXACT label text Praat shows
    control_types: [ButtonControl]   # optional; only when unambiguous
    title: {en: "...", zh: "..."}
    what:  {en: "...", zh: "..."}     # what the control does, 1-2 sentences
    how:   {en: "...", zh: "..."}     # how to use it right now, in this window
    concept: {en: "...", zh: "..."}   # optional; the acoustic/phonetic idea
    pitfalls:
      - {en: "...", zh: "..."}        # the mistakes beginners actually make
    keywords: [editor, waveform, 波形, 编辑器]
```

### 2.2 The four rules that matter

1. **`id`** is a stable internal key. Rename the label in Praat? Keep the id
   and update `aliases`. Never reuse an id for a different control.
2. **`aliases`** must contain the *clean* label text exactly as Praat shows
   it. No leading U+202F, no trailing `>`, no `\tCtrl-O` suffix. The
   ellipsis **is** part of the label and must be kept, because in Praat it
   means "this opens a dialog".
   * ✅ `["Draw"]`, `["Analyse spectrum"]`, `["Read from file..."]`
   * ❌ `["Draw >"]`, `["\u202f\u202f   Draw  >"]`, `["Read from file...\tCtrl-O"]`
3. **Alias uniqueness.** After normalisation, no two entries may share an
   alias. Longest alias wins, so `["Save as 24-bit WAV file..."]` beats a
   shorter `["Save as WAV file..."]`, but two entries with the same alias
   string is a bug, not a tie-break.
4. **Bilingual completeness.** `title`, `what` and `how` must have a
   non-empty `en` **and** `zh`. `concept` and every item of `pitfalls` follow
   the same rule. `keywords` may be English only, but the Chinese keywords
   are what make the entry findable when a user searches in Chinese.

### 2.3 What `what`, `how` and `concept` each owe the reader

| Field | The question it answers | Typical length |
|-------|------------------------|----------------|
| `what` | "What does this control *do*?" | 1–2 sentences |
| `how` | "How do I use it *right now*, in this window?" | 1–3 sentences |
| `concept` | "What is the acoustic/phonetic idea behind it?" | 1–3 sentences, omit when it would be filler |
| `pitfalls` | "What do beginners get wrong here?" | 1–3 items, each one concrete |

Keep every string under ~300 characters so it fits a hover card without
scrolling.

### 2.4 Matching, precisely

The lookup key is the **normalised UIA name**:

```
raw UIA name ─► normalize_name() ─► case-insensitive compare against aliases and id
```

`normalize_name()` (implemented in `praatao/sensors/uia.py`) does, in order:

1. replaces U+202F (narrow no-break space) and NBSP with a normal space;
2. collapses runs of whitespace into one space and trims;
3. strips a trailing `>`;
4. strips a trailing `:`;
5. strips a trailing `\t…` (the menu-item shortcut suffix);
6. strips a leading list index such as `1. ` from list items.

Then:

* **Step 1 — exact alias match.** The normalised name is compared
  case-insensitively with every alias and with every `id`. If several match,
  the **longest** alias wins. So `Save as 24-bit WAV file...` beats
  `Save as WAV file...`.
* **Step 2 — keyword fallback.** If no alias matches, the normalised name is
  matched against the `keywords` lists. Put the terms a teacher would use
  ("spectrogram", "窗长", "共振峰") in `keywords`, not in `aliases`:
  `aliases` are exact labels, `keywords` are search terms.

**Practical consequences for authors:**

* An alias that is a prefix of another alias is fine, but a *generic* alias
  ("Play", "File", "Edit", "Text") will win over everything else of the same
  length. Where one label legitimately appears in several windows (Play in the
  Objects window and in the editor; Help in three windows), write **one**
  entry that says so, rather than two entries that collide.
* `control_types` is a disambiguator, not a requirement. Use it when the same
  label is a `ButtonControl` in one place and a `MenuItemControl` in another
  and you want different cards.
* The loader must not fall over on an unknown control: return `None` and stay
  silent.

### 2.5 Version drift (important)

Praat's labels change between releases. The content in this repo was
verified against **Praat 6.4.12 (2 May 2024)** — the binary shipped at the
project root — using two independent sources:

* a live UI Automation probe of a running Praat session (exact control and
  menu-item names), and
* the `praat/praat` source at tag `v6.4.12` (exact command labels).

Known differences you will meet in older manuals and newer releases:

| Older label / tutorial wording | Praat 6.4.12 | How this repo handles it |
|-------------------------------|---------------|--------------------------|
| `To Formants (burg)...` | `To Formant (burg)...` | one entry, both aliases |
| `To Point Process (cc)...` | `To PointProcess (periodic, cc)...` | one entry, both aliases |
| `To PointTier...` | `To TextTier` | one entry, both aliases |
| `Extract part...` under Manipulate | under Convert | one entry, `how` says which |
| `Select all` in the Time menu | not a menu item; the script command is `select all` | dedicated entry, says so |
| `Save as EPS file...` / `Export as EPS file...` | `Save as EPS file...` | one entry, both aliases |
| a `Type` menu in the TextGrid editor | gone in 6.4; the menus are **File, Edit, TextGrid, Interval, Boundary, Tier, Spell, Time, Play, Help** | `type-menu` entry explains the change instead of pretending the menu is there |
| `Annotate → Add boundary` in the TextGrid editor | **Boundary → Add on selected tier** (Enter) | the `dynamic-annotate` entry and lesson 04 use the real label |

### 2.6 A note on cascade buttons

The Objects window's dynamic buttons (`Draw`, `Annotate`, `Analyse spectrum`,
…) are not menu-bar items: they are buttons that open a cascade menu. When a
lesson step needs a leaf inside one of them, address it as a two-element
menu path, for example `["Annotate", "To TextGrid..."]` or
`["Analyse spectrum", "To Spectrogram..."]`. The overlay should open the
cascade and then pick the leaf.

The real menu bars, for reference:

* **Objects window** — Praat, New, Open, Save, Help
* **Sound editor** — File, Edit, Time, Play, Sound, Analyses, Spectrogram,
  Pitch, Intensity, Formants, Pulses, Help
* **TextGrid editor** — File, Edit, TextGrid, Interval, Boundary, Tier,
  Spell, Time, Play, Help
* **Picture window** — File, Edit, Margins, World, Select, Pen, Font, Help

**When you add an entry for a control you cannot verify, say so in the
entry** (for example in `pitfalls`: "按钮位置随版本不同…"). A student who is
told that a label may differ can cope; a student who is told a wrong label
cannot.

---

## 3. Lesson packs

### 3.1 File shape

```yaml
version: 1
id: 02-spectrogram            # == the file stem, including the numeric prefix
file: 02-spectrogram.yaml
title: {en: "Reading a spectrogram", zh: "读频谱图"}
summary: {en: "...", zh: "..."}
prerequisites: [01-first-sound]
steps:
  - id: choose-window-length
    detect:
      object_types_present: ["Sound"]   # types currently in the Objects list
      selected_types: ["Sound"]         # types currently selected
      editor_open: true                 # is an editor window open?
    highlight: {kind: menu, path: ["Spectrogram", "Spectrogram settings..."]}
    tip:    {en: "0.005 s for formants", zh: "0.005 秒看共振峰"}
    detail: {en: "2-5 sentences of real teaching", zh: "两到五句真正的教学"}
```

### 3.2 Conventions

* **File names** carry the teaching order: `01-…`, `02-…`, and so on.
* **`id`** equals the file stem, so a loader can key on either the filename or
  the `id` field and get the same answer. `index.yaml` lists them in order
  with `id`, `file`, `order`, `title`, `summary`, `objective` and
  `prerequisites`.
* **`detect`** always carries all three keys (`object_types_present`,
  `selected_types`, `editor_open`), even when the value is an empty list or
  `false`. A missing key must never mean "unknown".
* **`highlight`** has one of three kinds:
  * `menu` — `path: [top-level menu, item]` (use the Praat label text, e.g.
    `["Open", "Read from file..."]`);
  * `button` — `name: "View & Edit"`;
  * `list` — `name: "Objects:"` for the list itself, or the list-item label.
* **`tip`** is the one-line coach mark that floats on screen: short enough to
  read without clicking.
* **`detail`** is the expandable text: **2–5 sentences** of real teaching,
  not a restatement of the tip. It is where you explain the phonetic idea and
  warn about the trap.
* **5–9 steps** per lesson. Fewer and the pack is too thin; more and students
  lose the thread.

### 3.3 What a good lesson step does

A step is not a feature tour. Each one should:

1. name the **next click**, not the whole feature area;
2. explain **why** that click, in one line;
3. give the **concept** (window length, F0 range, tier mechanics);
4. warn about the **trap** that will otherwise cost the student ten minutes.

The four beginner traps that the packs are built around (see
[08-community-pain-points.md](08-community-pain-points.md)):

* the dynamic buttons look broken when nothing is selected;
* the spectrogram looks washed out or smeared;
* the TextGrid is opened without its Sound (or without dual selection);
* labels are typed into the yellow boundary tier instead of the white text
  window.

---

## 4. Bilingual style

The Chinese is the **primary** audience (Hong Kong and mainland students),
so the Chinese is written as Chinese, not as a translation of awkward
English.

* Keep the standard Chinese phonetic-teaching register: 基频 (F0), 共振峰
  (formant), 音段 (segment), 层级 (tier), 频谱图 (spectrogram), 强度
  (intensity), 动态范围 (dynamic range), 窗长 (window length), 分析窗
  (analysis window), 宽频/窄频 (broadband/narrowband), 过零 (zero crossing).
* Give the English term in parentheses on first mention where it helps:
  「声门闭合（glottal closure）」.
* Keep English UI labels in English inside Chinese text, in ASCII quotes or
  code style: `To Formant (burg)...`. Students have to recognise them on
  screen.
* Avoid em dashes and en dashes (U+2014, U+2013); use a comma, a colon or a
  line break. Use the Chinese full-width comma and colon.
* Keep sentences short. A hover card is not a paragraph.

---

## 5. Validation

Run these before handing content over.

```bash
# every entry, and the required keys
python -c "import yaml,sys; d=yaml.safe_load(open(r'praatao/content/elements.yaml',encoding='utf-8')); print(len(d['entries'])); [print(e['id'], sorted(e.keys())) for e in d['entries']]"
```

The fuller check (duplicates, empty bilingual fields, string length, lesson
shape) is the snippet below. Save it as `tools/check_content.py` if you want
it as a file, or paste it straight into a Python shell. It reports:

* duplicate `id`s and duplicate normalised aliases;
* entries missing `title`/`what`/`how` or a language variant;
* empty pitfall strings or keywords;
* strings longer than 300 characters;
* lesson files whose `id` does not match the file stem, steps outside the
  5–9 range, or steps missing `detect`/`highlight`/`tip`/`detail`.

```python
"""Check the Praatao content packs. Usage: python tools/check_content.py"""
import collections
import glob
import os
import re
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ELEMENTS = os.path.join(ROOT, "praatao", "content", "elements.yaml")
LESSONS = os.path.join(ROOT, "praatao", "content", "lessons")
MAX_LEN = 300
problems = []


def normalise(text):
    text = text.replace("\u202f", " ").replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s*>$", "", text)
    text = re.sub(r"\t.*$", "", text)
    text = re.sub(r"^\d+\.\s*", "", text)
    return text.casefold()


def check_bilingual(where, field, mapping):
    for lang in ("en", "zh"):
        if not str(mapping.get(lang, "")).strip():
            problems.append(f"{where}: empty {field}.{lang}")


data = yaml.safe_load(open(ELEMENTS, encoding="utf-8"))
ids = collections.Counter()
aliases = collections.Counter()
for entry in data["entries"]:
    where = entry.get("id", "<no id>")
    ids[where] += 1
    for key in ("id", "aliases", "title", "what", "how", "keywords"):
        if key not in entry:
            problems.append(f"{where}: missing {key}")
    for alias in entry.get("aliases", []):
        aliases[normalise(alias)] += 1
    for key in ("title", "what", "how"):
        if key in entry:
            check_bilingual(where, key, entry[key])
            for lang in ("en", "zh"):
                if len(entry[key][lang]) > MAX_LEN:
                    problems.append(f"{where}: {key}.{lang} longer than {MAX_LEN}")
    if "concept" in entry:
        check_bilingual(where, "concept", entry["concept"])
        for lang in ("en", "zh"):
            if len(entry["concept"][lang]) > MAX_LEN:
                problems.append(f"{where}: concept.{lang} longer than {MAX_LEN}")
    for pitfall in entry.get("pitfalls", []):
        check_bilingual(where, "pitfall", pitfall)

for key, count in ids.items():
    if count > 1:
        problems.append(f"duplicate id: {key}")
for key, count in aliases.items():
    if count > 1:
        problems.append(f"duplicate alias: {key}")

for path in sorted(glob.glob(os.path.join(LESSONS, "*.yaml"))):
    stem = os.path.splitext(os.path.basename(path))[0]
    lesson = yaml.safe_load(open(path, encoding="utf-8"))
    if stem == "index":
        for item in lesson.get("lessons", []):
            for key in ("title", "summary", "objective"):
                check_bilingual(f"index/{item.get('id')}", key, item.get(key, {}))
        continue
    if lesson.get("id") != stem:
        problems.append(f"{stem}: id '{lesson.get('id')}' does not match file name")
    check_bilingual(stem, "title", lesson.get("title", {}))
    steps = lesson.get("steps", [])
    if not 5 <= len(steps) <= 9:
        problems.append(f"{stem}: {len(steps)} steps (expected 5-9)")
    for step in steps:
        where = f"{stem}/{step.get('id')}"
        for key in ("detect", "highlight", "tip", "detail"):
            if key not in step:
                problems.append(f"{where}: missing {key}")
        detect = step.get("detect", {})
        for key in ("object_types_present", "selected_types", "editor_open"):
            if key not in detect:
                problems.append(f"{where}: detect missing {key}")
        highlight = step.get("highlight", {})
        if highlight.get("kind") not in ("menu", "button", "list"):
            problems.append(f"{where}: bad highlight kind")
        if "path" not in highlight and "name" not in highlight:
            problems.append(f"{where}: highlight needs path or name")
        for key in ("tip", "detail"):
            check_bilingual(where, key, step.get(key, {}))

print(f"{len(data['entries'])} element entries")
for problem in problems:
    print("FAIL:", problem)
print("OK" if not problems else f"{len(problems)} problem(s)")
sys.exit(1 if problems else 0)
```

---

## 6. Current inventory

As of this writing:

* `elements.yaml` (+ the fragments in `elements/`): **288 entries**, one
  alias each, no alias used twice, every entry bilingual. Coverage: the
  Objects window and its selection-dependent row (one entry per cascade
  menu plus the leaves a first-year lab touches); the Objects window menu
  bar (Praat, New, Open, Save, Help) with their verified leaves; the
  editor windows (Sound editor, TextGrid editor, Picture window, the
  window buttons, the drawing area, the scroll bar controls); the common
  workflows (recording, importing, viewing, annotating, measuring pitch,
  formants and intensity, scripting, the demo window); the object types a
  student meets (Sound, Pitch, Intensity, TextGrid, Formant, FormantGrid,
  Spectrogram, Table, TableOfReal, Matrix, Strings, Corpus, the tiers) and
  the acoustic concepts behind them (time axis, sampling rate, the Nyquist
  limit, what a formant is, what "objects" means in Praat).
* `lessons/`: **6 packs** — `01-first-sound` (7 steps), `02-spectrogram`
  (8), `03-pitch` (7), `04-textgrid` (8), `05-analysis-workflow` (9),
  `06-batch-and-export` (the researcher's path: corpus, tables, scripts,
  exporting the results).

### The merge, and why there are two places

`tools/merge_elements.py` folds the fragments into `elements.yaml`:

* an entry whose alias is not in the main file is appended,
* an entry whose alias **is** in the main file replaces it, and the
  pitfalls of the replaced entry are carried over, so nothing is lost.

The loader does not depend on the merge having been run: it reads the
main file, then the fragments, and drops any fragment entry whose alias
is already taken. So a new fragment works immediately, and the merge only
keeps the main file tidy.

### Deliberately not covered

| Not covered | Why |
|--------------|-----|
| Every single leaf of the `Praat → Goodies` and `Technical` submenus | System-level settings, not phonetics. The menus themselves are covered. |
| `Sound → To Cochleagram`, `To Ltas`, `To BarkSpectrogram` | Auditory-model displays; useful but specialised, and their settings differ from the standard spectrogram. |
| The `Manipulation` editor's individual pitch/duration target commands | They live under `Modify` on a Manipulation object and are covered at the level of `To Manipulation...` and `To Sound (resynthesis)...`. |
| The old `To Formants (sl)...` and `To LPC (burg)...` variants | Kept as one-line mentions inside the main formant entry rather than separate cards. |
| The neural-network and constraint-grammar menus | They are research tools; the menus are covered, the models inside them are not. |
| Windows-specific dialogs (the file open/save boxes) | They are standard Windows controls; the overlay should stay out of the way there. |
| Anything whose exact label could not be verified against Praat 6.4.12 | Guessed labels are worse than silence. This is why `New Table...` was corrected to `Create Table with column names...`, and why there is no "Extract sound files..." card: in 6.4.12 a selected Corpus offers only Rename, Copy, Inspect, Info, Remove and View & Edit. |

---

## 7. Adding an entry, step by step

1. **Find the real label.** Do not type it from memory. Either probe the live
   Praat UI (see `prototypes/v1/experiments/uia_probe*.py`) or read the
   command registration in the Praat source (`praat_addAction1`,
   `praat_addMenuCommand`).
2. **Write the `aliases`** with the clean label text.
3. **Write `what`** — one or two sentences on what it does.
4. **Write `how`** — where to click, in this window, in this state.
5. **Write `concept`** if there is a genuine acoustic idea behind it, and
   **omit it** if it would be filler. A card without a concept is fine; a
   card with a vague concept is not.
6. **Write `pitfalls`** from real teaching experience, not from the manual.
7. **Add keywords** in both languages.
8. **Run the validation** above.
9. If the control appears in a lesson step, add the `highlight` path so the
   spotlight can find it.
