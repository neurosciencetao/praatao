# v1 interface contracts

> Single source of truth for module APIs. If you need to change a signature,
> change it here **and** tell the lead, so the other side stays consistent.

## Layer picture

```
   mouse  ──►  praatao.sensors.uia          (what is under the cursor?)
   Praat  ──►  praatao.sensors.praat_state  (what does Praat contain?)
                    │
                    ▼
            praatao.tutor.kb / lessons / advisor        (what should we say?)
                    │
                    ▼
            praatao.ui.hover / spotlight / panel         (how do we say it?)
```

Nothing in `ui/` may import from `sensors/`; `ui` receives plain data.
Nothing in `sensors/` may import from `tutor/` or `ui/`.

---

## `praatao.paths`

Already implemented. Exposes `ROOT`, `PRAAT_EXE`, `CONTENT_DIR`,
`ELEMENTS_FILE`, `LESSONS_DIR`, `STATE_DIR`, `ensure_state_dir()`.

---

## `praatao.sensors.uia`  (owner: uia teammate)

```python
@dataclass(frozen=True)
class Element:
    name: str                  # raw UIA name (may contain U+202F and '>' suffixes)
    control_type: str          # 'ButtonControl', 'MenuItemControl', 'ListItemControl', ...
    automation_id: str
    hwnd: int
    rect: tuple[int, int, int, int] | None   # (left, top, right, bottom) screen px
    window_title: str
    depth: int = 0

    @property
    def key(self) -> str: ...           # normalized lookup key
    def contains_point(self, x: int, y: int) -> bool: ...

def normalize_name(raw: str) -> str: ...
    # -> strips U+202F / NBSP, collapses runs of spaces, strips trailing '>',
    # strips trailing ellipsis-free whitespace, strips trailing ':' and '\t...'
    # '     Draw  >'  -> 'Draw'
    # 'Read from file...\tCtrl-O' -> 'Read from file...'
    # '1. Sound demo_vowel' -> 'Sound demo_vowel'   (list items lose the index)

@dataclass(frozen=True)
class UiaWindow:
    hwnd: int
    title: str
    class_name: str
    rect: tuple[int, int, int, int]
    kind: str                  # 'objects' | 'picture' | 'editor' | 'other'

class PraatUI:
    def __init__(self, praat_exe: Path | None = None) -> None: ...

    def windows(self) -> list[UiaWindow]: ...
    def objects_window(self) -> UiaWindow | None: ...
    def picture_window(self) -> UiaWindow | None: ...
    def editor_windows(self) -> list[UiaWindow]: ...      # title '2. Sound demo_vowel'
    def window_at_point(self, x: int, y: int) -> UiaWindow | None: ...

    def tree(self, window: UiaWindow, max_depth: int = 8) -> list[Element]: ...
    def element_at_point(self, x: int, y: int) -> Element | None: ...
    def find(self, name: str, *, window: UiaWindow | None = None,
             control_type: str | None = None) -> Element | None: ...
    def find_all(self, window: UiaWindow | None = None,
                 control_type: str | None = None) -> list[Element]: ...
    def invoke(self, element: Element) -> bool: ...     # UIA Invoke, fallback Click
    def open_menu(self, window: UiaWindow, menu_name: str,
                  timeout: float = 2.0) -> list[Element]: ...
        # clicks the menu, returns the popup items, closes the popup again
```

### Ground truth observed on this machine (Praat 6.x, Windows)

* Objects window: class `PraatShell1 Praat`, title `Praat Objects`.
* Picture window: class `PraatChildWindow1 Praat`, title `Praat Picture`.
* Editor window: class `PraatChildWindow1 Praat`, title is the **list label**
  (`2. Sound demo_vowel`), *not* `Sound demo_vowel`.
* Buttons exposed with exact names: `Rename...`, `Copy...`, `Inspect`, `Info`,
  `Remove`, `Sound help`, `View & Edit`, `Play`, `To Intensity...`.
* Dynamic action buttons (Sound selected) are named with leading U+202F and a
  trailing `>`: `'\u202f\u202f   Draw  >'`, `Query`, `Modify`, `Annotate`,
  `Analyse periodicity`, `Analyse spectrum`, `Manipulate`, `Convert`,
  `Filter`, `Combine`.
* Object list items are `ListItemControl` named `1. Sound demo_vowel`.
* Menu bar items: `Praat`, `New`, `Open`, `Save`, `Help`.
* Popup menu items are reachable: `MenuControl` named `Open` contains
  `MenuItemControl` children such as `Read from file...\tCtrl-O`.
* `uiautomation` (yinkaisheng) is installed: `uiautomation 2.0.18`.
  Use it rather than raw ctypes.

---

## `praatao.sensors.praat_state`  (owner: state teammate)

