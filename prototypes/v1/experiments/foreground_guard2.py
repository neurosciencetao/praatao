"""The coach must not pull Praat to the front while the student works.

The deep probe sends a Praat script every few seconds, and ``--send``
activates the Praat window.  With another program in front, the script
must not be sent at all.

The trace shows which part of the tick loop moved the foreground.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import win32gui  # noqa: E402

import run as praatao_run  # noqa: E402
from praatao.sensors.uia import PraatUI  # noqa: E402


def foreground() -> str:
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return "<none>"
    return f"{win32gui.GetClassName(hwnd)} {win32gui.GetWindowText(hwnd)[:30]!r}"


def a_non_praat_window() -> int:
    found = 0

    def _collect(hwnd: int, _extra: object) -> None:
        nonlocal found
        if found:
            return
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return
            cls = (win32gui.GetClassName(hwnd) or "").casefold()
            title = win32gui.GetWindowText(hwnd) or ""
            if "praat" in cls or title.startswith("Praatao"):
                return
            if cls in ("consolewindowclass", "progman", "shell_traywnd",
                       "thumbnaildevicehelperwnd"):
                return
            found = hwnd
        except Exception:
            return

    win32gui.EnumWindows(_collect, None)
    return found


def force_foreground(hwnd: int) -> bool:
    """Put a window in front, lifting the foreground lock if needed."""

    import win32api
    import win32process

    try:
        current = win32api.GetCurrentThreadId()
        foreground = win32gui.GetForegroundWindow()
        other = win32process.GetWindowThreadProcessId(foreground)[0]
        attached = bool(win32process.AttachThreadInput(current, other, True))
        try:
            win32gui.SetForegroundWindow(hwnd)
        finally:
            if attached:
                win32process.AttachThreadInput(current, other, False)
        time.sleep(0.5)
        return win32gui.GetForegroundWindow() == hwnd
    except Exception:
        return False


def main() -> int:
    ui = PraatUI()
    if ui.objects_window() is None:
        print("Praat is not running")
        return 1

    app = praatao_run.Praatao(lang="zh", use_llm=False, ui_backend="qt")
    app.host.after(praatao_run.MOUSE_POLL_MS, app._mouse_poll)
    app.host.after(45, app._tick)

    if "--no-deep" in sys.argv:
        # Keep the deep probe (the one that sends a Praat script) quiet.
        app._last_deep_poll = time.monotonic() + 1e9
        print("deep probe: disabled")
    if "--no-spot" in sys.argv:
        app.spot.show = lambda *a, **kw: None
        app.spot.hide = lambda *a, **kw: None
        print("spotlight: disabled")
    if "--no-card" in sys.argv:
        app.card.show = lambda *a, **kw: None
        print("card: disabled")
    if "--no-canvas" in sys.argv:
        app.canvas = None
        print("canvas: disabled")
    if "--no-raise" in sys.argv:
        app.card.raise_ = lambda *a, **kw: None
        app.panel.raise_ = lambda *a, **kw: None
        print("raise_: disabled")

    events: list[str] = []
    start = time.time()

    def stamp(message: str) -> None:
        events.append(f"{time.time() - start:6.2f}s  {message}")

    for name in ("_poll_state", "_poll_deep_state", "_handle_hover",
                 "_handle_canvas_hover", "_canvas_under_cursor",
                 "_element_under_cursor", "_popup_item_under_cursor",
                 "_raise_card", "_advise_element", "_menu_open",
                 "_update_auto_hide", "_dismiss_hover", "_refresh_panel"):
        if not hasattr(app, name):
            continue
        original = getattr(app, name)

        def make(name=name, original=original):
            def traced(*args, **kwargs):
                before = foreground()
                original(*args, **kwargs)
                after = foreground()
                mark = "  *** MOVED ***" if before != after else ""
                stamp(f"{name}: {after[:38]}{mark}")
            return traced

        setattr(app, name, make())

    if app.canvas is not None:
        original_capture = app.canvas.capture

        def traced_capture(*args, **kwargs):
            before = foreground()
            result = original_capture(*args, **kwargs)
            after = foreground()
            mark = "  *** MOVED ***" if before != after else ""
            stamp(f"canvas.capture: {after[:38]}{mark}")
            return result

        app.canvas.capture = traced_capture

    original_panel_show = app.panel.show

    def traced_panel_show(*args, **kwargs):
        before = foreground()
        result = original_panel_show(*args, **kwargs)
        after = foreground()
        mark = "  *** MOVED ***" if before != after else ""
        stamp(f"panel.show: {after[:38]}{mark}")
        return result

    app.panel.show = traced_panel_show

    original_popup_items = app.ui.open_popup_items

    def traced_popup_items(*args, **kwargs):
        before = foreground()
        result = original_popup_items(*args, **kwargs)
        after = foreground()
        mark = "  *** MOVED ***" if before != after else ""
        stamp(f"ui.open_popup_items: {after[:38]}{mark}")
        return result

    app.ui.open_popup_items = traced_popup_items

    from praatao.sensors.praat_state import PraatStateProbe

    original_send = PraatStateProbe.send

    def traced_send(self, script, timeout=10.0):  # noqa: ANN001
        stamp(">>> a Praat script is being sent")
        return original_send(self, script, timeout)

    PraatStateProbe.send = traced_send  # type: ignore[method-assign]

    for label, holder, attribute in (
        ("card.show", app.card, "show"),
        ("card.raise_", app.card, "raise_"),
        ("spot.show", app.spot, "show"),
    ):
        if not hasattr(holder, attribute):
            continue
        original_method = getattr(holder, attribute)

        def make_method(label=label, original_method=original_method):
            def traced_method(*args, **kwargs):
                before = foreground()
                result = original_method(*args, **kwargs)
                after = foreground()
                mark = "  *** MOVED ***" if before != after else ""
                stamp(f"{label}: {after[:38]}{mark}")
                return result

            return traced_method

        setattr(holder, attribute, make_method())

    # Our own side panel is the ideal "other application in front": a
    # process may always bring its own window forward.
    app.panel.show()
    app.pump()
    try:
        target = int(app.panel.win.winId())
    except Exception:
        target = a_non_praat_window()
    print("other window:", win32gui.GetClassName(target) if target else "<none>")
    if target:
        print("activated   :", force_foreground(target))
    time.sleep(0.5)
    before = foreground()
    print("foreground before:", before)
    stamp(f"start: {before}")

    # A sampler watches the foreground all the time, so the moment of the
    # change is known even when it happens between two traced calls.
    samples: list[tuple[float, str]] = []
    stop = False

    def sample() -> None:
        while not stop:
            samples.append((time.time() - start, foreground()))
            time.sleep(0.02)

    import threading

    thread = threading.Thread(target=sample, daemon=True)
    thread.start()

    deadline = time.time() + 20.0
    while time.time() < deadline:
        app.pump()
        time.sleep(0.05)
    stop = True
    after = foreground()
    print("foreground after :", after)
    print("STAYED PUT       :", after == before)
    print("--- the samples around the change ---")
    changed_at = None
    for index, (moment, text) in enumerate(samples):
        if index and text != samples[index - 1][1]:
            changed_at = moment
            for one in samples[max(0, index - 3): index + 2]:
                print(f"    {one[0]:6.2f}s  {one[1][:44]}")
            break
    print("--- the events around that moment ---")
    if changed_at is not None:
        for line in events:
            try:
                moment = float(line.split("s")[0])
            except ValueError:
                continue
            if abs(moment - changed_at) < 0.3:
                print("   ", line)
    app.quit()
    return 0 if after == before else 1


if __name__ == "__main__":
    sys.exit(main())
