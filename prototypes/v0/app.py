"""
Praatao v0 prototype — companion coach for Praat.

Run:
  python app.py

Requires: local ../../Praat.exe (repo root), pywin32, Tk (stdlib).
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk

from highlight import HighlightOverlay
from lessons import STEPS, match_step, step_index
from praat_bridge import (
    find_praat_windows,
    is_praat_running,
    launch_praat,
    load_demo_sound,
    note_sound_loaded,
    probe_state,
)


class PraataoApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Praatao — coach (v0)")
        self.root.geometry("420x640+40+40")
        self.root.attributes("-topmost", True)
        self.root.minsize(380, 520)

        self.manual_advance: set[str] = set()
        self._busy = False
        self._expanded = False
        self._poll_after_id: str | None = None
        self._last_fp: tuple | None = None
        self._last_step_id: str | None = None
        self.highlight = HighlightOverlay()
        self.highlight.root.transient(self.root)

        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._schedule_poll()

    def _build(self) -> None:
        pad = {"padx": 12, "pady": 6}

        header = ttk.Frame(self.root)
        header.pack(fill="x", **pad)
        ttk.Label(header, text="Praatao", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(
            header,
            text="Guidance beside live Praat (prototype)",
            font=("Segoe UI", 9),
            foreground="#555",
        ).pack(anchor="w")

        self.status = ttk.Label(self.root, text="Status: …", font=("Segoe UI", 9), justify="left")
        self.status.pack(fill="x", **pad)

        self.progress = ttk.Label(self.root, text="", font=("Segoe UI", 9))
        self.progress.pack(fill="x", padx=12)

        self.step_title = ttk.Label(
            self.root, text="", font=("Segoe UI", 12, "bold"), wraplength=380
        )
        self.step_title.pack(fill="x", padx=12, pady=(10, 2))

        self.tip_short = ttk.Label(
            self.root, text="", font=("Segoe UI", 10), wraplength=380, justify="left"
        )
        self.tip_short.pack(fill="x", padx=12, pady=4)

        self.why = ttk.Label(
            self.root,
            text="",
            font=("Segoe UI", 9, "italic"),
            foreground="#666",
            wraplength=380,
            justify="left",
        )
        self.why.pack(fill="x", padx=12, pady=2)

        btns = ttk.Frame(self.root)
        btns.pack(fill="x", padx=12, pady=8)
        self.expand_btn = ttk.Button(btns, text="Expand explanation", command=self.toggle_expand)
        self.expand_btn.pack(side="left")
        ttk.Button(btns, text="Refresh now", command=self.refresh).pack(side="right")

        self.detail = tk.Text(
            self.root, height=10, wrap="word", font=("Segoe UI", 9), state="disabled"
        )
        self.detail.pack(fill="both", expand=True, padx=12, pady=4)

        actions = ttk.Frame(self.root)
        actions.pack(fill="x", padx=12, pady=8)
        ttk.Button(actions, text="Launch Praat", command=self.on_launch).pack(fill="x", pady=2)
        ttk.Button(actions, text="Load demo sound into Praat", command=self.on_load_demo).pack(
            fill="x", pady=2
        )
        self.continue_btn = ttk.Button(
            actions, text="Continue →", command=self.on_confirm
        )
        self.continue_btn.pack(fill="x", pady=2)

        self.action_hint = ttk.Label(
            self.root, text="", font=("Segoe UI", 9), foreground="#333", wraplength=380
        )
        self.action_hint.pack(fill="x", padx=12, pady=(0, 8))

        ttk.Label(
            self.root,
            text="Polling no longer uses select-all (that was flashing Praat’s menus).",
            font=("Segoe UI", 8),
            foreground="#888",
            wraplength=380,
        ).pack(fill="x", padx=12, pady=(0, 10))

    def _schedule_poll(self) -> None:
        self.refresh()
        # Slower poll: window titles + light selection probe; UI updates only on change
        self._poll_after_id = self.root.after(4000, self._schedule_poll)

    def toggle_expand(self) -> None:
        self._expanded = not self._expanded
        self.expand_btn.configure(text="Collapse" if self._expanded else "Expand explanation")
        if hasattr(self, "_current_step"):
            self._render_step(self._current_step, force_detail=True)

    def on_launch(self) -> None:
        try:
            if not is_praat_running():
                launch_praat()
            else:
                messagebox.showinfo("Praatao", "Praat already looks open.")
        except Exception as exc:
            messagebox.showerror("Praatao", str(exc))
        self.root.after(1200, self.refresh)

    def on_load_demo(self) -> None:
        def work() -> None:
            try:
                if not is_praat_running():
                    launch_praat()
                    import time

                    time.sleep(1.5)
                load_demo_sound()
                note_sound_loaded()
            except Exception as exc:
                self.root.after(0, lambda: messagebox.showerror("Praatao", str(exc)))
            finally:
                self.root.after(600, self.refresh)

        threading.Thread(target=work, daemon=True).start()

    def on_confirm(self) -> None:
        step = getattr(self, "_current_step", None)
        if step is None:
            return
        idx = step_index(step)
        for s in STEPS[: idx + 1]:
            self.manual_advance.add(s.id)
        self._last_fp = None  # force UI refresh
        self.refresh()

    def _set_detail(self, text: str) -> None:
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        if self._expanded:
            self.detail.insert("1.0", text)
        else:
            self.detail.insert("1.0", "(Expand to read the longer explanation.)")
        self.detail.configure(state="disabled")

    def _update_highlight(self, step_id: str) -> None:
        wins = find_praat_windows()
        objects = next((w for w in wins if w.kind == "objects"), None)
        editor = next((w for w in wins if w.kind == "editor"), None)

        if step_id in {"load-sound", "select-sound"}:
            self.highlight.show_on_window(objects, nx=0.05, ny=0.18, nw=0.45, nh=0.35)
        elif step_id == "view-edit":
            self.highlight.show_on_window(objects, nx=0.55, ny=0.32, nw=0.4, nh=0.12)
        elif step_id == "spectrogram":
            # Small corner marker only — full-width band felt like the UI was "refreshing"
            self.highlight.show_on_window(editor, nx=0.02, ny=0.02, nw=0.22, nh=0.08)
        else:
            self.highlight.hide()

    def _render_step(self, step, force_detail: bool = False) -> None:
        self.step_title.configure(text=step.title)
        self.tip_short.configure(text=step.tip_short)
        self.why.configure(text=f"Why this trips people up: {step.why_common}")
        self.action_hint.configure(text=f"Try: {step.action_hint}")
        self.progress.configure(text=f"Step {step_index(step) + 1} / {len(STEPS)} — {step.id}")
        if force_detail or self._last_step_id != step.id:
            self._set_detail(step.tip_long + "\n\n—\n" + step.why_common)
        self._update_highlight(step.id)
        self._last_step_id = step.id
        if step.id == "spectrogram":
            self.continue_btn.configure(text="Spectrogram OK — Continue →")
        elif step.id == "bonus-textgrid":
            self.continue_btn.configure(text="Finish / restart tips →")
        else:
            self.continue_btn.configure(text="Continue →")

    def refresh(self) -> None:
        if self._busy:
            return

        def work() -> None:
            self._busy = True
            err = None
            state = None
            try:
                state = probe_state()
            except Exception as exc:
                err = str(exc)
            finally:
                self._busy = False

            def apply() -> None:
                if err:
                    self.status.configure(text=f"Status: probe error — {err}")
                    return
                assert state is not None
                step = match_step(state, self.manual_advance)
                self._current_step = step

                fp = (state.fingerprint(), step.id, frozenset(self.manual_advance))
                if fp == self._last_fp:
                    return  # no visible change — do not thrash labels/highlight
                self._last_fp = fp

                sel = ", ".join(state.selected) if state.selected else "(none / unknown)"
                self.status.configure(
                    text=(
                        f"Praat: {'running' if state.running else 'not detected'}  |  "
                        f"editor: {'yes' if state.editor_open else 'no'}  |  "
                        f"sound known: {'yes' if state.has_sound else 'no'}\n"
                        f"Selected: {sel}"
                    )
                )
                self._render_step(step)

            self.root.after(0, apply)

        threading.Thread(target=work, daemon=True).start()

    def _on_close(self) -> None:
        if self._poll_after_id is not None:
            try:
                self.root.after_cancel(self._poll_after_id)
            except tk.TclError:
                pass
        self.highlight.destroy()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    PraataoApp().run()
