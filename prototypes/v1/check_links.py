"""Check that every relative markdown link in the repo resolves."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
SKIP = ("http://", "https://", "mailto:", "#")


def main() -> int:
    broken: list[str] = []
    checked = 0
    for md in sorted(ROOT.rglob("*.md")):
        if "__pycache__" in md.parts:
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        for target in LINK.findall(text):
            target = target.strip()
            if not target or target.lower().startswith(SKIP):
                continue
            # Strip an anchor and any title after the path.
            path = target.split("#", 1)[0].split('"')[0].strip()
            if not path:
                continue
            checked += 1
            resolved = (md.parent / path).resolve()
            if not resolved.exists():
                broken.append(f"{md.relative_to(ROOT)} -> {target}")

    print(f"checked {checked} relative links in "
          f"{len(list(ROOT.rglob('*.md')))} markdown files")
    if broken:
        print(f"BROKEN ({len(broken)}):")
        for item in broken:
            print("  ", item)
        return 1
    print("all relative links resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main())