```python
@dataclass
class PraatObject:
    id: int
    type: str          # 'Sound', 'TextGrid', 'Pitch', ...
    name: str

@dataclass
class PraatState:
    running: bool
    version: str | None
    objects: list[PraatObject]
    selected: list[PraatObject]
    editor_open: bool
    editor_object: str | None
    textgrid_tiers: list[str]
    error: str | None = None
    raw: dict = field(default_factory=dict)

    @property
    def selected_types(self) -> list[str]: ...
    def selected_of(self, type_name: str) -> list[PraatObject]: ...

class PraatStateProbe:
    def __init__(self, praat_exe: Path | None = None,
                 state_dir: Path | None = None) -> None: ...
    def send(self, script: str | Path, timeout: float = 10.0) -> bool: ...
        # 'Praat.exe --send <script>'; never raises, returns False on failure.
        # MUST NOT block: use a short timeout and swallow TimeoutExpired.
    def snapshot(self, timeout: float = 3.0) -> PraatState: ...
        # full semantic snapshot (objects + selection + tiers + editor flag)
    def quick(self) -> PraatState: ...
        # window-title-only, no script, < 5 ms
```

### Notes

* `Praat.exe --send script.praat` returns in ~0.2 s for a trivial script.
* A script that opens an editor window can hang `--send`; wrap every call in
  a timeout and never assume the script finished.
* Praat script file syntax is **not** Python. Write the probe as a `.praat`
  file that writes JSON to a temp file, then read that file.
