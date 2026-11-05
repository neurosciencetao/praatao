"""Check the lesson packs against the rules in docs/13-content-guide.md.

    python tools\\check_lessons.py

Every step needs an id, a detect block with its three keys, a valid
highlight, and bilingual tip and detail text.  The catalogue in
``index.yaml`` must list every pack that exists.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

LESSONS = ROOT / "praatao" / "content" / "lessons"
VALID_KINDS = {"button", "menu", "list", "canvas", "window"}
VALID_DETECT = {"object_types_present", "selected_types", "editor_open"}


def main() -> int:
    problems: list[str] = []
    packs = sorted(p for p in LESSONS.glob("*.yaml") if p.name != "index.yaml")
    print(f"{len(packs)} lesson packs")

    for pack in packs:
        raw = pack.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            problems.append(f"{pack.name}: has a byte-order mark")
        data = yaml.safe_load(raw.decode("utf-8")) or {}
        if data.get("id") != pack.stem:
            problems.append(f"{pack.name}: id is {data.get('id')!r}")
        if data.get("file") not in (None, pack.name):
            problems.append(f"{pack.name}: file field is {data.get('file')!r}")
        for field in ("title", "summary"):
            value = data.get(field) or {}
            if not (value.get("en") and value.get("zh")):
                problems.append(f"{pack.name}: {field} is not bilingual")
        steps = data.get("steps") or []
        if not steps:
            problems.append(f"{pack.name}: no steps")
        for step in steps:
            sid = step.get("id", "?")
            detect = step.get("detect") or {}
            missing = VALID_DETECT - set(detect)
            if missing:
                problems.append(f"{pack.name}/{sid}: detect misses {sorted(missing)}")
            highlight = step.get("highlight") or {}
            kind = highlight.get("kind")
            if kind not in VALID_KINDS:
                problems.append(f"{pack.name}/{sid}: highlight kind {kind!r}")
            if kind == "menu":
                path = highlight.get("path") or []
                if len(path) != 2 or not all(isinstance(p, str) for p in path):
                    problems.append(f"{pack.name}/{sid}: menu path {path!r}")
            elif kind in ("button", "list") and not highlight.get("name"):
                problems.append(f"{pack.name}/{sid}: highlight has no name")
            for field in ("tip", "detail"):
                value = step.get(field) or {}
                if not isinstance(value, dict) or not (value.get("en") and value.get("zh")):
                    problems.append(f"{pack.name}/{sid}: {field} is not bilingual")
            for text in (step.get("detail", {}).get("zh", ""), step.get("tip", {}).get("zh", "")):
                # A dash between two letters or digits is a range
                # (0-5000 Hz, F1-F2), which is fine; a dash used as
                # punctuation is not.
                stripped = re.sub(r"[A-Za-z0-9][\u2013\u2014][A-Za-z0-9]", "", str(text))
                if "\u2014" in stripped or "\u2013" in stripped:
                    problems.append(f"{pack.name}/{sid}: a dash in the Chinese text")
        completion = data.get("completion") or {}
        message = completion.get("message") or {}
        if not (message.get("en") and message.get("zh")):
            problems.append(f"{pack.name}: completion message is not bilingual")
        print(f"  {pack.name}: {len(steps)} steps")

    index = yaml.safe_load((LESSONS / "index.yaml").read_text(encoding="utf-8")) or {}
    listed = {entry.get("file") for entry in index.get("lessons") or []}
    for pack in packs:
        if pack.name not in listed:
            problems.append(f"{pack.name}: not in index.yaml")
    for name in listed:
        if name and not (LESSONS / name).exists():
            problems.append(f"index.yaml lists {name}, which does not exist")

    if problems:
        print("\nproblems:")
        for problem in problems:
            print("  -", problem)
        return 1
    print("\nall lesson packs are fine")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
