"""Find out which Praat scripting builtins actually exist.

Each candidate is tested in its own script because a Praat error aborts the
whole script AND leaves a modal error dialog behind, which blocks every
later ``--send``.  So each test dismisses any leftover dialog first.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from pathlib import Path

import uiautomation as auto
import win32gui

ROOT = Path(__file__).resolve().parents[3]
PRAAT = ROOT / "Praat.exe"
TMP = Path(tempfile.gettempdir())

CANDIDATES = [
    ("numberOfSelected", 'string$(numberOfSelected())'),
    ("selectedDollar", 'selected$'),
    ("selectedDollarCall", 'selected$()'),
    ("selectedIndex", 'selected$[1]'),
    ("objectName", 'object[1].name$'),
    ("objectType", 'object[1].typeof$()'),
    ("numberOfSound", 'string$(numberOfSound)'),
    ("selectedNameObj", 'object[selected[1]].name$'),
    ("selectedType", 'object[selected[1]].typeof$()'),
]


def dismiss_dialogs() -> None:
    """Close any Praat modal dialog (error / message).

    Praat draws its dialogs with the Motif emulator, so the class is
    ``PraatChildWindow1 Praat`` / ``PraatShell1 Praat`` and the title is
    ``Message`` or ``Error`` - NOT the standard ``#32770``.
    """
    victims = []

    def cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        cls = win32gui.GetClassName(hwnd)
        title = (win32gui.GetWindowText(hwnd) or "").strip()
        if not cls.lower().startswith("praat"):
            return
        if title.lower() in ("message", "error", "warning", "praat message"):
            victims.append(hwnd)

    win32gui.EnumWindows(cb, None)
    for hwnd in victims:
        try:
            ctrl = auto.ControlFromHandle(hwnd)
            for node, _ in _walk(ctrl, max_depth=5):
                try:
                    if node.ControlTypeName == "ButtonControl" and node.Name.strip().lower() in ("ok", "确定"):
                        node.GetInvokePattern().Invoke()
                        time.sleep(0.3)
                        break
                except Exception:
                    pass
            else:
                auto.SendKeys("{ESC}")
        except Exception:
            pass
    if victims:
        time.sleep(0.4)


def _walk(ctrl, max_depth=4):
    stack = [(ctrl, 0)]
    while stack:
        node, d = stack.pop(0)
        yield node, d
        if d < max_depth:
            try:
                for c in node.GetChildren():
                    stack.append((c, d + 1))
            except Exception:
                pass


def run_one(tag: str, expr: str) -> str:
    dismiss_dialogs()
    out = TMP / f"_praatfn_{tag}.txt"
    if out.exists():
        out.unlink()
    script = TMP / f"_praatfn_{tag}.praat"
    # writeFileLine's second argument is an EXPRESSION, so it must not be
    # wrapped in quotes - otherwise Praat writes the literal text.
    script.write_text(
        'writeFileLine: "%s", %s\n' % (out.as_posix(), expr),
        encoding="utf-8",
    )
    try:
        subprocess.run(
            [str(PRAAT), "--send", str(script)],
            check=False, timeout=10,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        dismiss_dialogs()
        return "TIMEOUT"
    time.sleep(0.6)
    if out.exists():
        value = out.read_text(encoding="utf-8", errors="replace").strip()
        dismiss_dialogs()
        return value
    dismiss_dialogs()
    return "ERROR"


def main() -> int:
    for tag, expr in CANDIDATES:
        result = run_one(tag, expr)
        print(f"{tag:20s} = {result!r}    <- {expr}")
    dismiss_dialogs()
    return 0


if __name__ == "__main__":
    sys.exit(main())
