# v1 experiments — the measurements behind ADR-004

These scripts are the evidence trail for
[`docs/10-sensing-strategy.md`](../../../docs/10-sensing-strategy.md).  They are
not part of the product; they are kept because every claim in the decision
record should be reproducible.

All of them talk to the **live** Praat on this machine
(`Praat.exe`, version **6.4.12**).  Start Praat first.

## The question that started it all

> *Should the overlay use screen coordinates, or vision recognition?*

## Discovery

| Script | What it established |
|---|---|
| `uia_probe.py` | Praat's controls **are** exposed through the Windows accessibility tree: `Rename...`, `Copy...`, `Inspect`, `Info`, `Remove`, `Sound help`, `View & Edit`, `Play`, `To Intensity...`, plus the menu bar `Praat / New / Open / Save / Help`.  This killed the "we need OCR" hypothesis before it cost anything. |
| `uia_probe2.py` | With a Sound selected the **dynamic row** appears (`Draw`, `Query`, `Modify`, `Annotate`, `Analyse periodicity`, `Analyse spectrum`, `Manipulate`, `Convert`, `Filter`, `Combine`), and menu popups expose their items **with keyboard shortcuts** (`Read from file...\tCtrl-O`). |
| `uia_probe3.py`, `uia_probe4.py` | `Praat.exe --send` answers in ~0.2 s for a trivial script; UIA `Invoke` really opens the editor; the editor window is titled with the *list label* (`2. Sound demo_vowel`), not `Sound demo_vowel`. |
| `uia_perf.py` | Hit test **1-5 ms**, tree walk **34-92 ms**.  That is what makes a <60 ms hover budget comfortable. |
| `uia_invoke.py` | UIA `Invoke` works on Praat buttons (it is a real click, not a synthetic one). |
| `uia_diag*.py` | The object list is exposed as `ListItemControl` named `1. Sound demo_vowel`. |
| `uia_dismiss_dialogs.py` | A failing Praat script leaves a modal box behind; this clears it. |

## Praat scripting: what exists and what does not

| Script | What it established |
|---|---|
| `praat_func_probe.py` | `numberOfSelected()` and `selected$()` **exist**.  `numberOfObjects`, `selected$` (no parentheses) and `selected$[1]` **do not**.  Also: `writeFileLine:`'s second argument is an *expression* — quoting it writes the literal text. |
| `select_probe.py` | `selectObject: 1` (by id) is unambiguous; `selectObject: "Sound demo_vowel"` is not, when two objects share a name. |

## Overlay bugs found while building it

| Script | What it established |
|---|---|
| `ui_debug.py` | **Tk rebuilds the HWND when a withdrawn toplevel is deiconified**, so window styles applied in the constructor are lost.  They must be applied *after* mapping.  Also: setting `WS_EX_LAYERED` by hand makes the window render invisible. |
| `hittest_after_card.py` | Mapping the hover card does **not** break the UIA hit test. |
| `pane_children.py` | UIA reports a **disabled** button as its unnamed container, and that container's parent does not expose the button as a child — which is why the sensor needs a geometric fallback against the window's named elements. |

## The tooltip ("pip") problem

The most expensive bug of the whole build, and the one that is invisible
until you actually use the thing.

| Script | What it established |
|---|---|
| `menu_debug.py` | The "Open" menu item was found, enabled, and had a sensible rectangle — but clicking it did nothing. |
| `menu_debug2.py` | The **same click, done with raw Win32** (`SetCursorPos` + `mouse_event`), opened the menu every time. So the fault was in the *click mechanism*, not in Praat. |
| `menu_debug3.py` | The foreground window at that moment was **`MouseInc` / `PipWindow`** — Praat's object-list tooltip, stuck on top of the menu bar and eating the clicks. |
| `pip_dismiss.py` | Posting `ESC` **to the tooltip window** closes it, and the menu opens on the next click. A real ESC keystroke would instead land on the Objects window and clear Praat's object selection. |

Two separate lessons:

