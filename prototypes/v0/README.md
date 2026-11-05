# Praatao v0 prototype

Companion coach window for live Praat on Windows.

## Run

```powershell
cd D:\Documents\Playground\praatao\prototypes\v0
python test_bridge.py   # headless checks
python app.py           # coach UI
```

## What it does

1. Detects Praat windows (Objects / Picture / editors)
2. Probes object list via `Praat.exe --send probes/dump_state.praat`
3. Shows step tips with expandable explanations
4. Draws a semi-transparent highlight on a rough UI region
5. Buttons: Launch Praat, Load demo sound, “I did this step”

## Lesson flow

Start Praat → Load sound → Select Sound → View & Edit → Spectrogram tips → TextGrid bonus gotcha

Tips incorporate common community/teaching pain points (dual-select TextGrid, spectrogram dynamic range, typing in yellow tier, etc.).
