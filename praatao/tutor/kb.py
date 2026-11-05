"""Knowledge base: the offline dictionary that explains Praat's controls.

The primary source of truth for "what does this button mean" is this curated
YAML file, not a language model. The LLM layer (see :mod:`praatao.tutor.llm`)
is optional and only used for what the dictionary does not cover.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

try:  # PyYAML is present in this environment, but keep the import soft.
    import yaml
except Exception:  # pragma: no cover - yaml missing
    yaml = None  # type: ignore[assignment]

LANGUAGES = ("en", "zh")


def _clean(text: Any) -> str:
    if text is None:
        return ""
    if isinstance(text, (list, tuple)):
        return " ".join(_clean(t) for t in text).strip()
    return str(text).strip()


def _bilingual(node: Any, lang: str) -> str:
    """Read a ``{en: ..., zh: ...}`` mapping, falling back to the other language."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node.strip()
    if not isinstance(node, dict):
        return _clean(node)
    primary = _clean(node.get(lang))
    if primary:
        return primary
    for other in LANGUAGES:
        if other != lang:
            value = _clean(node.get(other))
            if value:
                return value
    return ""


def normalize_key(text: str) -> str:
    """Normalise a UI label so that lookup is forgiving.

    Rules (mirrored by ``praatao.sensors.uia.normalize_name``):

    * a tab-separated accelerator suffix is dropped, so
      ``'Read from file...\\tCtrl-O'`` becomes ``'Read from file...'``
    * NBSP / narrow NBSP become plain spaces
    * whitespace runs collapse to one space
    * a leading list index such as ``1. `` is dropped
    * a trailing cascade marker ``>`` is dropped
    * trailing colons are dropped
    * case is folded
    """
    if not text:
        return ""
    s = str(text).split("\t", 1)[0]
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("\u00a0", " ").replace("\u202f", " ")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^\d+\.\s*", "", s)
    s = re.sub(r"^(?:[-*]\s*)+", "", s)
    s = s.rstrip(" >:").strip()
    return s.casefold()


@dataclass
class KnowledgeEntry:
    """One explainable UI element."""

    id: str
    aliases: list[str] = field(default_factory=list)
    control_types: list[str] = field(default_factory=list)
    title_en: str = ""
    title_zh: str = ""
    what_en: str = ""
    what_zh: str = ""
    how_en: str = ""
    how_zh: str = ""
    concept_en: str = ""
    concept_zh: str = ""
    pitfalls: list[dict[str, str]] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)

    # -- cached normalisations ---------------------------------------
    # The hover asks the knowledge base for an entry every time the
    # pointer rests on a control, so the normalisations are done once
    # and kept.  They are hidden from the constructor's usual use and
    # from equality, so the entry still behaves like a plain record.
    _norm_keywords: list[str] | None = field(
        default=None, repr=False, compare=False
    )
    _norm_aliases: list[str] | None = field(
        default=None, repr=False, compare=False
    )
    _norm_haystack: str | None = field(default=None, repr=False, compare=False)

    # -- accessors -------------------------------------------------
    def title(self, lang: str = "zh") -> str:
        return self.title_zh if lang == "zh" else self.title_en

    def what(self, lang: str = "zh") -> str:
        return self.what_zh if lang == "zh" else self.what_en

    def how(self, lang: str = "zh") -> str:
        return self.how_zh if lang == "zh" else self.how_en

    def concept(self, lang: str = "zh") -> str:
        return self.concept_zh if lang == "zh" else self.concept_en

    def pitfall_texts(self, lang: str = "zh") -> list[str]:
        out: list[str] = []
        for p in self.pitfalls:
            text = _bilingual(p, lang)
            if text:
                out.append(text)
        return out

    def all_aliases(self) -> list[str]:
        return [self.id, *self.aliases]

    def normalized_keywords(self) -> list[str]:
        """The keywords, normalised once (only usable ones are kept)."""

        if self._norm_keywords is None:
            seen: list[str] = []
            for raw in self.keywords:
                key = normalize_key(raw)
                if len(key) >= 2 and key not in seen:
                    seen.append(key)
            self._norm_keywords = seen
        return self._norm_keywords

    def normalized_aliases(self) -> list[str]:
        """The aliases (including the id), normalised once."""

        if self._norm_aliases is None:
            seen: list[str] = []
            for raw in self.all_aliases():
                key = normalize_key(raw)
                if key and key not in seen:
                    seen.append(key)
            self._norm_aliases = seen
        return self._norm_aliases

    def normalized_haystack(self) -> str:
        """Everything about this entry, as one normalised search string.

        Building it costs a normalisation of the whole entry, which is
        far too much to repeat on every lookup, so it is kept.
        """

        if self._norm_haystack is None:
            self._norm_haystack = normalize_key(self.search_text())
        return self._norm_haystack

    def search_text(self, lang: str = "zh") -> str:
        parts = [
            self.id,
            *self.aliases,
            self.title_en,
            self.title_zh,
            self.what_en,
            self.what_zh,
            self.how_en,
            self.how_zh,
            self.concept_en,
            self.concept_zh,
            *self.keywords,
        ]
        return " ".join(_clean(p) for p in parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "aliases": list(self.aliases),
            "control_types": list(self.control_types),
            "title": {"en": self.title_en, "zh": self.title_zh},
            "what": {"en": self.what_en, "zh": self.what_zh},
            "how": {"en": self.how_en, "zh": self.how_zh},
            "concept": {"en": self.concept_en, "zh": self.concept_zh},
            "pitfalls": list(self.pitfalls),
            "keywords": list(self.keywords),
        }


