"""Performance and robustness probe for praatao.sensors.uia.

* how long does element_at_point take (the hot path on every mouse move)?
* what happens with a stale / bogus window handle?
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from praatao.sensors.uia import PraatUI, UiaWindow  # noqa: E402


def main() -> int:
    ui = PraatUI()
    obj = ui.objects_window()
    if obj is None:
        print("Praat not running")
        return 1
    assert obj is not None

    # A point over the object list.
    items = [
        item
        for item in ui.find_all(window=obj, control_type="ListItemControl")
        if item.rect
    ]
    assert items
    rect = items[0].rect
    assert rect is not None
    x = (rect[0] + rect[2]) // 2
    y = (rect[1] + rect[3]) // 2

    print("== element_at_point x 40 ==")
    start = time.perf_counter()
    for _ in range(40):
        hit = ui.element_at_point(x, y)
    elapsed = time.perf_counter() - start
    print(f"   {(elapsed / 40) * 1000:.2f} ms per call, last hit = {hit}")

    print("\n== element_at_point over a moving cursor (40 different points) ==")
    start = time.perf_counter()
    for i in range(40):
        ui.element_at_point(x + (i % 7), y + (i % 5))
    elapsed = time.perf_counter() - start
    print(f"   {(elapsed / 40) * 1000:.2f} ms per call")

    print("\n== tree() timing ==")
    start = time.perf_counter()
    elements = ui.tree(obj)
    print(f"   tree() -> {len(elements)} elements in {(time.perf_counter() - start) * 1000:.1f} ms")

    print("\n== find() timing ==")
    start = time.perf_counter()
    ui.find("View & Edit", window=obj)
    print(f"   find() -> {(time.perf_counter() - start) * 1000:.1f} ms")

    print("\n== robustness: bogus window handle ==")
    bogus = UiaWindow(hwnd=999999, title="Nope", class_name="PraatShell1 Praat", rect=(0, 0, 0, 0), kind="other")
    print("   tree:", ui.tree(bogus))
    print("   find:", ui.find("View & Edit", window=bogus))
    print("   open_menu:", ui.open_menu(bogus, "Open", timeout=0.5))
    print("   window_at_point:", ui.window_at_point(5, 5))
    print("   element_at_point:", ui.element_at_point(-500, -500))

    print("\n== robustness: Praat not running (simulated by an empty window list) ==")
    ui._windows = []
    ui._windows_by_hwnd = {}
    ui._windows_cached_at = 0.0
    ui._enum_windows = lambda: []  # type: ignore[assignment]
    print("   windows:", ui.windows())
    print("   objects_window:", ui.objects_window())
    print("   picture_window:", ui.picture_window())
    print("   editor_windows:", ui.editor_windows())
    print("   find_all:", ui.find_all())
    print("   available:", ui.available())

    return 0


if __name__ == "__main__":
    sys.exit(main())
