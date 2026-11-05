"""Test how to select an object unambiguously in Praat scripting.

Two Sounds share the name 'demo_vowel', so `selectObject: "Sound demo_vowel"`
is ambiguous.  Find the form that works.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

P = Path(r"D:\Documents\Playground\praatao\Praat.exe")
T = Path(tempfile.gettempdir())

CANDIDATES = [
    ("selectObjectNumber", "selectObject: 1"),
    ("selectObjectAt", "selectObject: 1, 1"),
    ("plusObjectNumber", "plusObject: 1"),
]


def run(tag: str, body: str) -> str:
    out = T / f"_sel_{tag}.txt"
    if out.exists():
        out.unlink()
    script = T / f"_sel_{tag}.praat"
    script.write_text(
        body + '\nwriteFileLine: "{}", "ok"\n'.format(out.as_posix()),
        encoding="utf-8",
    )
    try:
        subprocess.run([str(P), "--send", str(script)], check=False, timeout=10,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    time.sleep(0.6)
    if out.exists():
        return out.read_text(encoding="utf-8", errors="replace").strip()
    return "ERROR"


def main() -> int:
    from praatao.sensors.praat_state import PraatStateProbe

    probe = PraatStateProbe()
    for tag, body in CANDIDATES:
        print(f"{tag:22s} -> {run(tag, body)!r}")
        probe.dismiss_dialogs()
        time.sleep(0.4)
    probe.dismiss_dialogs()

    from praatao.sensors.praat_state import PraatStateProbe as P2
    st = P2().snapshot()
    print("selected now:", st.selected)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
