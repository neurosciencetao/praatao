"""The user's own settings for Praatao.

Three things the student may want to change without editing a file:

* the language of the explanations (Chinese or English),
* whether the language model may be used at all,
* whether a picture of the drawing area may be sent to the model.

They are stored in ``%LOCALAPPDATA%\\praatao\\settings.json`` (or
``PRAATAO_STATE_DIR``), which never leaves the machine.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

LANG_ZH = "zh"
LANG_EN = "en"
SUPPORTED_LANGS: tuple[str, ...] = (LANG_ZH, LANG_EN)

#: The file name inside the state directory.
FILE_NAME = "settings.json"


def settings_path() -> Path:
    """Where the settings live."""

    try:
        from . import paths

        return Path(paths.ensure_state_dir()) / FILE_NAME
    except Exception:  # pragma: no cover - a broken checkout still runs
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home())
        return base / "praatao" / FILE_NAME


@dataclass
class Settings:
    """What the student chose."""

    lang: str = LANG_ZH
    use_llm: bool = True
    allow_vision: bool = False

    def __post_init__(self) -> None:
        if self.lang not in SUPPORTED_LANGS:
            self.lang = LANG_ZH
        self.use_llm = bool(self.use_llm)
        self.allow_vision = bool(self.allow_vision)

    @classmethod
    def load(cls, path: str | Path | None = None) -> "Settings":
        """Read the settings; a missing or broken file gives the defaults."""

        target = Path(path) if path is not None else settings_path()
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except Exception:
            return cls()
        if not isinstance(data, dict):
            return cls()
        return cls(
            lang=str(data.get("lang") or LANG_ZH),
            use_llm=bool(data.get("use_llm", True)),
            allow_vision=bool(data.get("allow_vision", False)),
        )

    def save(self, path: str | Path | None = None) -> bool:
        """Write the settings; returns ``False`` when that is not possible."""

        target = Path(path) if path is not None else settings_path()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps(asdict(self), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return True
        except Exception:  # noqa: BLE001
            return False
