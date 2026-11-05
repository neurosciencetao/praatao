"""Does the second process see the pipe?"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

CHILD = """
import sys, time
sys.path.insert(0, r"D:\\Documents\\Playground\\praatao")
from PySide6 import QtNetwork, QtWidgets
app = QtWidgets.QApplication([])
server = QtNetwork.QLocalServer()
server.setSocketOptions(QtNetwork.QLocalServer.SocketOption.UserAccessOption)
ok = server.listen("praatao-coach-single-instance")
print("listen:", ok, server.errorString(), flush=True)
if ok:
    socket = QtNetwork.QLocalSocket()
    socket.connectToServer("praatao-coach-single-instance")
    print("connected:", socket.waitForConnected(1000), socket.errorString(), flush=True)
    socket.write(b"show")
    socket.flush()
    socket.waitForBytesWritten(1000)
    time.sleep(1)
"""


def main() -> int:
    first = subprocess.Popen(
        [sys.executable, str(ROOT / "prototypes" / "v1" / "experiments" / "single_instance_check.py")],
        cwd=str(ROOT),
    )
    time.sleep(3.0)
    second = subprocess.run([sys.executable, "-c", CHILD], capture_output=True, text=True)
    print("second process:", second.stdout.strip())
    print("second stderr:", second.stderr.strip()[-300:])
    first.kill()
    return 0


if __name__ == "__main__":
    sys.exit(main())
