# Praatao Praat probes

`.praat` scripts that Praatao hands to the running Praat GUI with
`Praat.exe --send <script>`.

| File | Purpose |
|------|---------|
| `snapshot.praat` | Writes the semantic state of Praat to a file. |

## `snapshot.praat`

The template contains one placeholder, `@OUT@`, which the probe replaces
with the path of the file the script should write (forward slashes).  The
script is strictly read-only: it never changes the selection, so the user
never notices the probe.

### Output format

One record per line, fields separated by a single TAB, lines terminated by
CRLF.  Praat writes ANSI text for ASCII content and switches to UTF-16 as
soon as a non-ASCII character appears, so the reader detects the encoding.

| Record | Meaning |
|--------|---------|
| `V<TAB><version>` | Praat version, e.g. `6.4.12` |
| `N<TAB><n>` | number of selected objects |
| `S<TAB><id><TAB><full name>` | one record per selected object; `id` is Praat's object id, the full name is `<Type> <name>` (e.g. `Sound demo_vowel`) |
| `A<TAB><duration><TAB><sampling frequency><TAB><channels><TAB><start><TAB><end>` | attributes of a single selected `Sound` (omitted when the selection is empty or holds something else) |
| `T<TAB><n>` | number of tiers of the selected `TextGrid` |
| `I<TAB><index><TAB><tier name>` | one record per tier |
| `E` | end-of-probe marker; its absence means the script died half way |

Inside a name a backslash is doubled and a TAB or newline is written as
`\t` / `\n`; the reader undoes that.

### What the script cannot do

Praat's scripting language has **no** way to enumerate the whole object
list: there is no `numberOfObjects()`, and `object[i]` only exposes numeric
attributes (`xmin`, `nx`, ...), never a name or a type.  The complete list
of objects is therefore read from the Objects window through UI Automation
(`1. Sound demo_vowel`); the script only reports the selection.

## Rules for writing probes

* A failing Praat script opens a **modal message box** in the running
  Praat, and every later `--send` call blocks until that box is closed.
  Therefore: guard every command that can fail (for instance
  `Get number of tiers` only works when exactly one `TextGrid` is
  selected), and always call `--send` with a timeout.
* Praat scripts have **no** backslash escapes in string literals: `"\t"` is
  a backslash followed by a `t`.  Use the `tab$` and `newline$` constants
  for the real characters.
* `writeFileLine: "path", <expression>` takes an *expression* as its
  second argument; quoting it writes the literal text.
