"""Check whether `Praat.exe --send` is still responsive."""

from __future__ import annotations

import subprocess
import tempfile
import time
from pathlib import Path

P = Path(r"D:\Documents\Playground\praatao\Praat.exe")
T = Path(tempfile.gettempdir())

for i in range(3):
    out = T / f"_ping{i}.txt"
    if out.exists():
        out.unlink()
    sc = T / f"_ping{i}.praat"
    sc.write_text(
        'writeFileLine: "{}", "pong"\n'.format(out.as_posix()), encoding="utf-8"
    )
    t0 = time.time()
    try:
        subprocess.run([str(P), "--send", str(sc)], check=False, timeout=15,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(i, "send ok in %.2fs" % (time.time() - t0), "file:", out.exists())
    except subprocess.TimeoutExpired:
        print(i, "TIMEOUT after %.2fs" % (time.time() - t0))
    time.sleep(1)
