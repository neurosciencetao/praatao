"""Praatao: a companion overlay that teaches Praat while you use it.

Layers
------
``sensors``  read Praat's live state (Windows UI Automation + Praat scripts)
``tutor``    turn that state into guidance (knowledge base, lessons, optional LLM)
``ui``       render guidance next to Praat without stealing clicks
"""

from __future__ import annotations

__version__ = "1.0.0"
__all__ = ["__version__"]
