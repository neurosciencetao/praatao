"""Why does the hover card not appear for 'View & Edit' right now?"""

from __future__ import annotations

import ctypes
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from praatao.sensors.uia import PraatUI, normalize_name  # noqa: E402
from praatao.tutor.advisor import Advisor  # noqa: E402
from praatao.tutor.kb import load_default  # noqa: E402

ui = PraatUI()
target = ui.find("View & Edit")
print("target:", target)
if target is None:
    obj = ui.objects_window()
    print("names:", [normalize_name(e.name) for e in ui.tree(obj, max_depth=4) if e.name])
    raise SystemExit(0)

left, top, right, bottom = target.rect
cx, cy = (left + right) // 2, (top + bottom) // 2
print("centre:", (cx, cy))
ctypes.windll.user32.SetCursorPos(cx, cy)
time.sleep(0.3)

el = ui.element_at_point(cx, cy)
print("hit test:", el)

kb = load_default()
print("kb lookup:", kb.lookup(normalize_name(target.name), target.control_type))

advisor = Advisor(kb, lang="zh")
if el is not None:
    advice = advisor.advise(el)
    print("headline:", advice.headline)
    print("source:", advice.source)
    print("body len:", len(advice.body))
    print("body:", advice.body[:200])

    print("\n--- now with a live state ---")
    from praatao.sensors.praat_state import PraatStateProbe

    state = PraatStateProbe().snapshot()
    print("state:", state)
    advice2 = advisor.advise(el, state=state)
    print("headline:", repr(advice2.headline))
    print("source:", advice2.source)
    print("body len:", len(advice2.body))
    print("body:", repr(advice2.body[:300]))