1. **UIA's `Invoke` can fail silently.** For a control without an HWND
   (Praat's menu items have `NativeWindowHandle == 0`), `Invoke()` returns
   without doing anything and without raising. The sensor therefore
   dispatches on the HWND: real window → Invoke, no window → raw Win32 click.
2. **A tooltip is not a control.** The sensor now treats a tooltip hit as
   "nothing there" and resolves the real control geometrically.

`pip_dismiss.py` is kept because it is the smallest runnable proof of both
claims.

## The model, the canvas and the new card (2026-11-04)

| Script | What it established |
|---|---|
| `minimax_probe.py` | The MiniMax endpoint answers in **1.9 s** (text) and **3.0 s** (vision on a small picture), with the model `MiniMax-M3.1-Flash`; `/v1/models` lists only the chat models. |
| `minimax_imagegen.py` | The image model `image-01` answers in **14 s** and returns a JPEG at `data.image_urls[0]`. The pictures are attractive but **not literally accurate** (a "spectrogram" comes out as abstract wavy bands), so the feature is opt-in. |
| `canvas_probe.py` | Praat's drawing areas **are** in the accessibility tree: `[PaneControl] 'drawingArea' cls='PraatDrawingArea1 Praat'`, editor rect 76, 143, 1880, 1008. The earlier "the canvases are invisible" claim was wrong. |
| `canvas_stats.py` | A local classification works: pixel statistics separate a spectrogram (dark canvas) from a waveform or a pitch view (bright canvas with coloured curves). |
| `card_render.py` | The Qt card renders on its own: rounded corners, soft shadow, coloured section headings, pin and close buttons. |
| `card_layout.py` | The card's layout is identical in isolation and inside the application, so a mismatch on screen is not a layout problem. |
| `card_rules.py` | The three interaction rules on the real application: the pointer leaves → gone after **2 s**; pinned → stays; a click → dismissed. |
| `pin_button.py` | The pin button, the close button and the card body, each with its own behaviour. It also showed that the *first* click on an inactive window only activates it, so the application (which polls the mouse) has to do the hit test itself. |
| `llm_async_probe.py` | The model answer arrives **3.2 s** after the question, on a worker thread, while the hover loop stays responsive. |
| `llm_end_to_end.py` | The late answer reaches the **open card** and replaces the "thinking" text in place. This is what exposed the Qt thread bridge bug (a `staticmethod` slot made the connection direct, so the slot ran in the worker thread). |
| `imagegen_end_to_end.py` | The drawn teaching picture reaches the card **19.7 s** after the question (3 s for the text answer, 14 s for the picture). |

Three bugs that only showed up in the real application, not in the tests:

1. **The spotlight was drawn over the card.** The ring is a separate window,
   so it covered the first line of the text. The card is now raised above it.
2. **A `QGraphicsDropShadowEffect` changes how the compositor draws the
   window**, so the text on screen did not match what Qt drew itself. The
   shadow is painted by hand now.
3. **A `Qt.Tool` window that never takes focus keeps its old pixels** after a
   resize: `repaint()` is needed, `update()` is not enough.

## The acceptance round (2026-11-04, later)

Taking the acceptance screenshots turned up four more bugs that no test had
caught, because every one of them needs the *whole* application running with
a real mouse.

| Script | What it established |
|---|---|
| `menu_survives.py` | **A Praat script closes the menu the user has open.** A trivial `writeFileLine` sent through `Praat.exe --send` makes the "Open" menu disappear. The state probe used to run such a script every 0.9 s, so the coach took the menu away all the time. The hot path now reads the state through UIA (`fast()`, 17 ms, no script). |
| `menu_bisect.py`, `menu_bisect2.py` | Which part of the tick loop closed the menu. The first version of the bisect was itself wrong: the timer kept running between the cases, so every case was contaminated. The clean version (stop the timer, patch one thing, restart) showed the probe was the only cause. |
| `script_closes_menu.py` | The same measurement in isolation: a script closes the menu, and `--send` takes 0.16 s. |
| `pinned_shot.py` | Two more bugs: a click shorter than the 45 ms tick is **lost** (the mouse button is now watched every 10 ms), and the pointer being on our own card was treated as "the pointer left Praat", so the card dismissed itself just before the pin could be reached. |

`prototypes/v1/acceptance_capture.py` takes the acceptance screenshots
itself: the real mouse, the real tick loop, the real Praat.

## The launcher round (2026-11-04, later still)

The entry point is a desktop shortcut, so the coach had to survive being
started from a cold machine. Writing that down turned up two more bugs,
both of them about *what the coach looks at*.

| Script | What it established |
|---|---|
| `menu_interference.py`, `menu_class_repro.py` | The menu test failed only when another test ran before it. Bisecting the hover loop with the popup open showed the second cause of a closing menu: **a UIA hit test over the menu bar dismisses the open menu** (`--no-hit` kept the menu, everything else did not). The coach now reads the open popup's items from its own tree instead of hit testing. |
| `menu_item_hover.py` | The feature still works: with the pointer on "Read from file...", the card explains it (`Read from file...（从档案读入）`) and the menu stays open. |

Two more findings came out of the same round:

* **The coach explained other applications.** The geometric fallback
  ("is the pointer inside a Praat rectangle?") is not enough, because
  another window can cover that rectangle. The frontmost window at the
  pointer decides now, and Praat's own popups (menu `#32768`, the "pip"
  tooltip) count through their owner.
