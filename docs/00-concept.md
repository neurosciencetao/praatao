# Product concept: Praatao

## Name

**Praatao** = **Praat** + **a**ugmentation + **o**rientation  
(Also a playful nod to the author / lab identity.)

## Problem

Praat (Boersma & Weenink) is indispensable for phonetics research and teaching, but:

1. **UI density** — Objects window, Picture window, View & Edit, dynamic menus that change with selection.
2. **Concept + tool coupling** — Users must learn both acoustic phonetics *and* where buttons live.
3. **Static help** — Built-in Help and external tutorials are not tied to the live screen state.
4. **Fragile workflows** — Common tasks (open sound → View & Edit → show spectrogram → measure formants → annotate TextGrid) require many precise clicks in order.

Literature and teaching practice repeatedly note that Praat’s interface is powerful but hard for beginners; pronunciation-training studies often conclude that learners need scaffolding or that raw formant/pitch displays are too complex without guidance (see `04-literature.md`).

## Vision

A **companion process** that runs beside Praat and renders a **transparent overlay**:

- Spotlights (“click here next”)
- Floating coach marks with short text
- Expandable panels with deeper phonetic / UI explanation
- Optional guided tours (lesson packs) for lab courses
- Later: adaptive hints based on detected stuckness (idle, wrong window focus, rage-clicks)

Praatao does **not** replace Praat. It orients users *inside* the real Praat GUI.

## Target users (priority)

| Tier | User | Need |
|------|------|------|
| P0 | Undergrad / MA phonetics students | First-week labs: open file, spectrogram, pitch, TextGrid |
| P1 | Research assistants | Repeatable measurement protocols |
| P2 | Pronunciation teachers | Guided use for intonation / vowel practice |
| P3 | Power users | Optional tips off; scripting / batch orientation |

## Core interaction loop

```
detect Praat state  →  match lesson / rule  →  render overlay tip
        ↑                                              |
        └──────── user acts in Praat / expands tip ────┘
```

### Example: “Open a sound and view spectrogram”

1. User starts Praat (or Praatao launches Praat).
2. Tip: “Open → Read from file…” with arrow near menu / Open button.
3. After a Sound appears in Objects: “Select the Sound, then click **View & Edit**.”
4. In editor: “Press **s** or enable Spectrogram in the Spectrum menu.”
5. Expandable card: what a spectrogram shows (time × frequency × intensity), common pitfalls (window length, dynamic range).

## Content model

Content should be structured, not hard-coded strings only:

```yaml
id: open-sound-view-edit
title: Open a sound and inspect it
prerequisites: []
steps:
  - id: read-file
    detect: { window: Objects, objects: empty_or_no_sound }
    highlight: { kind: menu, path: ["Open", "Read from file..."] }
    tip_short: "Load a WAV (or other) sound file."
    tip_long_md: |
      Praat stores sounds as **Sound** objects...
  - id: view-edit
    detect: { selected: Sound }
    highlight: { kind: button, label: "View & Edit" }
    tip_short: "Open the waveform/spectrogram editor."
```

Lessons = ordered packs of steps. Detection rules = declarative sensors (see architecture).

## Design principles

1. **Click-through by default** — Overlay must not block Praat unless the tip itself is interactive.
2. **Progressive disclosure** — Short tip → expandable detail → optional deep dive / demo GIF.
3. **Phonetics + UI together** — Explain *why* (F0, formants) and *where* (which button).
4. **Non-destructive** — Prefer observing Praat; avoid forcing scripted actions unless user opts into “demo mode.”
5. **Offline-first for labs** — University labs often have limited network; ship lesson packs locally.
6. **Respect Praat as source of truth** — Algorithms stay in Praat; Praatao teaches use, not reimplements analysis (except optional Parselmouth demos outside the overlay).

## Non-goals (v1)

- Full rewrite of Praat UI
- Automatic grading of phonetic measurements (later research track)
- Completely autonomous “ghost cursor” that drives Praat without user consent
- Mobile app

## Success metrics (later)

- Time-to-first-spectrogram for novices
- Task completion rate on lab worksheets
- Tip dismissal / expand rates (engagement)
- Qualitative: “I understand what I’m clicking”

## Open product questions

1. **Course-integrated vs standalone** — Should v1 ship with PolyU/LST lab packs only, or a public starter curriculum?
2. **Language** — Bilingual EN/ZH tips from day one?
3. **AI tips** — Rule-based first, LLM explanations as optional expansion (needs grounding to avoid phonetic hallucinations)?
4. **Fork Praat vs overlay** — Overlay is faster to ship; forking Praat for native hooks is heavier but more reliable sensing (see architecture).
