"""Merge the knowledge-base fragments into the main dictionary.

``praatao/content/elements.yaml`` holds the dictionary; the folder
``praatao/content/elements/`` holds fragments that were written
separately (one topic per file).  Two entries must never share an alias,
so this tool merges a fragment into the main file:

* an entry whose alias is not in the main file is appended,
* an entry whose alias **is** in the main file replaces it, and the
  pitfalls of the old entry are kept (nothing is lost).

The result is written back to ``praatao/content/elements.yaml`` and the
fragment is left in place, so the merge can be repeated.

    python tools\\merge_elements.py            # merge everything
    python tools\\merge_elements.py --dry-run  # only report
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

MAIN = ROOT / "praatao" / "content" / "elements.yaml"
FRAGMENTS = ROOT / "praatao" / "content" / "elements"


def _alias_key(alias: str) -> str:
    return " ".join(str(alias).split()).casefold()


def _text_key(text: str) -> str:
    """A comparison key for a pitfall: the words, without punctuation."""

    keep = [
        ch for ch in str(text)
        if ch.isalnum() or ch.isspace() or "\u4e00" <= ch <= "\u9fff"
    ]
    return "".join(keep).casefold()


def dedupe_pitfalls(entries: list[dict]) -> int:
    """Remove the pitfalls that say the same thing twice.

    Two entries about the same control are written by different hands, so
    the merged entry can end up with two pitfalls that say the same thing
    in slightly different words.  The Chinese text decides.
    """

    removed = 0
    for entry in entries:
        pitfalls = entry.get("pitfalls") or []
        seen: set[str] = set()
        unique = []
        for pitfall in pitfalls:
            if isinstance(pitfall, dict):
                key = _text_key(pitfall.get("zh") or pitfall.get("en") or "")
            else:
                key = _text_key(pitfall)
            if key and key in seen:
                removed += 1
                continue
            if key:
                seen.add(key)
            unique.append(pitfall)
        if unique:
            entry["pitfalls"] = unique
    return removed


def load(path: Path) -> list[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = data.get("entries") or []
    return [entry for entry in entries if isinstance(entry, dict)]


def dump(path: Path, entries: list[dict]) -> None:
    header = (
        "# Praatao — UI element dictionary (v1)\n"
        "#\n"
        "# Merged from praatao/content/elements/*.yaml by\n"
        "# tools/merge_elements.py.  See docs/13-content-guide.md.\n"
    )
    body = yaml.safe_dump(
        {"version": 1, "entries": entries},
        allow_unicode=True,
        sort_keys=False,
        width=100,
    )
    path.write_text(header + "\n" + body, encoding="utf-8")


def merge(main_entries: list[dict], fragment: list[dict]) -> tuple[list[dict], int, int]:
    """Return (entries, added, replaced)."""

    by_alias: dict[str, dict] = {}
    by_id: dict[str, dict] = {}
    for entry in main_entries:
        for alias in entry.get("aliases") or []:
            by_alias.setdefault(_alias_key(alias), entry)
        eid = entry.get("id")
        if eid:
            by_id.setdefault(str(eid), entry)

    added = 0
    replaced = 0
    for entry in fragment:
        aliases = entry.get("aliases") or []
        clash = None
        # An id that is already there is the same entry, even when the
        # label changed and the aliases do not match.
        eid = entry.get("id")
        if eid and str(eid) in by_id:
            clash = by_id[str(eid)]
        if clash is None:
            for alias in aliases:
                existing = by_alias.get(_alias_key(alias))
                if existing is not None:
                    clash = existing
                    break
        if clash is None:
            main_entries.append(entry)
            added += 1
            for alias in aliases:
                by_alias[_alias_key(alias)] = entry
            if eid:
                by_id[str(eid)] = entry
            continue

        # Same label, different entry: keep the fragment's text and carry
        # over the pitfalls of the entry that is replaced.
        index = next(
            (i for i, existing in enumerate(main_entries) if existing is clash),
            None,
        )
        if index is None:  # pragma: no cover - defensive
            main_entries.append(entry)
            added += 1
            for alias in aliases:
                by_alias[_alias_key(alias)] = entry
            continue
        merged = dict(entry)
        pitfalls = list(entry.get("pitfalls") or [])
        for pitfall in clash.get("pitfalls") or []:
            text = pitfall.get("en", "") if isinstance(pitfall, dict) else str(pitfall)
            zh = pitfall.get("zh", "") if isinstance(pitfall, dict) else ""
            if not text:
                continue
            if any(
                _text_key((p.get("zh") if isinstance(p, dict) else str(p)) or "")
                == _text_key(zh)
                for p in pitfalls
            ):
                continue
            if any(
                (p.get("en", "") if isinstance(p, dict) else str(p)) == text
                for p in pitfalls
            ):
                continue
            pitfalls.append(pitfall)
        if pitfalls:
            merged["pitfalls"] = pitfalls
        # Keep the old id when the fragment does not bring its own.
        merged.setdefault("id", clash.get("id"))
        main_entries[index] = merged
        replaced += 1
        for alias in aliases:
            by_alias[_alias_key(alias)] = merged
        if eid:
            by_id[str(eid)] = merged
    return main_entries, added, replaced


def dedupe_by_id(entries: list[dict]) -> tuple[list[dict], list[str]]:
    """Drop the entries whose id is already in the list."""

    seen: set[str] = set()
    unique: list[dict] = []
    dropped: list[str] = []
    for entry in entries:
        eid = str(entry.get("id") or "")
        if eid and eid in seen:
            dropped.append(eid)
            continue
        if eid:
            seen.add(eid)
        unique.append(entry)
    return unique, dropped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="only report what would change")
    args = parser.parse_args(argv)

    entries = load(MAIN)
    before = len(entries)
    for fragment in sorted(FRAGMENTS.glob("*.yaml")):
        fragment_entries = load(fragment)
        if not fragment_entries:
            continue
        entries, added, replaced = merge(entries, fragment_entries)
        print(f"{fragment.name}: +{added} new, {replaced} merged into existing")
    entries, dropped = dedupe_by_id(entries)
    if dropped:
        print(f"dropped {len(dropped)} duplicated ids: {', '.join(dropped)}")
    removed = dedupe_pitfalls(entries)
    if removed:
        print(f"removed {removed} repeated pitfalls")
    print(f"entries: {before} -> {len(entries)}")
    if not args.dry_run:
        dump(MAIN, entries)
        print(f"written to {MAIN}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
