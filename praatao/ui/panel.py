"""Side panel: lesson progress, live state, and a free-text question box."""

from __future__ import annotations

import tkinter as tk
from tkinter import scrolledtext

from .overlay import keep_on_top

BG = "#ffffff"
FG = "#1f2933"
MUTED = "#6b7a89"
ACCENT = "#b4530a"
SOFT = "#fdf6ec"
BORDER = "#e3d9c6"


class SidePanel:
    """A small always-on-top companion window."""

    def __init__(self, master: tk.Tk, lang: str = "zh") -> None:
        self.master = master
        self.lang = lang
        self.on_ask = None  # callback(question: str) -> str
        self.on_command = None  # callback(name: str) -> None
        # Called when the student closes this window.
        self.on_close = None  # callback() -> None

        self.win = tk.Toplevel(master)
        self.win.title("Praatao")
        self.win.configure(bg=BG)
        self.win.geometry("380x520+40+120")
        self.win.minsize(320, 320)
        try:
            self.win.protocol("WM_DELETE_WINDOW", self._on_close)
        except Exception:  # noqa: BLE001
            pass

        header = tk.Frame(self.win, bg=BORDER, height=3)
        header.pack(fill="x")

        title_row = tk.Frame(self.win, bg=BG)
        title_row.pack(fill="x", padx=12, pady=(10, 4))
        self.title_label = tk.Label(
            title_row, text=self._t("Praatao 助手", "Praatao coach"),
            bg=BG, fg=ACCENT, font=("Microsoft YaHei UI", 12, "bold"),
        )
        self.title_label.pack(side="left")
        self.state_label = tk.Label(
            title_row, text="", bg=BG, fg=MUTED, font=("Microsoft YaHei UI", 8),
        )
        self.state_label.pack(side="right")

        self.notice = tk.Label(
            self.win, text="", bg="#fff4e5", fg="#8a3b12", anchor="w",
            justify="left", wraplength=340, font=("Microsoft YaHei UI", 8),
        )

        # -- lesson section -----------------------------------------
        self.lesson_title = tk.Label(
            self.win, text=self._t("未开始课程", "No lesson running"),
            bg=BG, fg=FG, anchor="w", justify="left",
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        self.lesson_title.pack(fill="x", padx=12, pady=(4, 2))

        self.lesson_body = scrolledtext.ScrolledText(
            self.win, height=9, wrap="word", relief="flat", borderwidth=0,
            bg=SOFT, fg=FG, font=("Microsoft YaHei UI", 9), padx=8, pady=6,
        )
        self.lesson_body.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self.lesson_body.configure(state="disabled")

        btns = tk.Frame(self.win, bg=BG)
        btns.pack(fill="x", padx=12, pady=(0, 8))
        self._button(btns, self._t("上一步", "Back"), lambda: self._command("prev"))
        self._button(btns, self._t("下一步", "Next"), lambda: self._command("next"))
        self._button(btns, self._t("重开", "Restart"), lambda: self._command("restart"))
        self._button(btns, self._t("隐藏", "Hide"), lambda: self._command("hide"))

        # -- lesson picker ------------------------------------------
        picker = tk.Frame(self.win, bg=BG)
        picker.pack(fill="x", padx=12)
        self.lesson_picker = tk.Listbox(
            picker, height=4, relief="flat", borderwidth=0, bg=SOFT, fg=FG,
            font=("Microsoft YaHei UI", 9), highlightthickness=1,
            highlightbackground=BORDER, selectbackground="#ffe8cc",
            selectforeground=FG, activestyle="none",
        )
        self.lesson_picker.pack(side="left", fill="both", expand=True)
        self.lesson_picker.bind("<<ListboxSelect>>", self._on_pick)

        # -- question box -------------------------------------------
        ask_row = tk.Frame(self.win, bg=BG)
        ask_row.pack(fill="x", padx=12, pady=(10, 4))
        self.ask_entry = tk.Entry(
            ask_row, font=("Microsoft YaHei UI", 9), relief="flat", bd=0,
            highlightthickness=1, highlightbackground=BORDER,
        )
        self.ask_entry.pack(side="left", fill="x", expand=True, ipady=4)
        self.ask_entry.bind("<Return>", lambda _e: self._do_ask())
        self._button(ask_row, self._t("提问", "Ask"), self._do_ask, primary=True)

        self.answer = scrolledtext.ScrolledText(
            self.win, height=9, wrap="word", relief="flat", borderwidth=0,
            bg=SOFT, fg=FG, font=("Microsoft YaHei UI", 9), padx=8, pady=6,
        )
        self.answer.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.answer.configure(state="disabled")

        keep_on_top(self.win)

    # -- helpers ----------------------------------------------------
    def _t(self, zh: str, en: str) -> str:
        return zh if self.lang == "zh" else en

    def _button(self, parent, text, command, primary: bool = False) -> None:
        tk.Button(
            parent, text=text, command=command, relief="flat", bd=0,
            bg=ACCENT if primary else SOFT, fg="#ffffff" if primary else FG,
            activebackground="#c9630f" if primary else "#f3e6d2",
            font=("Microsoft YaHei UI", 9), padx=8, pady=3, cursor="hand2",
        ).pack(side="left", padx=(0, 6))

    def _command(self, name: str) -> None:
        if self.on_command:
            self.on_command(name)

    def _on_close(self) -> None:
        """Closing the panel means the student is done with the coach."""

        callback = self.on_close
        if callback is not None:
            try:
                callback()
            except Exception:  # noqa: BLE001
                pass
        try:
            self.win.destroy()
        except Exception:  # noqa: BLE001
            pass

    def _on_pick(self, _event=None) -> None:
        sel = self.lesson_picker.curselection()
        if sel and self.on_command:
            self.on_command(f"select:{self.lesson_picker.get(sel[0])}")

    def _do_ask(self) -> None:
        q = self.ask_entry.get().strip()
        if not q:
            return
        self.ask_entry.delete(0, "end")
        self.set_answer(self._t("思考中…", "Thinking…"))
        if self.on_ask:
            answer = self.on_ask(q)
            if answer is not None:
                self.set_answer(answer)

    # -- public API -------------------------------------------------
    def set_lessons(self, lessons: list[tuple[str, str]]) -> None:
        """``lessons`` is a list of ``(id, display_title)``."""
        self.lesson_picker.delete(0, "end")
        for lid, title in lessons:
            self.lesson_picker.insert("end", f"{title}  [{lid}]")

    def set_lesson(self, title: str, body: str, progress: tuple[int, int]) -> None:
        self.lesson_title.configure(text=title)
        self.lesson_body.configure(state="normal")
        self.lesson_body.delete("1.0", "end")
        self.lesson_body.insert("end", body)
        self.lesson_body.configure(state="disabled")
        done, total = progress
        self.state_label.configure(text=f"{done}/{total}")

    def set_state(self, text: str) -> None:
        self.state_label.configure(text=text)

    def set_notice(self, text: str) -> None:
        """Show (or clear) a warning strip under the header."""
        self.notice.configure(text=text or "")
        if text:
            if not self.notice.winfo_ismapped():
                self.notice.pack(fill="x", padx=8, pady=(4, 0))
        else:
            self.notice.pack_forget()

    def set_answer(self, text: str) -> None:
        self.answer.configure(state="normal")
        self.answer.delete("1.0", "end")
        self.answer.insert("end", text)
        self.answer.configure(state="disabled")

    def show(self) -> None:
        self.win.deiconify()
        keep_on_top(self.win)

    def hide(self) -> None:
        self.win.withdraw()

    def toggle(self) -> None:
        if self.win.winfo_viewable():
            self.hide()
        else:
            self.show()

    def is_visible(self) -> bool:
        """Is the panel on screen?"""

        try:
            return bool(self.win.winfo_viewable())
        except tk.TclError:
            return False

    def geometry(self) -> tuple[int, int, int, int]:
        """The panel's rectangle on screen."""

        try:
            x = self.win.winfo_rootx()
            y = self.win.winfo_rooty()
            return (x, y, x + self.win.winfo_width(), y + self.win.winfo_height())
        except tk.TclError:
            return (0, 0, 0, 0)

    def destroy(self) -> None:
        try:
            self.win.destroy()
        except tk.TclError:
            pass
