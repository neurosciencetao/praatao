"""Build the packaged Praatao.

    python tools\\packaging\\build.py

What it does:

1. runs PyInstaller on ``tools/packaging/Praatao.spec``,
2. copies ``Praat.exe`` next to the executable (the launcher looks for
   it there, so the student gets one folder that just works),
3. writes ``dist/Praatao/启动 Praatao.cmd`` as a plain-language fallback
   for anyone who prefers to start it from the file manager.

The build takes a few minutes the first time; afterwards PyInstaller
reuses its cache.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "tools" / "packaging" / "Praatao.spec"
DIST = ROOT / "dist" / "Praatao"

FALLBACK = """@echo off
rem Start Praatao.  If this window stays open, the coach is running.
rem Close it, or press Ctrl+Alt+X, to stop the coach.
cd /d "%~dp0"
start "" "%~dp0Praatao.exe"
"""


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    if "--skip-build" not in argv:
        print("building ... this takes a few minutes the first time")
        start = time.time()
        result = subprocess.run(
            [sys.executable, "-m", "PyInstaller", "--noconfirm", str(SPEC)],
            cwd=str(ROOT),
        )
        if result.returncode != 0:
            print("the build failed")
            return result.returncode
        print(f"built in {time.time() - start:.0f} s")

    exe = DIST / "Praatao.exe"
    if not exe.exists():
        print(f"the executable is missing: {exe}")
        return 1

    praat = ROOT / "Praat.exe"
    if praat.exists():
        shutil.copy2(praat, DIST / "Praat.exe")
        print("copied Praat.exe next to the executable")

    launcher = DIST / "启动 Praatao.cmd"
    launcher.write_text(FALLBACK, encoding="utf-8")
    print("wrote", launcher)

    total = sum(f.stat().st_size for f in DIST.rglob("*") if f.is_file())
    print(f"ready: {exe}  ({total / 1024 / 1024:.0f} MB in total)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
