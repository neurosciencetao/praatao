"""Compare two result files of ``perf_probe.py``.

    python prototypes/v1/experiments/perf_compare.py [before.json] [after.json]

The default pair is the one of ``docs/15-performance.md``:
``perf_baseline.json`` (the old implementations, measured with ``--legacy``)
and ``perf_after.json`` (the current ones).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name: str) -> dict:
    path = Path(name)
    if not path.is_absolute():
        path = HERE / path
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str]) -> int:
    before = load(argv[0] if argv else "perf_baseline.json")
    after = load(argv[1] if len(argv) > 1 else "perf_after.json")

    for label, data in (("BEFORE", before), ("AFTER", after)):
        meta = data.get("meta", {})
        print("=" * 3, label, meta.get("timestamp", ""),
              f"dwell={meta.get('dwell_ms')} ms",
              "legacy" if meta.get("legacy") else "")
        e2e = data.get("end_to_end", {})
        if "end_to_end" in e2e:
            print("   end to end median:", e2e["end_to_end"].get("median"), "ms",
                  " p95:", e2e["end_to_end"].get("p95"))
            for key, value in e2e.get("stages", {}).items():
                print("     ", key.ljust(26), value.get("median"), value.get("unit", ""))
        cpu = data.get("cpu", {})
        for key, value in cpu.items():
            print("   cpu", key, ":", value.get("cpu_percent"), "%")
        sensors = data.get("sensors", {})
        for key in ("uia.element_at_point (button)", "uia.find_all (full tree walk)",
                    "uia.open_popup_items (no menu open)",
                    "kb.lookup (exact hit)", "kb.lookup (miss -> full scan)",
                    "probe.fast() (UIA, no script)",
                    "probe.snapshot() (deep probe, sends a Praat script)",
                    "canvas.capture (screen grab)"):
            if key in sensors:
                print("   ", key.ljust(38), sensors[key].get("median"), "ms")
        rows = data.get("false_triggers", {}).get("sweeps", [])
        if rows:
            print("    false triggers")
            for row in rows:
                print("     ", str(row["dwell_per_control_ms"]).rjust(4), "ms",
                      f"{row['cards_shown']}/{row['controls_visited']}",
                      f"{row['false_trigger_rate'] * 100:.1f} %")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
