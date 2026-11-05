"""The window where a student reports a problem.

The student writes what happened and, if they want to be answered, their
email address.  The report is not sent silently: the program opens
GitHub's "new issue" page with everything filled in, and the student
presses the button there.  A copy is kept on the machine as well.
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6 import QtCore, QtWidgets

from praatao.ui.qt.settings import ACCENT, BORDER, FG, MUTED, SOFT, WARN_BG, WARN_FG

__all__ = ["QtFeedbackWindow"]


class QtFeedbackWindow:
    """A small window: what happened, and an email address."""

    def __init__(
        self,
        master: Any = None,
        lang: str = "zh",
        on_submit: Callable[[str, str], None] | None = None,
        on_save: Callable[[str, str], None] | None = None,
    ) -> None:
        self.master = master
        self.lang = lang
        self.on_submit = on_submit
        self.on_save = on_save
        self.on_close = None  # callback() -> None

        self.win = QtWidgets.QWidget()
        self.win.setWindowTitle(
            self._t("报告一个问题", "Report a problem")
        )
        self.win.setWindowFlags(
            QtCore.Qt.WindowType.Tool | QtCore.Qt.WindowType.WindowStaysOnTopHint
        )
        self.win.setMinimumWidth(460)
        from praatao.ui.qt.close_watch import watch_close

        watch_close(self.win, self)

        outer = QtWidgets.QVBoxLayout(self.win)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(8)

        title = QtWidgets.QLabel(
            self._t("遇到了什么问题？", "What went wrong?")
        )
        title.setStyleSheet(f"color:{ACCENT}; font-size:14px; font-weight:600;")
        outer.addWidget(title)

        self.text = QtWidgets.QTextEdit()
        self.text.setPlaceholderText(
            self._t(
                "例如：我在 Formants 菜单里悬停，卡片讲的是波形而不是共振峰。",
                "For example: I hovered in the Formants menu and the card "
                "explained the waveform instead of the formants.",
            )
        )
        self.text.setStyleSheet(
            f"QTextEdit{{background:{SOFT}; border:1px solid {BORDER};"
            "border-radius:8px; padding:8px; color:#1F2933; font-size:12px;}"
        )
        self.text.setFixedHeight(130)
        outer.addWidget(self.text)

        email_label = QtWidgets.QLabel(
            self._t(
                "邮箱（可选）：这样我们能回复你。它会写进 issue 里，别人也看得到。",
                "Email (optional): so we can answer you. It goes into the "
                "issue, where other people can read it too.",
            )
        )
        email_label.setWordWrap(True)
        email_label.setStyleSheet(f"color:{MUTED}; font-size:11px;")
        outer.addWidget(email_label)

        self.email = QtWidgets.QLineEdit()
        self.email.setPlaceholderText(self._t("name@example.com", "name@example.com"))
        self.email.setStyleSheet(
            f"QLineEdit{{background:{SOFT}; border:1px solid {BORDER};"
            "border-radius:8px; padding:6px 8px; color:#1F2933; font-size:12px;}"
        )
        outer.addWidget(self.email)

        note = QtWidgets.QLabel(
            self._t(
                "按「在 GitHub 上提交」会打开 GitHub 的新问题页面，"
                "内容已经填好，你确认之后再发。一份副本也会存在这台电脑上。",
                "Press the button and GitHub's new-issue page opens with "
                "everything filled in; you send it yourself. A copy is also "
                "kept on this computer.",
            )
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"background:{WARN_BG}; color:{WARN_FG}; font-size:10px;"
                           "border-radius:6px; padding:6px;")
        outer.addWidget(note)

        buttons = QtWidgets.QHBoxLayout()
        buttons.setSpacing(6)
        self._button(buttons, self._t("在 GitHub 上提交", "Open on GitHub"),
                     self._submit, primary=True)
        self._button(buttons, self._t("只存到本地", "Save locally"), self._save)
        self._button(buttons, self._t("取消", "Cancel"), self.hide)
        outer.addLayout(buttons)

        self.win.hide()

    # -- helpers ----------------------------------------------------
    def _t(self, zh: str, en: str) -> str:
        return zh if self.lang == "zh" else en

    def _button(
        self,
        parent: QtWidgets.QHBoxLayout,
        label: str,
        command: Callable[[], None],
        primary: bool = False,
    ) -> None:
        button = QtWidgets.QPushButton(label)
        button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        if primary:
            button.setStyleSheet(
                f"QPushButton{{background:{ACCENT}; color:#FFFFFF; border:none;"
                "border-radius:8px; padding:6px 12px; font-size:12px;}"
            )
        else:
            button.setStyleSheet(
                f"QPushButton{{background:{SOFT}; color:{FG}; border:1px solid {BORDER};"
                "border-radius:8px; padding:6px 12px; font-size:12px;}"
            )
        button.clicked.connect(command)
        parent.addWidget(button)

    # -- actions ----------------------------------------------------
    def _submit(self) -> None:
        feedback = self.text.toPlainText().strip()
        if not feedback:
            return
        email = self.email.text().strip()
        if self.on_submit is not None:
            self.on_submit(feedback, email)
        self.hide()

    def _save(self) -> None:
        feedback = self.text.toPlainText().strip()
        if not feedback:
            return
        email = self.email.text().strip()
        if self.on_save is not None:
            self.on_save(feedback, email)
        self.hide()

    # -- window -----------------------------------------------------
    def show(self) -> None:
        self.win.show()
        self.win.raise_()
        self.text.setFocus()

    def hide(self) -> None:
        try:
            self.win.hide()
        except Exception:  # noqa: BLE001
            pass

    def is_visible(self) -> bool:
        try:
            return bool(self.win.isVisible())
        except Exception:  # noqa: BLE001
            return False

    def destroy(self) -> None:
        try:
            self.win.close()
            self.win.deleteLater()
        except Exception:  # noqa: BLE001
            pass
