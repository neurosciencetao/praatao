"""
Spike A helper: run a Praat probe via --send and print the state file.

Usage (PowerShell):
  python watch_probe.py
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRAAT = ROOT / "Praat.exe"
PROBE = Path(__file__).with_name("probe_selected.praat")
STATE = Path(__file__).with_name("last_state.json")


def send_probe() -> None:
    if not PRAAT.exists():
        raise SystemExit(f"Praat not found: {PRAAT}")
    subprocess.run([str(PRAAT), "--send", str(PROBE)], check=False)


def read_state() -> dict:
    if not STATE.exists():
        return {}
    text = STATE.read_text(encoding="utf-8", errors="replace").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}


def main() -> None:
    print("Sending probe to Praat…")
    send_probe()
    time.sleep(0.5)
    print(read_state())


if __name__ == "__main__":
    main()
