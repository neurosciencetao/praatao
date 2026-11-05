"""Check the single-instance hand-over."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from PySide6 import QtWidgets  # noqa: E402

app = QtWidgets.QApplication([])

from praatao.launcher import SingleInstance  # noqa: E402

calls: list[str] = []


def show() -> None:
    calls.append("show")
    print("   the running coach was asked to come forward", flush=True)


instance = SingleInstance(show)
first = instance.acquire()
print("acquire:", first, flush=True)

if first:
    # A second copy in this process talks to the first one.
    second = SingleInstance(show)
    print("second acquire:", second.acquire(), flush=True)

    deadline = time.time() + 3
    while time.time() < deadline:
        app.processEvents()
        time.sleep(0.05)
    print("calls:", calls, flush=True)
    instance.release()
else:
    deadline = time.time() + 5
    while time.time() < deadline:
        app.processEvents()
        time.sleep(0.05)
    print("calls:", calls, flush=True)
