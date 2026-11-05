"""Starting Praatao without a console window, and without a manual.

The student double-clicks one icon.  What has to happen then is:

* Praat has to be running, and it has to be in front (otherwise there is
  nothing to look at),
* the coach has to start without a black console window in the way,
* the student has to get *some* sign that it worked, because a program
  that says nothing looks broken,
* the student has to be able to find the controls again later, without
  knowing the hotkeys.

This module holds that logic: :func:`ensure_praat`, the little
notification window (:class:`Toast`) and the tray icon (:class:`Tray`).
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

__all__ = [
    "ensure_praat",
    "praat_running",
    "start_praat",
    "bring_praat_to_front",
    "Toast",
    "Tray",
]


# --------------------------------------------------------------------------
# Praat
# --------------------------------------------------------------------------
def _praat_exe() -> Path:
    from . import paths

    return Path(paths.PRAAT_EXE)


def praat_running() -> bool:
    """Is a Praat process alive?"""

    if sys.platform == "win32":
        try:
            import win32process  # noqa: F401

            import uiautomation

            for window in uiautomation.GetWindows():
                try:
                    name = (window.Name or "")
                    cls = (window.ClassName or "")
                except Exception:  # noqa: BLE001
                    continue
                if "praat" in cls.casefold() or name.casefold().startswith("praat"):
                    return True
            return False
        except Exception:  # noqa: BLE001
            pass
    # Fall back to the task list.
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq Praat.exe"],
            capture_output=True, text=True, timeout=10,
        )
        return "Praat.exe" in (result.stdout or "")
    except Exception:  # noqa: BLE001
        return False


def start_praat(wait_seconds: float = 25.0) -> bool:
    """Start Praat and wait until its Objects window is there."""

    exe = _praat_exe()
    if not exe.exists():
        return False
    try:
        subprocess.Popen([str(exe)], cwd=str(exe.parent))
    except Exception:  # noqa: BLE001
        return False

    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        if _objects_window() is not None:
            return True
        time.sleep(0.4)
    return _objects_window() is not None


def _objects_window() -> Any:
    try:
        from .sensors.uia import PraatUI

        return PraatUI().objects_window()
    except Exception:  # noqa: BLE001
        return None


def bring_praat_to_front() -> bool:
    """Put the Praat Objects window in front (without stealing focus later)."""

    try:
        from .sensors.uia import PraatUI

        ui = PraatUI()
        window = ui.objects_window()
        if window is None:
            return False
        ui._activate(window)
        return True
    except Exception:  # noqa: BLE001
        return False


def ensure_praat(start_if_missing: bool = True) -> dict[str, Any]:
    """Make sure Praat is running and visible.

    Returns what happened, so the caller can tell the student:
    ``{"already": True}`` or ``{"started": True}`` or ``{"failed": True}``.
    """

    if praat_running():
        window = _objects_window()
        if window is None:
            # Praat is running but has no window yet (it is still starting).
            deadline = time.time() + 10.0
            while time.time() < deadline:
                window = _objects_window()
                if window is not None:
                    break
                time.sleep(0.3)
        bring_praat_to_front()
        return {"already": True, "window": window is not None}

    if not start_if_missing:
        return {"failed": True}

    exe = _praat_exe()
    if not exe.exists():
        return {"failed": True, "reason": "no praat.exe"}
    started = start_praat()
    if started:
        bring_praat_to_front()
    return {"started": started, "failed": not started}


# --------------------------------------------------------------------------
# The little window that says "it works"
# --------------------------------------------------------------------------
class SingleInstance:
    """Only one coach at a time.

    A beginner who double-clicks the shortcut twice should not end up with
    two tray icons and two coaches fighting over the mouse.  The second
    copy tells the first one to come forward and then leaves.

    Two pieces do the work:

    * a Windows mutex says whether another coach is running.  On Windows
      ``QLocalServer.listen()`` succeeds even when the pipe already
      exists, so the socket alone cannot answer that question.
    * a local socket (a named pipe on Windows) carries the message
      "come forward" from the second copy to the first one.
    """

    SOCKET_NAME = "praatao-coach-single-instance"
    MUTEX_NAME = "Local\\PraataoCoachSingleton"
    _ERROR_ALREADY_EXISTS = 183

    def __init__(self, on_show: Any = None) -> None:
        self.on_show = on_show
        self._server: Any = None
        self._mutex: Any = None

    def acquire(self) -> bool:
        """True when this process is the one and only coach."""

        if not self._take_the_mutex():
            # Another coach is running: ask it to come forward and leave.
            self._talk_to_running()
            return False
        self._start_server()
        return True

    # -- the mutex ---------------------------------------------------
    def _take_the_mutex(self) -> bool:
        """True when we are the first coach.  False when one is running."""

        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            kernel32.CreateMutexW.restype = ctypes.c_void_p
            handle = kernel32.CreateMutexW(None, False, self.MUTEX_NAME)
            if not handle:
                # Cannot tell; carry on rather than refuse to start.
                return True
            already = kernel32.GetLastError() == self._ERROR_ALREADY_EXISTS
            if already:
                kernel32.CloseHandle(ctypes.c_void_p(handle))
                return False
            self._mutex = ctypes.c_void_p(handle)
            return True
        except Exception:  # noqa: BLE001
            return True

    # -- the socket --------------------------------------------------
    def _start_server(self) -> None:
        """Open the door for a second copy to knock on."""

        try:
            from PySide6 import QtNetwork
        except Exception:  # pragma: no cover - Qt without QtNetwork
            return
        self._server = QtNetwork.QLocalServer()
        self._server.setSocketOptions(
            QtNetwork.QLocalServer.SocketOption.UserAccessOption
        )
        if not self._server.listen(self.SOCKET_NAME):
            # A pipe left behind by a coach that crashed: remove it and
            # try once more.
            try:
                QtNetwork.QLocalServer.removeServer(self.SOCKET_NAME)
            except Exception:  # noqa: BLE001
                pass
            self._server = QtNetwork.QLocalServer()
            self._server.setSocketOptions(
                QtNetwork.QLocalServer.SocketOption.UserAccessOption
            )
            if not self._server.listen(self.SOCKET_NAME):
                self._server = None
                return
        self._server.newConnection.connect(self._on_connection)

    def _talk_to_running(self) -> bool:
        """Ask the running coach to show itself.  True when it answered."""

        try:
            from PySide6 import QtNetwork
        except Exception:  # pragma: no cover
            return False
        socket = QtNetwork.QLocalSocket()
        socket.connectToServer(self.SOCKET_NAME)
        if not socket.waitForConnected(2000):
            return False
        try:
            socket.write(b"show")
            socket.flush()
            socket.waitForBytesWritten(1000)
            # Wait for the answer, so the message really arrived before
            # this copy leaves.  Without the answer the pipe can close
            # too early and the running coach never hears the news.
            socket.waitForReadyRead(2000)
            answer = bytes(socket.readAll().data())
        except Exception:  # noqa: BLE001
            answer = b""
        socket.disconnectFromServer()
        return b"ok" in answer

    def _on_connection(self) -> None:
        """The running coach was asked to come forward."""

        try:
            from PySide6 import QtNetwork
        except Exception:  # pragma: no cover
            return
        server = self._server
        if server is None:
            return
        socket = server.nextPendingConnection()
        if socket is None:
            return
        try:
            socket.readyRead.connect(lambda: self._read(socket))
            if socket.bytesAvailable() > 0:
                self._read(socket)
        except Exception:  # noqa: BLE001
            pass

    def _read(self, socket: Any) -> None:
        try:
            data = bytes(socket.readAll().data())
        except Exception:  # noqa: BLE001
            return
        if b"show" not in data:
            return
        callback = self.on_show
        if callback is not None:
            try:
                callback()
            except Exception:  # noqa: BLE001
                pass
        # Say that the news arrived, so the other copy can leave.
        try:
            socket.write(b"ok")
            socket.flush()
            socket.waitForBytesWritten(1000)
        except Exception:  # noqa: BLE001
            pass

    def release(self) -> None:
        """Give the name back, so the next start is the first one again."""

        server = self._server
        self._server = None
        if server is not None:
            try:
                server.close()
            except Exception:  # noqa: BLE001
                pass
            try:
                from PySide6 import QtNetwork

                QtNetwork.QLocalServer.removeServer(self.SOCKET_NAME)
            except Exception:  # noqa: BLE001
                pass
        mutex = self._mutex
        self._mutex = None
        if mutex is not None:
            try:
                import ctypes

                ctypes.windll.kernel32.CloseHandle(mutex)
            except Exception:  # noqa: BLE001
                pass


class Toast:
    """A small, self-closing message in the corner of the screen.

    It exists because a program that starts silently looks broken, and a
    beginner needs to see that the double-click did something.  It can
    carry a row of buttons, so the student does not have to hunt for the
    tray icon or remember a hotkey.
    """

    def __init__(self, master: Any = None, seconds: float = 12.0) -> None:
        from PySide6 import QtCore, QtGui, QtWidgets

        self.seconds = seconds
        # Called when the student closes the greeting window.
        self.on_close = None  # callback() -> None
        self.win = QtWidgets.QWidget()
        self._watch_close()
        self.win.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
            | QtCore.Qt.WindowType.Tool
        )
        self.win.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.win.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating)

        frame = QtWidgets.QFrame(self.win)
        frame.setStyleSheet(
            "QFrame{background:#FFFDF8; border:1px solid #E8590C;"
            "border-radius:10px;}"
        )
        layout = QtWidgets.QVBoxLayout(self.win)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(frame)

        inner = QtWidgets.QVBoxLayout(frame)
        inner.setContentsMargins(16, 12, 16, 12)
        inner.setSpacing(4)

        self.title = QtWidgets.QLabel("")
        self.title.setStyleSheet("color:#E8590C; font-size:13px; font-weight:600;")
        inner.addWidget(self.title)

        self.body = QtWidgets.QLabel("")
        self.body.setWordWrap(True)
        self.body.setStyleSheet("color:#1F2933; font-size:11px;")
        inner.addWidget(self.body)

        self.buttons = QtWidgets.QHBoxLayout()
        self.buttons.setSpacing(6)
        self.buttons.setContentsMargins(0, 4, 0, 0)
        inner.addLayout(self.buttons)

        self._timer = QtCore.QTimer(self.win)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self._fade = QtCore.QPropertyAnimation(self.win, b"windowOpacity", self.win)
        self._fade.setDuration(350)
        self._fade.finished.connect(self.win.hide)

    def _watch_close(self) -> None:
        """Closing the greeting window is closing the coach."""

        try:
            from praatao.ui.qt.close_watch import watch_close

            watch_close(self.win, self)
        except Exception:  # noqa: BLE001
            pass

    def _add_button(self, label: str, callback: Any) -> None:
        from PySide6 import QtCore, QtWidgets

        button = QtWidgets.QPushButton(label)
        button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet(
            "QPushButton{background:#E8590C; color:#ffffff; border:none;"
            "border-radius:6px; padding:5px 12px; font-size:11px;}"
            "QPushButton:hover{background:#C9630F;}"
        )
        button.clicked.connect(callback)
        self.buttons.addWidget(button)

    def show_message(self, title: str, body: str = "",
                     actions: list[tuple[str, Any]] | None = None) -> None:
        self.title.setText(title)
        self.body.setText(body)
        self.body.setVisible(bool(body))

        # Rebuild the button row.
        while self.buttons.count():
            item = self.buttons.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for label, callback in actions or []:
            self._add_button(label, callback)
        # A layout has no visibility of its own; hide the buttons it holds.
        for index in range(self.buttons.count()):
            widget = self.buttons.itemAt(index).widget()
            if widget is not None:
                widget.setVisible(bool(actions))

        screen = None
        try:
            from PySide6 import QtGui

            screen = QtGui.QGuiApplication.primaryScreen()
        except Exception:  # noqa: BLE001
            screen = None
        if screen is not None:
            area = screen.availableGeometry()
            self.win.adjustSize()
            size = self.win.size()
            self.win.move(
                area.right() - size.width() - 24,
                area.bottom() - size.height() - 24,
            )
        self.win.setWindowOpacity(1.0)
        self.win.show()
        self._timer.start(int(self.seconds * 1000))

    def hide(self) -> None:
        try:
            self._fade.stop()
            self._fade.setStartValue(1.0)
            self._fade.setEndValue(0.0)
            self._fade.start()
        except Exception:  # noqa: BLE001
            try:
                self.win.hide()
            except Exception:  # noqa: BLE001
                pass

    def destroy(self) -> None:
        try:
            self.win.close()
            self.win.deleteLater()
        except Exception:  # noqa: BLE001
            pass


# --------------------------------------------------------------------------
# The tray icon: where the controls live
# --------------------------------------------------------------------------
class Tray:
    """A system-tray icon with the few commands a beginner needs."""

    def __init__(self, master: Any = None, on_command: Any = None,
                 lang: str = "zh") -> None:
        from PySide6 import QtCore, QtGui, QtWidgets

        self.on_command = on_command
        self.lang = lang

        self.icon = QtWidgets.QSystemTrayIcon()
        self.icon.setIcon(_tray_pixmap())
        self.icon.setToolTip("Praatao")

        menu = QtWidgets.QMenu()
        self.panel_action = menu.addAction(
            "打开侧栏 (Ctrl+Alt+P)" if lang == "zh" else "Open the panel (Ctrl+Alt+P)"
        )
        self.panel_action.triggered.connect(lambda: self._command("panel"))
        self.settings_action = menu.addAction(
            "设置 (Ctrl+Alt+S)" if lang == "zh" else "Settings (Ctrl+Alt+S)"
        )
        self.settings_action.triggered.connect(lambda: self._command("settings"))
        self.ask_action = menu.addAction(
            "提问 (Ctrl+Alt+Q)" if lang == "zh" else "Ask (Ctrl+Alt+Q)"
        )
        self.ask_action.triggered.connect(lambda: self._command("ask"))
        self.feedback_action = menu.addAction(
            "报告问题" if lang == "zh" else "Report a problem"
        )
        self.feedback_action.triggered.connect(lambda: self._command("feedback"))
        menu.addSeparator()
        self.quit_action = menu.addAction(
            "退出 (Ctrl+Alt+X)" if lang == "zh" else "Quit (Ctrl+Alt+X)"
        )
        self.quit_action.triggered.connect(lambda: self._command("quit"))
        self.icon.setContextMenu(menu)
        self.icon.activated.connect(self._on_activated)

    def _on_activated(self, reason: Any) -> None:
        from PySide6 import QtCore

        if reason == QtCore.QSystemTrayIcon.ActivationReason.Trigger:
            self._command("panel")

    def _command(self, name: str) -> None:
        if self.on_command is not None:
            try:
                self.on_command(name)
            except Exception:  # noqa: BLE001
                pass

    def show(self) -> None:
        try:
            self.icon.show()
        except Exception:  # noqa: BLE001
            pass

    def set_lang(self, lang: str) -> None:
        self.lang = lang

    def destroy(self) -> None:
        try:
            self.icon.hide()
        except Exception:  # noqa: BLE001
            pass


def _tray_pixmap() -> Any:
    """A small orange bubble with a letter, so the tray reads as ours."""

    from PySide6 import QtCore, QtGui

    pixmap = QtGui.QPixmap(64, 64)
    pixmap.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    painter.setBrush(QtGui.QColor("#E8590C"))
    painter.setPen(QtGui.QPen(QtGui.QColor("#FFFFFF"), 3))
    painter.drawEllipse(4, 4, 56, 56)
    font = painter.font()
    font.setBold(True)
    font.setPixelSize(34)
    painter.setFont(font)
    painter.setPen(QtGui.QColor("#FFFFFF"))
    painter.drawText(pixmap.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, "P")
    painter.end()
    return pixmap


def no_console() -> None:
    """Detach from the console window (Windows).

    Called by the packaged executable, and by the launcher when it is
    started through ``pythonw.exe``.
    """

    if sys.platform != "win32":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.FreeConsole()
    except Exception:  # noqa: BLE001
        pass
    try:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def log_path() -> Path:
    """Where the coach writes what it is doing when nobody can see it."""

    base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / ".local" / "share"))
    return base / "praatao" / "coach.log"


def log_line(text: str) -> None:
    """Append one line to the log file (never raises)."""

    try:
        target = log_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as handle:
            handle.write(text.rstrip() + "\n")
    except Exception:  # noqa: BLE001
        pass