class KnowledgeBase:
    """Loads ``elements.yaml`` and resolves UI labels to knowledge.

    Everything the hover needs is indexed once, at load time:

    * ``_by_alias`` - normalised alias -> entries (an exact hit);
    * ``_by_keyword`` - normalised keyword -> entries (the fallback);
    * ``_alias_order`` - the aliases, longest first, so the "longest
      alias inside the label" rule can stop at the first match.

    The hover asks for an entry on every dwell, so the lookup has to be
    a dictionary read and not a scan over 288 entries.
    """

    def __init__(self, entries: Iterable[KnowledgeEntry] | None = None) -> None:
        self._entries: list[KnowledgeEntry] = list(entries or [])
        self._by_alias: dict[str, list[KnowledgeEntry]] = {}
        self._alias_ids: dict[str, set[int]] = {}
        self._by_id: dict[str, KnowledgeEntry] = {}
        self._by_keyword: dict[str, list[tuple[int, KnowledgeEntry]]] = {}
        self._alias_order: list[str] = []
        for index, entry in enumerate(self._entries):
            self._index(entry, index)

    # -- construction ----------------------------------------------
    def _index(self, entry: KnowledgeEntry, index: int = 0) -> None:
        self._by_id[entry.id.casefold()] = entry
        for alias in entry.all_aliases():
            key = normalize_key(alias)
            if not key:
                continue
            bucket = self._by_alias.setdefault(key, [])
            known = self._alias_ids.setdefault(key, set())
            if id(entry) not in known:
                known.add(id(entry))
                bucket.append(entry)
        for keyword in entry.normalized_keywords():
            self._by_keyword.setdefault(keyword, []).append((index, entry))
        # The search text and the aliases are normalised now, not on the
        # first search: a search happens while the pointer waits for the
        # card, and it must not be the moment that pays for 288 entries.
        entry.normalized_aliases()
        entry.normalized_haystack()
        # The aliases, longest first.  Ties keep their original order, so
        # the "first alias of the longest match wins" rule is unchanged.
        order = {key: pos for pos, key in enumerate(self._by_alias)}
        self._alias_order = sorted(
            self._by_alias, key=lambda key: (-len(key), order[key])
        )

    @classmethod
    def load(cls, path: str | Path) -> "KnowledgeBase":
        """Load a knowledge base from a file **or a directory**.

        A directory is read as a set of fragments: every ``*.yaml`` inside
        it is loaded and the entries are concatenated (in file-name
        order).  That keeps a large dictionary maintainable and lets
        several people work on it at the same time without touching the
        same file.
        """

        path = Path(path)
        if yaml is None:
            raise RuntimeError("PyYAML is required to load the knowledge base")
        if not path.exists():
            return cls([])
        if path.is_dir():
            raw_entries: list[dict[str, Any]] = []
            for fragment in sorted(path.glob("*.yaml")):
                raw_entries.extend(cls._raw_entries(fragment))
            # Two entries may not share an alias.  The main file comes
            # first, so a fragment that was already merged in is simply
            # skipped here.
            raw_entries = cls._unique_by_alias(raw_entries)
            return cls([cls._entry_from_raw(raw) for raw in raw_entries])
        raw_entries = cls._raw_entries(path)
        raw_entries = cls._unique_by_alias(raw_entries)
        return cls([cls._entry_from_raw(raw) for raw in raw_entries])

    @staticmethod
    def _unique_by_alias(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Drop the entries whose alias is already taken by an earlier one."""

        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for entry in entries:
            aliases = [str(a).strip().casefold() for a in (entry.get("aliases") or [])]
            aliases = [a for a in aliases if a]
            if not aliases:
                unique.append(entry)
                continue
            if any(alias in seen for alias in aliases):
                continue
            seen.update(aliases)
            unique.append(entry)
        return unique

    @staticmethod
    def _raw_entries(path: Path) -> list[dict[str, Any]]:
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001
            return []
        if isinstance(data, list):
            return [raw for raw in data if isinstance(raw, dict)]
        return [raw for raw in (data.get("entries") or []) if isinstance(raw, dict)]

    @staticmethod
    def _entry_from_raw(raw: dict[str, Any]) -> KnowledgeEntry:
        pitfalls_raw = raw.get("pitfalls") or []
        pitfalls = [p if isinstance(p, dict) else {"en": _clean(p), "zh": _clean(p)}
                    for p in pitfalls_raw]
        return KnowledgeEntry(
            id=_clean(raw.get("id")),
            aliases=[_clean(a) for a in (raw.get("aliases") or []) if _clean(a)],
            control_types=[_clean(c) for c in (raw.get("control_types") or []) if _clean(c)],
            title_en=_bilingual(raw.get("title"), "en"),
            title_zh=_bilingual(raw.get("title"), "zh"),
            what_en=_bilingual(raw.get("what"), "en"),
            what_zh=_bilingual(raw.get("what"), "zh"),
            how_en=_bilingual(raw.get("how"), "en"),
            how_zh=_bilingual(raw.get("how"), "zh"),
            concept_en=_bilingual(raw.get("concept"), "en"),
            concept_zh=_bilingual(raw.get("concept"), "zh"),
            pitfalls=pitfalls,
            keywords=[_clean(k) for k in (raw.get("keywords") or []) if _clean(k)],
        )

    # -- queries ----------------------------------------------------
    def entries(self) -> list[KnowledgeEntry]:
        return list(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def by_id(self, entry_id: str) -> KnowledgeEntry | None:
        return self._by_id.get(entry_id.casefold())

    def lookup(self, element_name: str,
               control_type: str | None = None) -> KnowledgeEntry | None:
        """Resolve a UIA label to a knowledge entry.

        Order: exact alias -> longest alias contained in the label -> keyword hit.

        ``control_type`` is a **soft** preference, never a hard filter: a
        label like ``Play`` appears both as an Objects-window button and as an
        editor menu item, and one entry may cover both.  When several entries
        match equally well, the one that declares this control type wins.

        The three rules are the same as they always were, but they run on
        dictionaries now: the alias rule stops at the first (longest) match,
        and the keyword rule looks the label's substrings up in the keyword
        index instead of normalising every keyword of every entry again.
        """
        key = normalize_key(element_name)
        if not key:
            return None

        exact = self._by_alias.get(key)
        if exact:
            return self._choose(exact, control_type)

        # Longest alias that is a substring of the label (e.g. the label is
        # "Read from file..." but the entry aliases "Read from file").
        for alias_key in self._alias_order:
            if len(alias_key) < 3:
                continue
            if alias_key in key:
                return self._choose(list(self._by_alias[alias_key]), control_type)

        # Keyword fallback: the longest keyword that appears in the label.
        found = self._keyword_matches(key)
        if found:
            return self._choose(found, control_type)
        return None

    def _keyword_matches(self, key: str) -> list[KnowledgeEntry]:
        """The entries whose longest matching keyword wins.

        The keywords are indexed, so the label's own substrings are looked
        up instead of every keyword of every entry being normalised again.
        The result keeps the order of the entries, exactly like the old
        scan over ``self._entries`` did.
        """

        length = len(key)
        while length >= 2:
            found: list[KnowledgeEntry] = []
            seen: set[int] = set()
            for start in range(0, len(key) - length + 1):
                bucket = self._by_keyword.get(key[start:start + length])
                if not bucket:
                    continue
                for _index, entry in bucket:
                    if id(entry) in seen:
                        continue
                    seen.add(id(entry))
                    found.append((_index, entry))
            if found:
                found.sort(key=lambda pair: pair[0])
                return [entry for _index, entry in found]
            length -= 1
        return []

    @staticmethod
    def _choose(candidates: list[KnowledgeEntry],
                control_type: str | None) -> KnowledgeEntry:
        """Pick between entries that match equally well.

        ``control_type`` is a **soft** preference, never a hard filter: a
        label like ``Play`` is both an Objects-window button and an editor
        menu item, and one entry may cover both.  When an entry declares this
        control type it wins; otherwise the first candidate does.
        """
        if not candidates:
            raise ValueError("no candidates")
        if control_type:
            for entry in candidates:
                if control_type in entry.control_types:
                    return entry
        return candidates[0]

    def search(self, query: str, limit: int = 5) -> list[KnowledgeEntry]:
        """Rank entries against a free-text query."""
        q = normalize_key(query)
        if not q:
            return []
        tokens = [t for t in re.split(r"[\s,;.!?/]+", q) if len(t) >= 2]
        scored: list[tuple[float, KnowledgeEntry]] = []
        for entry in self._entries:
            # The haystack and the aliases are normalised once, when the
            # entry is built; doing it here cost 20 ms per search.
            haystack = entry.normalized_haystack()
            score = 0.0
            if q in haystack:
                score += 3.0
            for tok in tokens:
                if tok in haystack:
                    score += 1.0 + 0.1 * min(len(tok), 12)
                for a in entry.normalized_aliases():
                    if a and (a == tok or (len(a) > 3 and a in tok) or (len(tok) > 3 and tok in a)):
                        score += 2.5
                        break
            if score > 0:
                scored.append((score, entry))
        scored.sort(key=lambda pair: (-pair[0], pair[1].id))
        return [entry for _, entry in scored[:limit]]

    # -- misc -------------------------------------------------------
    def exact_match(self, name: str) -> KnowledgeEntry | None:
        """The entry whose alias is *exactly* this label.

        No guessing, no keyword search: the label has to be an alias of
        the entry.  The caller uses it to tell a real match from a loose
        one ("Formant ceiling (Hz):" is not an alias, but "Help" is).
        """

        key = normalize_key(name)
        if not key:
            return None
        candidates = self._by_alias.get(key)
        if not candidates:
            return None
        return self._choose(list(candidates), None)

    def stats(self) -> dict[str, Any]:
        aliases = sum(len(e.aliases) for e in self._entries)
        return {
            "entries": len(self._entries),
            "aliases": aliases,
            "keys": sum(len(e.all_aliases()) for e in self._entries),
            "bilingual": all(e.title_zh and e.title_en for e in self._entries),
        }


def load_default() -> KnowledgeBase:
    """Load the packaged knowledge base.

    The dictionary is the main file plus everything in the ``elements``
    folder next to it, so new topics can be added as separate fragments.
    An alias that is already taken by the main file is skipped, so a
    fragment that has been merged in (see ``tools/merge_elements.py``)
    does not produce a second card for the same control.
    """

    from ..paths import ELEMENTS_FILE

    raw: list[dict[str, Any]] = []
    raw.extend(KnowledgeBase._raw_entries(Path(ELEMENTS_FILE)))
    folder = Path(ELEMENTS_FILE).parent / "elements"
    if folder.is_dir():
        for fragment in sorted(folder.glob("*.yaml")):
            raw.extend(KnowledgeBase._raw_entries(fragment))
    raw = KnowledgeBase._unique_by_alias(raw)
    return KnowledgeBase(
        [KnowledgeBase._entry_from_raw(entry) for entry in raw]
    )
