"""Dump every control name the live Praat exposes.

The knowledge base has to cover the controls that really exist, so they
are read from the running Praat instead of being guessed.  The result is
written to ``prototypes/v0/probes/praat_controls.txt``.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from praatao.sensors.uia import PraatUI  # noqa: E402


def main() -> int:
    ui = PraatUI()
    windows = ui.windows() + ui.editor_windows()
    lines: list[str] = []
    seen: set[str] = set()

    for window in windows:
        lines.append(f"=== {window.title} ({window.class_name}) ===")
        control = ui._control_from_window(window)
        if control is None:
            lines.append("  (no control)")
            continue
        for node, depth in ui._iter_controls(control, max_depth=8):
            name = (node.Name or "").strip()
            kind = node.ControlTypeName or ""
            if not name or name in seen:
                continue
            seen.add(name)
            lines.append(f"{kind:22s} {name}")

    # The menu bar and its items: open each menu and read the items.
    objects = ui.objects_window()
    if objects is not None:
        for menu in ("Praat", "New", "Open", "Save", "Help"):
            try:
                items = ui.open_menu(objects, menu)
            except Exception:
                continue
            if not items:
                continue
            lines.append(f"=== menu: {menu} ===")
            for item in items:
                name = (item.name or "").strip()
                if name and name not in seen:
                    seen.add(name)
                    lines.append(f"{'MenuItem':22s} {name}")

    out = ROOT / "prototypes" / "v0" / "probes" / "praat_controls.txt"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(seen)} names -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
