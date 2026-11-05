"""Why does the local socket hand-over not arrive?"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from PySide6 import QtNetwork, QtWidgets  # noqa: E402

app = QtWidgets.QApplication([])

NAME = "praatao-debug-socket"

server = QtNetwork.QLocalServer()
server.setSocketOptions(QtNetwork.QLocalServer.SocketOption.UserAccessOption)
print("listen:", server.listen(NAME), server.fullServerName(), flush=True)


def on_connection() -> None:
    socket = server.nextPendingConnection()
    print("   a client connected", flush=True)
    if socket is None:
        return
    socket.readyRead.connect(
        lambda: print("   the client said:", bytes(socket.readAll().data()), flush=True)
    )


server.newConnection.connect(on_connection)

socket = QtNetwork.QLocalSocket()
socket.connectToServer(NAME)
print("connect:", socket.connectToServer(NAME), flush=True)
print("waitForConnected:", socket.waitForConnected(1000), flush=True)
print("state:", socket.state(), socket.errorString(), flush=True)
socket.write(b"show")
socket.flush()
socket.waitForBytesWritten(1000)
time.sleep(0.5)
app.processEvents()
time.sleep(0.5)
app.processEvents()