* **A background process could not bring Praat to the front.**
  `SetForegroundWindow` alone is refused by the foreground lock;
  `AttachThreadInput` to the foreground thread lifts it.

## The round that stopped Praat from stealing the keyboard (2026-11-05)

The student reported the worst kind of bug: Praat kept jumping to the front
while he was typing in another program.  It took three separate causes,
and each one needed its own measurement.

| Script | What it established |
|---|---|
| `foreground_probe.py`, `foreground_probe2.py` | **`Praat.exe --send` activates the Praat window.**  The deep state probe sent a script every few seconds, so every one of those jumps was the coach's fault. |
| `foreground_probe3.py`, `foreground_probe4.py` | A UIA hit test over a Praat control activates Praat as well (an isolated `ControlFromPoint` does not, but the real path does).  So even the hover itself was enough to pull Praat forward. |
| `foreground_guard2.py` | The guard that finally worked: our own panel takes the foreground, the coach runs for 20 s, and the foreground must not move.  Before the fix it printed `STAYED PUT: False`, after it `True`. |
| `foreground_watch.py`, `uia_focus_probe*.py` | Which of the three mechanisms was active at any moment.  The version string was part of it: `Praat.exe --version` starts a console Praat and writes UTF-16, so the version now comes from the executable's version resource. |
| `dump_controls.py` | A live dump of the 90 real control names of Praat 6.4.12 (Objects window, editors, menus), used as the ground truth for the knowledge base. |
| `hover_debug.py` | Why a hover sometimes shows nothing: the pointer, the focus and the open menu are printed every 100 ms. |
| `llm_context_check.py` | The prompt that goes to the model, and the answer that comes back, for one control in a secondary window.  The answer has to mention the selected object, not only the label. |
| `settings_roundtrip.py` | The settings window, end to end: switch the language, switch the model off, and check the file that was written. |

Two more findings came out of the same round:

* **A card that asks for the focus gives it to the next window.**
  `activateWindow()` on a `WindowDoesNotAcceptFocus` window makes
  Windows pass the focus on, which was Praat.  Raising the card with
  `SetWindowPos(..., SWP_NOACTIVATE)` fixes it.
* **`--no-llm` did not switch the model off.**  The advisor falls back to
  an environment-configured client when it is handed `None`, so "off" has
  to be handed over as the client that answers nothing.

## Reproducing

```powershell
cd D:\Documents\Playground\praatao
python prototypes\v1\experiments\uia_probe.py
python prototypes\v1\experiments\uia_perf.py
python prototypes\v1\experiments\praat_func_probe.py
python prototypes\v1\experiments\canvas_probe.py
python prototypes\v1\experiments\card_rules.py
python prototypes\v1\experiments\llm_end_to_end.py
python prototypes\v1\experiments\foreground_guard2.py
python prototypes\v1\experiments\llm_context_check.py
python prototypes\v1\experiments\settings_roundtrip.py
python prototypes\v1\acceptance_capture.py
```

They print to stdout and, in a few cases, leave a JSON dump next to themselves.
