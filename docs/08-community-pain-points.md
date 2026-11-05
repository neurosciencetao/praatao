# Common Praat user confusions (web / teaching sources)

Collected 2026-08-04 while shaping the v0 prototype. Used to write tip copy in `prototypes/v0/lessons.py`.

## High-frequency gotchas

| # | Confusion | What people hit | Prototype tip |
|---|-----------|-----------------|---------------|
| 1 | **Open / Read / LongSound** | Wrong menu → unexpected object type | Step `load-sound` |
| 2 | **Dynamic buttons** | Right panel empty because nothing selected | Step `select-sound` |
| 3 | **Spectrogram “missing” / washed out** | Need zoom; Dynamic range often too high; window length broadband vs narrowband | Step `spectrogram` |
| 4 | **Pitch jumps (octave errors)** | Default floor/ceiling wrong for speaker | Mentioned in spectrogram long tip / future pack |
| 5 | **TextGrid dual-select** | Must select Sound **and** TextGrid, then View & Edit — classic “gotcha” in Gouskova & lab PDFs | Step `bonus-textgrid` |
| 6 | **Typing in the yellow tier** | Labels go in the **top white box**, not the yellow strip (Mark Antoniou teaching note) | Step `bonus-textgrid` |
| 7 | **Analyses clutter** | Red formants + blue pitch + pulses overwhelm first lab | Spectrogram tip: toggle Show pitch/formants off |
| 8 | **Where are settings?** | Spectrum/Pitch menus live in the **editor**, not Objects | Step `view-edit` |

## Sources (non-exhaustive)

- Maria Gouskova — Praat tutorial (TextGrid View & Edit gotcha): https://www.gouskova.com/2016/09/03/praat-tutorial/
- Mark Antoniou — TextGrid labeling (yellow tier vs white box): https://markantoniou.blogspot.com/2023/03/marking-segments-and-annotating.html
- Lab worksheets / UNC TextGrid PDF — dual selection & tier types
- Will Styler guidebook — spectrogram / pitch settings practice
- Osatananda & Thinchan (2021) — out-of-class Praat friction (file/procedure complexity)
- Official Praat Intro — spectrogram & pitch configuration

## Design implication for Praatao

Priority order for early tips should be **procedural UI gotchas** first (selection, View & Edit, TextGrid dual-select), then **interpretation settings** (dynamic range, pitch range), then deeper phonetics.
