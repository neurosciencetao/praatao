"""Desktop evidence capture.

Moves the real mouse over a named Praat control, lets Praatao react, and
screenshots the result.  This is how we prove the overlay works on the real
machine rather than in theory.

    python prototypes/v1/demo_capture.py --target "View & Edit"
    python prototypes/v1/demo_capture.py --menu Open --item "Read from file..."
"""

from __future__ import annotations

import argparse
import ctypes
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

user32 = ctypes.windll.user32

OUT_DIR = ROOT / "docs" / "screenshots"


def move_mouse(x: int, y: int) -> None:
    user32.SetCursorPos(int(x), int(y))


def shot(path: Path) -> Path:
    from PIL import ImageGrab

    path.parent.mkdir(parents=True, exist_ok=True)
    img = ImageGrab.grab(all_screens=True)
    img.save(path)
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="View & Edit",
                    help="name of the Praat control to hover")
    ap.add_argument("--menu", default=None,
                    help="open this menu first, then hover --item")
    ap.add_argument("--item", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--lang", default="zh")
    ap.add_argument("--wait", type=float, default=2.5)
    ap.add_argument("--select", type=int, default=None,
                    help="select the object with this id first (Praat's dynamic "
                         "buttons only appear for a selection)")
    ap.add_argument("--ui", choices=("auto", "qt", "tk"), default="auto")
    args = ap.parse_args()

    from praatao import paths

    if args.select is not None:
        import tempfile

        from praatao.sensors.praat_state import PraatStateProbe

        probe = PraatStateProbe()
        probe.dismiss_dialogs()
        script = Path(tempfile.gettempdir()) / "_praatao_select.praat"
        script.write_text(f"selectObject: {args.select}\n", encoding="utf-8")
        import subprocess

        subprocess.run([str(paths.PRAAT_EXE), "--send", str(script)],
                       check=False, timeout=15,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.2)
        probe.dismiss_dialogs()
        print(f"selected object id {args.select}")

    from praatao import paths
    from praatao.sensors.uia import PraatUI, normalize_name  # noqa: E402

    # A modal "Message" box left by a failing Praat script freezes the whole
    # UI (the dynamic buttons disappear), so clear it before capturing.
    try:
        from praatao.sensors.praat_state import PraatStateProbe

        dismissed = PraatStateProbe().dismiss_dialogs()
        if dismissed:
            print(f"cleared {dismissed} modal Praat dialog(s)")
    except Exception as exc:
        print("could not clear dialogs:", exc)

    ui = PraatUI()
    windows = ui.windows()
    if not windows:
        print("Praat is not running")
        return 1

    # -- find the target -------------------------------------------
    owner = None
    if args.menu:
        obj = ui.objects_window()
        if obj is None:
            print("no Objects window")
            return 1
        items = ui.open_menu(obj, args.menu, keep_open=True)
        names = [normalize_name(i.name) for i in items]
        target = None
        for item in items:
            if normalize_name(item.name) == normalize_name(args.item or ""):
                target = item
                break
        if target is None:
            ui.close_popup(obj)
            print(f"menu item not found. available: {names}")
            return 1
        rect = target.rect
    else:
        # Find the control *and* the window that owns it, so that the
        # window can be brought to the front before the capture.
        target = None
        owner = None
        for window in ui.windows():
            found = ui.find(args.target, window=window)
            if found is not None:
                target, owner = found, window
                break
        if target is None:
            print(f"control not found: {args.target}")
            print("available buttons:")
            for w in windows:
                for e in ui.tree(w, max_depth=3):
                    if e.name and e.control_type in ("ButtonControl", "MenuItemControl"):
                        print("   ", repr(e.name), e.rect)
            return 1
        rect = target.rect

    print(f"target {target.name!r} at {rect}")

    # Bring the window that owns the control to the front, so that the
    # capture shows the control and not whatever is lying on top of it.
    if owner is not None and ui._activate(owner):
        print(f"activated {owner.title!r}")
        time.sleep(0.6)

    # -- start Praatao ---------------------------------------------
    from praatao.tutor.kb import load_default
    from praatao.tutor.advisor import Advisor
    from praatao.ui.hover import source_label

    kb = load_default()
    advisor = Advisor(kb, lang=args.lang)

    # The real application, so that the capture shows exactly what a user
    # sees - including the Qt card and the spotlight.
    import run as praatao_run

    app = praatao_run.Praatao(lang=args.lang, use_llm=False,
                              ui_backend=args.ui)
    print("backend:", app.backend)
    card, spot = app.card, app.spot

    left, top, right, bottom = rect
    move_mouse((left + right) // 2, (top + bottom) // 2)

    element = ui.element_at_point((left + right) // 2, (top + bottom) // 2)
    if element is None:
        print("could not hit-test the target")
        app.quit()
        return 1

    advice = advisor.advise(element)
    print("headline:", advice.headline)
    print("source  :", advice.source)
    print("body    :", advice.body[:400])

    card.show(advice.headline, advice.body,
              anchor=((left + right) // 2, (top + bottom) // 2),
              rect=rect,
              source=source_label(advice.source),
              signature=(normalize_name(element.name), advice.headline))
    spot.show(rect)
    app._raise_card()
    for _ in range(20):
        app.pump()
        time.sleep(0.03)
    time.sleep(args.wait)
    for _ in range(10):
        app.pump()
        time.sleep(0.03)

    out = Path(args.out) if args.out else OUT_DIR / f"hover-{args.target.replace(' ', '_').replace('&', 'and')}.png"
    path = shot(out)
    print("saved", path)

    if args.menu:
        ui.close_popup()
    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
