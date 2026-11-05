"""The Praatao settings window.

A small standalone window where the student decides

* which language the explanations are in (Chinese or English),
* whether the language model may be used at all,
* whether a picture of the drawing area may be sent to the model.

Everything is stored on this machine only, and every change takes effect
right away.
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6 import QtCore, QtGui, QtWidgets

ACCENT = "#E8590C"
SOFT = "#FDF6EC"
BORDER = "#E7D9C4"
FG = "#1F2933"
MUTED = "#7A6A58"
WARN_BG = "#FFF1DC"
WARN_FG = "#8A4B08"

__all__ = ["QtSettingsWindow"]


class QtSettingsWindow:
    """A frameless-ish small window with the three settings."""

    def __init__(
        self,
        master: Any = None,
        lang: str = "zh",
        settings: Any = None,
        on_apply: Callable[[Any], None] | None = None,
    ) -> None:
        self.master = master
        self.lang = lang
        self.settings = settings
        self.on_apply = on_apply
        # Called when the student closes this window.
        self.on_close = None  # callback() -> None

        self.win = QtWidgets.QWidget()
        self.win.setWindowTitle(self._t("Praatao 设置", "Praatao settings"))
        self._watch_close()
        self.win.setWindowFlags(
            QtCore.Qt.WindowType.Tool | QtCore.Qt.WindowType.WindowStaysOnTopHint
        )
        self.win.setMinimumWidth(380)

        outer = QtWidgets.QVBoxLayout(self.win)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        accent = QtWidgets.QFrame()
        accent.setFixedHeight(3)
        accent.setStyleSheet(f"background:{ACCENT};")
        outer.addWidget(accent)

        body = QtWidgets.QVBoxLayout()
        body.setContentsMargins(16, 14, 16, 14)
        body.setSpacing(10)
        outer.addLayout(body)

        title = QtWidgets.QLabel(self._t("Praatao 设置", "Praatao settings"))
        title.setStyleSheet(f"color:{ACCENT}; font-size:15px; font-weight:600;")
        body.addWidget(title)

        intro = QtWidgets.QLabel(
            self._t(
                "这些设置只保存在这台电脑上，随时可以改。",
                "These settings stay on this computer and can be changed any time.",
            )
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color:{MUTED}; font-size:11px;")
        body.addWidget(intro)

        # -- language --------------------------------------------------
        body.addWidget(self._group_label(self._t("语言", "Language")))
        self.language_box = QtWidgets.QComboBox()
        self.language_box.addItem(self._t("中文", "Chinese"), "zh")
        self.language_box.addItem("English", "en")
        self.language_box.setStyleSheet(self._combo_style())
        current = getattr(settings, "lang", lang) or lang
        index = self.language_box.findData(current)
        if index >= 0:
            self.language_box.setCurrentIndex(index)
        body.addWidget(self.language_box)

        # -- the model -------------------------------------------------
        body.addWidget(self._group_label(self._t("大模型", "Language model")))
        self.llm_box = QtWidgets.QCheckBox(
            self._t(
                "允许使用大模型（本地知识库始终可用）",
                "Allow the language model (the local knowledge base always works)",
            )
        )
        self.llm_box.setChecked(bool(getattr(settings, "use_llm", True)))
        self.llm_box.setStyleSheet(f"color:{FG}; font-size:12px;")
        body.addWidget(self.llm_box)

        self.vision_box = QtWidgets.QCheckBox(
            self._t(
                "允许把绘图区的截图发给模型（默认关闭）",
                "Allow sending a picture of the drawing area to the model (off by default)",
            )
        )
        self.vision_box.setChecked(bool(getattr(settings, "allow_vision", False)))
        self.vision_box.setStyleSheet(f"color:{FG}; font-size:12px;")
        body.addWidget(self.vision_box)

        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet(
            f"background:{SOFT}; border:1px solid {BORDER}; border-radius:8px;"
            f"padding:8px; color:{FG}; font-size:11px;"
        )
        body.addWidget(self.status)

        # -- buttons ---------------------------------------------------
        buttons = QtWidgets.QHBoxLayout()
        buttons.setSpacing(6)
        buttons.addStretch(1)
        self.apply_button = QtWidgets.QPushButton(
            self._t("保存并应用", "Save and apply")
        )
        self.apply_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.apply_button.setStyleSheet(
            f"QPushButton{{background:{ACCENT}; color:#ffffff; border:none;"
            "border-radius:6px; padding:6px 14px; font-size:11px;}"
            "QPushButton:hover{background:#C9630F;}"
        )
        self.apply_button.clicked.connect(self.apply)
        buttons.addWidget(self.apply_button)

        close_button = QtWidgets.QPushButton(self._t("关闭", "Close"))
        close_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        close_button.setStyleSheet(
            f"QPushButton{{background:{SOFT}; color:{FG}; border:1px solid {BORDER};"
            "border-radius:6px; padding:6px 14px; font-size:11px;}"
        )
        close_button.clicked.connect(self.hide)
        buttons.addWidget(close_button)
        body.addLayout(buttons)

        self.win.hide()
        self.set_status()

    # -- helpers ----------------------------------------------------
    def _t(self, zh: str, en: str) -> str:
        return zh if self.lang == "zh" else en

    def _watch_close(self) -> None:
        """Closing the settings window is closing the coach."""

        try:
            from praatao.ui.qt.close_watch import watch_close

            watch_close(self.win, self)
        except Exception:  # noqa: BLE001
            pass

    def _group_label(self, text: str) -> QtWidgets.QLabel:
        label = QtWidgets.QLabel(text)
        label.setStyleSheet(f"color:{MUTED}; font-size:11px; font-weight:600;")
        return label

    def _combo_style(self) -> str:
        return (
            f"QComboBox{{background:{SOFT}; border:1px solid {BORDER};"
            "border-radius:8px; padding:6px 8px; color:#1F2933; font-size:12px;}"
        )

    def set_status(self, text: str = "") -> None:
        """Show a short line about what is running."""

        if text:
            self.status.setText(text)
            return
        llm = self.llm_box.isChecked()
        vision = self.vision_box.isChecked()
        if self.lang == "zh":
            self.status.setText(
                "大模型：{}；绘图区截图：{}。\n"
                "关闭大模型后，讲解层只用本地知识库，完全离线。".format(
                    "已开启" if llm else "已关闭",
                    "允许" if vision else "不允许",
                )
            )
        else:
            self.status.setText(
                "Model: {}. Pictures of the drawing area: {}.\n"
                "With the model off the coach only uses the local knowledge "
                "base and works completely offline.".format(
                    "on" if llm else "off",
                    "allowed" if vision else "not allowed",
                )
            )

    def set_lang(self, lang: str) -> None:
        """Switch the language of this window (it is rebuilt by the caller)."""

        self.lang = lang

    def values(self) -> dict:
        """What the student chose."""

        return {
            "lang": self.language_box.currentData() or "zh",
            "use_llm": bool(self.llm_box.isChecked()),
            "allow_vision": bool(self.vision_box.isChecked()),
        }

    def apply(self) -> None:
        """Hand the choices to the application and store them."""

        from ...settings import Settings

        values = self.values()
        settings = Settings(**values)
        if self.on_apply is not None:
            try:
                self.on_apply(settings)
            except Exception:  # noqa: BLE001 - a setting must never crash it
                pass
        settings.save()
        self.set_status()

    def show(self) -> None:
        self.win.show()
        self.win.raise_()

    def hide(self) -> None:
        self.win.hide()

    def is_visible(self) -> bool:
        try:
            return bool(self.win.isVisible())
        except Exception:  # noqa: BLE001
            return False

    def toggle(self) -> None:
        if self.is_visible():
            self.hide()
        else:
            self.show()

    def destroy(self) -> None:
        try:
            self.win.close()
            self.win.deleteLater()
        except Exception:  # noqa: BLE001
            pass
