"""Check the element dictionary against the rules in docs/13-content-guide.md.

    python tools\\check_elements.py

The rules that matter: one id per entry, one alias per control (no alias
used twice), bilingual text everywhere, no string that is too long, and
no byte-order mark (Windows editors add one and the loader does not
expect it).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

CONTENT = ROOT / "praatao" / "content"
MAX_CHARS = 300


def main() -> int:
    problems: list[str] = []
    entries: list[dict] = []
    sources: list[str] = []

    main_file = CONTENT / "elements.yaml"
    files = [main_file] + sorted((CONTENT / "elements").glob("*.yaml"))
    for path in files:
        if not path.exists():
            continue
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            problems.append(f"{path.name}: has a byte-order mark")
        data = yaml.safe_load(raw.decode("utf-8")) or {}
        found = data.get("entries") or []
        entries.extend(found)
        sources.append(f"{path.name}: {len(found)}")

    print("; ".join(sources))
    print(f"{len(entries)} entries in total")

    ids: dict[str, int] = {}
    aliases: dict[str, str] = {}
    for entry in entries:
        eid = entry.get("id")
        if not eid:
            problems.append("an entry has no id")
            continue
        ids[eid] = ids.get(eid, 0) + 1
        for field in ("title", "what", "how"):
            value = entry.get(field) or {}
            if not (value.get("en") and value.get("zh")):
                problems.append(f"{eid}: {field} is not bilingual")
        concept = entry.get("concept")
        if concept and not (concept.get("en") and concept.get("zh")):
            problems.append(f"{eid}: concept is not bilingual")
        for pitfall in entry.get("pitfalls") or []:
            if not (pitfall.get("en") and pitfall.get("zh")):
                problems.append(f"{eid}: a pitfall is not bilingual")
        for value in entry.values():
            if isinstance(value, dict):
                for text in value.values():
                    if isinstance(text, str) and len(text) > MAX_CHARS:
                        problems.append(f"{eid}: a text is {len(text)} characters long")
            elif isinstance(value, str) and len(value) > MAX_CHARS:
                problems.append(f"{eid}: a text is {len(value)} characters long")

    # The main file may hold a copy of a fragment entry (the merge writes
    # it there), so the uniqueness rules are checked on the dictionary the
    # loader really builds.
    from praatao.tutor.kb import load_default

    effective = load_default()
    for entry in effective.entries():
        eid = entry.id
        for alias in entry.aliases:
            key = " ".join(str(alias).split()).casefold()
            if key in aliases:
                problems.append(
                    f"{eid}: alias {alias!r} is already used by {aliases[key]}"
                )
            else:
                aliases[key] = eid
    print(f"effective dictionary: {len(effective.entries())} entries, "
          f"{len(aliases)} aliases")

    for eid, count in ids.items():
        if count > 1 and count != 2:
            problems.append(f"id {eid} is used {count} times")

    if problems:
        print(f"\n{len(problems)} problems:")
        for problem in problems[:40]:
            print("  -", problem)
        if len(problems) > 40:
            print(f"  ... and {len(problems) - 40} more")
        return 1
    print("\nthe dictionary is fine")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
