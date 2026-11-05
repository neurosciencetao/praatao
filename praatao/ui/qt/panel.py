"""Side panel, drawn with Qt.

Same job as the Tk panel - lesson progress, live Praat state, and a
free-text question box - but with the typography and spacing of a real
desktop widget.
"""

from __future__ import annotations

from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets

__all__ = ["QtSidePanel"]

BG = "#FFFFFF"
FG = "#1F2933"
MUTED = "#6B7A89"
ACCENT = "#B4530A"
SOFT = "#FDF6EC"
BORDER = "#E3D9C6"
WARN_BG = "#FFF4E5"
WARN_FG = "#8A3B12"


class QtSidePanel:
    """A small always-on-top companion window."""

    def __init__(self, master: Any = None, lang: str = "zh") -> None:
        self.master = master
        self.lang = lang
        self.on_ask = None  # callback(question: str) -> str
        self.on_command = None  # callback(name: str) -> None
        # Called when the student closes this window.  Closing the panel
        # means "I am done", so the whole coach leaves with it.
        self.on_close = None  # callback() -> None

        self.win = QtWidgets.QWidget()
        self.win.setWindowTitle("Praatao")
        self._watch_close()
        self.win.setWindowFlags(
            QtCore.Qt.WindowType.Tool | QtCore.Qt.WindowType.WindowStaysOnTopHint
        )
        self.win.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.win.setMinimumSize(320, 320)
        self.win.resize(390, 540)

        outer = QtWidgets.QVBoxLayout(self.win)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        accent = QtWidgets.QFrame()
        accent.setFixedHeight(3)
        accent.setStyleSheet(f"background:{ACCENT};")
        outer.addWidget(accent)

        body = QtWidgets.QVBoxLayout()
        body.setContentsMargins(14, 12, 14, 12)
        body.setSpacing(8)
        outer.addLayout(body, 1)

        title_row = QtWidgets.QHBoxLayout()
        self.title_label = QtWidgets.QLabel(self._t("Praatao 助手", "Praatao coach"))
        self.title_label.setStyleSheet(
            f"color:{ACCENT}; font-size:15px; font-weight:600;"
        )
        title_row.addWidget(self.title_label)
        title_row.addStretch(1)
        # The live Praat state and the lesson progress are two different
        # things, so they get two labels; one label would make them
        # overwrite each other.
        self.state_label = QtWidgets.QLabel("")
        self.state_label.setStyleSheet(f"color:{MUTED}; font-size:10px;")
        title_row.addWidget(self.state_label)
        self.progress_label = QtWidgets.QLabel("")
        self.progress_label.setStyleSheet(f"color:{MUTED}; font-size:10px;")
        title_row.addWidget(self.progress_label)
        body.addLayout(title_row)

        self.notice = QtWidgets.QLabel("")
        self.notice.setWordWrap(True)
        self.notice.setStyleSheet(
            f"background:{WARN_BG}; color:{WARN_FG}; font-size:10px;"
            "border-radius:6px; padding:6px;"
        )
        self.notice.hide()
        body.addWidget(self.notice)

        self.lesson_title = QtWidgets.QLabel(
            self._t("未开始课程", "No lesson running")
        )
        self.lesson_title.setStyleSheet(f"color:{FG}; font-size:12px; font-weight:600;")
        self.lesson_title.setWordWrap(True)
        body.addWidget(self.lesson_title)

        self.lesson_body = QtWidgets.QTextBrowser()
        self.lesson_body.setOpenExternalLinks(False)
        self.lesson_body.setStyleSheet(
            f"QTextBrowser{{background:{SOFT}; border:1px solid {BORDER};"
            "border-radius:8px; padding:8px; color:#1F2933; font-size:12px;}"
        )
        body.addWidget(self.lesson_body, 1)

        btns = QtWidgets.QHBoxLayout()
        btns.setSpacing(6)
        self._button(btns, self._t("上一步", "Back"), lambda: self._command("prev"))
        self._button(btns, self._t("下一步", "Next"), lambda: self._command("next"))
        self._button(btns, self._t("重开", "Restart"), lambda: self._command("restart"))
        self._button(btns, self._t("隐藏", "Hide"), lambda: self._command("hide"))
        self._button(btns, self._t("设置", "Settings"), lambda: self._command("settings"))
        body.addLayout(btns)

        # The way to report a problem: a small quiet button, because a
        # beginner should find it but not be bothered by it.
        report_row = QtWidgets.QHBoxLayout()
        report_row.setSpacing(6)
        report_row.addStretch(1)
        self._button(report_row, self._t("报告问题", "Report a problem"),
                     lambda: self._command("feedback"))
        body.addLayout(report_row)

        self.lesson_picker = QtWidgets.QListWidget()
        self.lesson_picker.setStyleSheet(
            f"QListWidget{{background:{SOFT}; border:1px solid {BORDER};"
            "border-radius:8px; color:#1F2933; font-size:12px; padding:4px;}"
            f"QListWidget::item:selected{{background:#FFE8CC; color:#1F2933;}}"
        )
        self.lesson_picker.setMaximumHeight(110)
        self.lesson_picker.itemSelectionChanged.connect(self._on_pick)
        body.addWidget(self.lesson_picker)

        ask_row = QtWidgets.QHBoxLayout()
        ask_row.setSpacing(6)
        self.ask_entry = QtWidgets.QLineEdit()
        self.ask_entry.setPlaceholderText(
            self._t("问点什么…（例如：什么是共振峰？）",
                    "Ask something… (e.g. what is a formant?)")
        )
        self.ask_entry.setStyleSheet(
            f"QLineEdit{{background:{SOFT}; border:1px solid {BORDER};"
            "border-radius:8px; padding:6px 8px; font-size:12px;}"
        )
        self.ask_entry.returnPressed.connect(self._do_ask)
        ask_row.addWidget(self.ask_entry, 1)
        self._button(ask_row, self._t("提问", "Ask"), self._do_ask, primary=True)
        body.addLayout(ask_row)

        self.answer = QtWidgets.QTextBrowser()
        self.answer.setOpenExternalLinks(False)
        self.answer.setStyleSheet(
            f"QTextBrowser{{background:{SOFT}; border:1px solid {BORDER};"
            "border-radius:8px; padding:8px; color:#1F2933; font-size:12px;}"
        )
        body.addWidget(self.answer, 1)

        self.win.hide()

    # -- helpers ----------------------------------------------------
    def _t(self, zh: str, en: str) -> str:
        return zh if self.lang == "zh" else en

    def _button(
        self,
        parent: QtWidgets.QHBoxLayout,
        text: str,
        command,
        primary: bool = False,
    ) -> None:
        button = QtWidgets.QPushButton(text)
        button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet(
            "QPushButton{background:%s; color:%s; border:none; border-radius:6px;"
            "padding:5px 10px; font-size:11px;}"
            "QPushButton:hover{background:%s;}"
            % (
                ACCENT if primary else SOFT,
                "#ffffff" if primary else FG,
                "#C9630F" if primary else "#F3E6D2",
            )
        )
        button.clicked.connect(command)
        parent.addWidget(button)

    def _command(self, name: str) -> None:
        if self.on_command:
            self.on_command(name)

    def _watch_close(self) -> None:
        """Closing the panel means the student is done with the coach."""

        try:
            from praatao.ui.qt.close_watch import watch_close

            watch_close(self.win, self)
        except Exception:  # noqa: BLE001
            pass

    def _on_pick(self) -> None:
        items = self.lesson_picker.selectedItems()
        if items and self.on_command:
            self.on_command(f"select:{items[0].data(QtCore.Qt.ItemDataRole.UserRole)}")

    def _do_ask(self) -> None:
        question = self.ask_entry.text().strip()
        if not question:
            return
        self.ask_entry.clear()
        self.set_answer(self._t("思考中…", "Thinking…"))
        if self.on_ask:
            answer = self.on_ask(question)
            if answer is not None:
                self.set_answer(answer)

    # -- public API -------------------------------------------------
    def set_lessons(self, lessons: list[tuple[str, str]]) -> None:
        """``lessons`` is a list of ``(id, display_title)``."""

        self.lesson_picker.clear()
        for lid, title in lessons:
            item = QtWidgets.QListWidgetItem(f"{title}  [{lid}]")
            item.setData(QtCore.Qt.ItemDataRole.UserRole, lid)
            self.lesson_picker.addItem(item)

    def set_lesson(self, title: str, body: str, progress: tuple[int, int]) -> None:
        self.lesson_title.setText(title)
        self.lesson_body.setPlainText(body)
        done, total = progress
        self.progress_label.setText(f"{done}/{total}")

    def set_state(self, text: str) -> None:
        self.state_label.setText(text)

    def set_notice(self, text: str) -> None:
        self.notice.setText(text or "")
        self.notice.setVisible(bool(text))

    def set_answer(self, text: str) -> None:
        self.answer.setPlainText(text)

    def show(self) -> None:
        self.win.show()
        self.raise_()

    def raise_(self) -> None:
        """Bring the panel to the front of our own windows.

        Without ``SWP_NOACTIVATE`` the panel would take the focus, and the
        student would lose the keyboard while typing in Praat.
        """

        try:
            self.win.raise_()
            hwnd = int(self.win.winId())
        except Exception:  # noqa: BLE001
            return
        try:
            import win32gui

            win32gui.SetWindowPos(
                hwnd,
                win32gui.HWND_TOP,
                0,
                0,
                0,
                0,
                0x0010  # SWP_NOACTIVATE
                | 0x0040,  # SWP_SHOWWINDOW
            )
        except Exception:  # noqa: BLE001
            pass

    def hide(self) -> None:
        self.win.hide()

    def is_visible(self) -> bool:
        """Is the panel on screen?"""

        try:
            return bool(self.win.isVisible())
        except Exception:  # noqa: BLE001
            return False

    def geometry(self) -> tuple[int, int, int, int]:
        """The panel's rectangle on screen."""

        try:
            rect = self.win.geometry()
            return (rect.x(), rect.y(), rect.x() + rect.width(), rect.y() + rect.height())
        except Exception:  # noqa: BLE001
            return (0, 0, 0, 0)

    def toggle(self) -> None:
        if self.win.isVisible():
            self.hide()
        else:
            self.show()

    def destroy(self) -> None:
        try:
            self.win.close()
            self.win.deleteLater()
        except Exception:  # noqa: BLE001
            pass