* Praat can write JSON with `writeFileLine:` / `writeFile:` and
  `string$(...)`; quote and escape carefully (use `\` escapes).

### Verified Praat scripting API (measured on this machine + official manual)

Source: <https://praat.org/manual/Scripting_4_3__Querying_objects.html>

| Expression | Meaning | Verified |
|------------|---------|----------|
| `selected$()` | full name of the topmost selected object, e.g. `Sound demo_vowel` | yes |
| `selected$("Sound")` | name of the topmost selected Sound | yes |
| `selected$("Sound", 2)` | name of the 2nd selected Sound (negative counts from the bottom) | manual |
| `selected("Sound")` | unique id of the topmost selected Sound | manual |
| `selected#("Sound")` | array of ids of all selected Sounds | manual |
| `numberOfSelected()` | number of selected objects | yes |
| `numberOfSelected("Sound")` | number of selected Sounds | manual |
| `extractWord$(fullName$, "")` | type out of a full name | manual |
| `extractLine$(fullName$, " ")` | name out of a full name | manual |
| `numberOfObjects` | **does not exist** | yes (error) |
| `selected$` (no parentheses) | **does not exist** | yes (error) |
| `selected$[1]` | **does not exist** | yes (error) |

**There is no scripting function that enumerates *all* objects**, only the
selected ones.  The complete object list therefore comes from the UIA layer
(`ListItemControl` named `1. Sound demo_vowel`).

### Praat scripting traps (all hit for real on this machine)

1. `writeFileLine: "path", expr` - the second argument is an **expression**,
   never wrap it in quotes.  `"string$(numberOfSelected())"` writes the
   literal text `'string$(numberOfSelected())'`.
2. A script error pops a **modal dialog**.  Window classes on this machine:
   * `#32770` - the modal message box (title `Message`, 3/3 reproductions)
   * `PraatShell1 Praat` - the Objects window
   * `PraatChildWindow1 Praat` - the Picture window and the object editors
   * `#32768` - a menu popup

   The title filter is **mandatory**: `PraatChildWindow1 Praat` is the class
   of the student's sound editor, so a rule that matches on the class prefix
   alone would close their editor.  Match on
   (class is `#32770` or starts with `Praat`) **and** title in
   {`Message`, `Error`, `Script error`, `Praat error`}.
   The *send that carries the failing script* blocks (10 s+ in 2 of 3 runs);
   a *later* send still succeeds in 0.14-0.21 s while the box is up.
3. The UIA tree does **not** collapse when a dialog is up.  The Objects
   window exposes **22** named nodes with nothing selected and **46** with a
   Sound selected; the extra 24 are `Sound help`, `View & Edit`, `Play`,
   `To Intensity...` and 10 x (`rowColumn` + dynamic button).  So
   *"`View & Edit` disappeared"* means "the selection changed" or "a dialog
   is up", not "UIA broke".
4. `asserterror <text>` suppresses an *expected* error and checks the message
   text - useful for probing without a dialog.
5. `Get ...` commands write to the Info window; in a script assign them:
   `mean = Get mean: 0, 0, "Hertz", "Parabolic"` (or `mean$ = ...` for text).
6. Praat script strings have **no backslash escapes**: `"\t"` is a backslash
   plus a `t`.  Use `tab$` and `newline$`.
7. Praat writes ANSI for ASCII text and flips to UTF-16 (BOM `FE FF`,
   little-endian payload) as soon as a non-ASCII character appears.
8. Selecting an object by name is **ambiguous** when two objects share a
   name.  Use the id: `selectObject: 1` (verified working).

---

## `praatao.tutor.kb`  (owner: lead)

```python
@dataclass
class KnowledgeEntry:
    id: str
    aliases: list[str]
    title_en: str
    title_zh: str
    what_en: str
    what_zh: str
    how_en: str
    how_zh: str
    concept_en: str | None
    concept_zh: str | None
    pitfalls: list[str]           # bilingual? -> use dict {'en':..,'zh':..}
    keywords: list[str]

class KnowledgeBase:
    @classmethod
    def load(cls, path: Path) -> "KnowledgeBase": ...
    def lookup(self, element_name: str,
               control_type: str | None = None) -> KnowledgeEntry | None: ...
    def search(self, query: str, limit: int = 5) -> list[KnowledgeEntry]: ...
    def entries(self) -> list[KnowledgeEntry]: ...
```

---

## `praatao.content.elements` schema  (owner: content teammate)

YAML file at `praatao/content/elements.yaml`:

```yaml
version: 1
entries:
  - id: view-and-edit
    aliases: ["View & Edit", "Open editor"]
    control_types: [ButtonControl]          # optional filter
    title: {en: "Open the sound editor", zh: "打开声音编辑器"}
    what: {en: "...", zh: "..."}
    how:  {en: "...", zh: "..."}
    concept: {en: "...", zh: "..."}         # optional, the phonetic idea
    pitfalls:
      - {en: "...", zh: "..."}
    keywords: [editor, waveform, spectrogram]
```

Matching rules:

1. Normalize the UIA name (`normalize_name`) and compare case-insensitively
   against `aliases` and `id`.
2. If no alias hits, fall back to keyword matching on the normalized name.
3. Longest alias wins.

---

## `praatao.content.lessons` schema  (owner: content teammate)

YAML files in `praatao/content/lessons/*.yaml`:

```yaml
version: 1
id: first-sound
title: {en: "Your first sound", zh: "你的第一个声音"}
steps:
  - id: read-file
    detect:
      object_types_present: []           # e.g. ['Sound']
      selected_types: []
      editor_open: false
    highlight: {kind: menu, path: ["Open", "Read from file..."]}
    tip: {en: "Load a WAV file", zh: "载入一个 WAV 文件"}
    detail: {en: "longer markdown", zh: "更长的说明"}
```

---

## `praatao.tutor.advisor` / `praatao.tutor.llm`  (owner: ai teammate)

```python
@dataclass
class Advice:
    headline: str
    body: str
    source: str            # 'kb' | 'llm' | 'kb+llm'
    element_key: str | None = None
    entries: list[KnowledgeEntry] = field(default_factory=list)

class Advisor:
    def __init__(self, kb: KnowledgeBase, state: PraatStateProbe | None = None,
                 llm: LlmClient | None = None, lang: str = "zh") -> None: ...
    def advise(self, element: Element | None,
               state: PraatState | None = None) -> Advice: ...
    def ask(self, question: str, element: Element | None = None,
            state: PraatState | None = None) -> Advice: ...
```

`LlmClient` must work with any OpenAI-compatible endpoint and with Ollama,
read from env vars, and degrade to "unavailable" when unconfigured:

```
PRAATAO_LLM_ENDPOINT   e.g. https://api.deepseek.com/v1
PRAATAO_LLM_MODEL      e.g. deepseek-chat
PRAATAO_LLM_API_KEY
PRAATAO_LLM_BACKEND    'openai' | 'ollama'
```

---

## `praatao.ui`  (owner: lead)

```python
class HoverCard:
    """Click-through card that follows the cursor and explains one element."""
    def show(self, advice: Advice, anchor: tuple[int, int], rect=None) -> None
    def hide(self) -> None
    def pin(self) -> None          # keep it open so the user can read + click
    def unpin(self) -> None

class Spotlight:
    """Ring around a target rect, click-through, always on top."""
    def show(self, rect: tuple[int, int, int, int]) -> None
    def hide(self) -> None

class SidePanel:
    """Always-on-top panel: current lesson step, state, free-text questions."""
```

Overlay rules:

* Always-on-top, `overrideredirect(True)`.
* Must be **click-through** (`WS_EX_TRANSPARENT | WS_EX_LAYERED`) so Praat keeps
  receiving mouse input, except while the user explicitly interacts with the
  panel (that window is a normal window and is therefore interactive).
* Never steal focus from Praat.

---

## Testing

* `tests/` uses plain `unittest` (no pytest dependency guaranteed).
* Tests that need a live Praat must be skipped automatically when
  `Praat.exe` is not running / not found; use
  `unittest.skipUnless(praat_available(), "Praat not running")`.
* Run everything with `python -m unittest discover -s tests -v`.
