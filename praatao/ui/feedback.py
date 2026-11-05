"""The Tk fallback for the feedback window.

The Qt front-end has its own window; this is the plain version for the
computers that do not have PySide6.  It asks the same two questions.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import simpledialog

__all__ = ["ask_feedback"]


def ask_feedback(
    master: tk.Misc, lang: str = "zh"
) -> tuple[str, str] | None:
    """Ask what happened and for an email address.

    Returns ``(feedback, email)`` or ``None`` when the student cancels.
    """

    if lang == "zh":
        title = "报告一个问题"
        prompt = "遇到了什么问题？\n（越具体越好）"
        email_prompt = "邮箱（可选，用来回复你）："
        email_title = "邮箱"
    else:
        title = "Report a problem"
        prompt = "What went wrong?\n(the more detail the better)"
        email_prompt = "Email (optional, so we can answer you):"
        email_title = "Email"

    feedback = simpledialog.askstring(
        title, prompt, parent=master, initialvalue=""
    )
    if feedback is None:
        return None
    feedback = feedback.strip()
    if not feedback:
        return None
    email = simpledialog.askstring(
        email_title, email_prompt, parent=master, initialvalue=""
    )
    email = (email or "").strip()
    return feedback, email
