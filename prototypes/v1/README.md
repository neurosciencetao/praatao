# v1 prototypes

The v0 prototype (a Tk coach with relative-rectangle highlights) lives in
[`../v0/`](../v0/).  This folder holds the scripts that produced the
**v1** product and its evidence.

| | |
|---|---|
| [`../v1/experiments/`](../v1/experiments/) | the measurements behind [ADR-004](../../docs/10-sensing-strategy.md) — what each script proved, and how to re-run it |
| [`../v1/demo_capture.py`](../v1/demo_capture.py) | moves the real mouse over a Praat control, shows the card, screenshots the result |
| [`../v1/live_run.py`](../v1/live_run.py) | drives the real `run.py` application against the live Praat and captures it |
| [`../v1/ui_smoke.py`](../v1/ui_smoke.py) | smoke test for the overlay windows |
| [`../v1/check_lessons.py`](../v1/check_lessons.py) | prints the lesson packs and their steps |

The product itself is not in this folder: it is [`../../praatao/`](../../praatao/)
plus [`../../run.py`](../../run.py).

## Capturing evidence

```powershell
cd D:\Documents\Playground\praatao

# hover a button
python prototypes\v1\demo_capture.py --target "View & Edit" --select 1 --lang zh

# hover a menu item (the menu stays open)
python prototypes\v1\demo_capture.py --menu Open --item "Read from file..." --lang zh

# run the real application and capture it
python prototypes\v1\live_run.py
```

Output lands in [`../../docs/screenshots/`](../../docs/screenshots/).
