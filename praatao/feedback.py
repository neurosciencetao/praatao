"""Let a student report a problem without leaving the program.

The report becomes a **GitHub issue**: the program opens the browser on
a pre-filled "new issue" page and the student reads it before sending
it.  Nothing is sent silently - the student always sees what is about
to be posted, and can change it.

A copy is kept on the machine as well, so nothing is lost when the
browser does not open or when the student decides not to post at all.

The body is written in a fixed shape (a small block of ``key: value``
lines) so that the issues can be read by a program later on: that is how
the feedback can be sorted out and, where it makes sense, fixed
automatically.
"""

from __future__ import annotations

import os
import platform
import time
import webbrowser
from pathlib import Path
from typing import Any

#: Where the issues live.
GITHUB_OWNER = "neurosciencetao"
GITHUB_REPO = "praatao"


def issue_url(title: str, body: str) -> str:
    """The address of a GitHub page with the report already filled in."""

    from urllib.parse import quote

    return (
        f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/issues/new"
        f"?title={quote(title)}&body={quote(body)}"
    )


def _version() -> str:
    try:
        from praatao import __version__

        return str(__version__)
    except Exception:  # pragma: no cover
        return "unknown"


def build_body(
    feedback: str,
    email: str = "",
    *,
    praat_version: str = "",
    extra: dict[str, Any] | None = None,
) -> str:
    """The text of the issue.

    The first lines are what a human reads, the block below them is what
    a program reads.
    """

    feedback = (feedback or "").strip()
    email = (email or "").strip()
    lines: list[str] = []
    lines.append("## 学生反馈")
    lines.append("")
    lines.append(feedback or "（没有写文字）")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("<!-- praatao-feedback:begin -->")
    lines.append("app: Praatao " + _version())
    lines.append("praat: " + (praat_version or "unknown"))
    lines.append("windows: " + platform.platform())
    lines.append("python: " + platform.python_version())
    lines.append("email: " + (email or "(none)"))
    if extra:
        for key, value in extra.items():
            lines.append(f"{key}: {value}")
    lines.append("<!-- praatao-feedback:end -->")
    return "\n".join(lines)


def build_title(feedback: str) -> str:
    """The title of the issue: the first line of what the student wrote."""

    first = (feedback or "").strip().splitlines()
    head = first[0].strip() if first else ""
    if len(head) > 80:
        head = head[:77] + "..."
    return "[反馈] " + (head or "一个没有标题的问题")


def feedback_folder() -> Path:
    """Where the local copies of the reports are kept."""

    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "praatao" / "feedback"


def save_locally(body: str, title: str = "") -> Path:
    """Keep a copy of the report on this machine."""

    folder = feedback_folder()
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except Exception:  # pragma: no cover
        return Path()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = folder / f"feedback-{stamp}.md"
    try:
        header = f"# {title}\n\n" if title else ""
        path.write_text(header + body, encoding="utf-8")
    except Exception:  # pragma: no cover
        return Path()
    return path


def open_in_browser(url: str) -> bool:
    """Open the report page in the default browser."""

    try:
        return bool(webbrowser.open(url))
    except Exception:  # pragma: no cover
        return False
