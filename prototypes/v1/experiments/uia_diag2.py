"""Diagnostic 2: close the popup without disturbing the Praat selection."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import uiautomation as auto  # noqa: E402
import win32con  # noqa: E402
import win32gui  # noqa: E402

from praatao.sensors.uia import PraatUI  # noqa: E402


def state(ui, label):
    obj = ui.objects_window()
    buttons = [b.name for b in ui.find_all(window=obj, control_type="ButtonControl")]
    menus = [m.name for m in ui.find_all(window=obj, control_type="MenuControl")]
    fg = auto.GetForegroundWindow()
    try:
        fg_title = win32gui.GetWindowText(fg)
    except Exception:
        fg_title = "?"
    print(f"   [{label}] popup={menus} fg={fg_title!r} has_view_edit={'View & Edit' in buttons}")
    return menus, buttons


def open_popup(ui, obj):
    ctrl = ui._control_from_window(obj)
    for node, _d in ui._iter_controls(ctrl):
        try:
            if node.ControlTypeName == "MenuItemControl" and node.Name == "Open":
                ui._click_control(node)
                time.sleep(0.6)
                return node
        except Exception:
            pass
    return None


def popup_hwnd(ui, obj):
    for node, _d in ui._iter_controls(ui._control_from_window(obj)):
        try:
            if node.ControlTypeName == "MenuControl":
                return int(node.NativeWindowHandle)
        except Exception:
            pass
    return 0


def main() -> int:
    ui = PraatUI()
    obj = ui.objects_window()
    print("objects:", obj)

    print("\n== A: PostMessage ESC to the popup window ==")
    state(ui, "before")
    open_popup(ui, obj)
    state(ui, "popup open")
    ph = popup_hwnd(ui, obj)
    print("   popup hwnd:", ph, "class:", win32gui.GetClassName(ph) if ph else None)
    win32gui.PostMessage(ph, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0)
    win32gui.PostMessage(ph, win32con.WM_KEYUP, win32con.VK_ESCAPE, 0)
    time.sleep(0.8)
    state(ui, "after PostMessage ESC")

    print("\n== B: WM_CANCELMODE to the owner window ==")
    open_popup(ui, obj)
    state(ui, "popup open")
    ph = popup_hwnd(ui, obj)
    owner = win32gui.GetWindow(ph, win32con.GW_OWNER) or obj.hwnd
    print("   popup hwnd:", ph, "owner:", owner)
    win32gui.PostMessage(owner, win32con.WM_CANCELMODE, 0, 0)
    time.sleep(0.8)
    state(ui, "after WM_CANCELMODE")

    print("\n== C: SendKeys ESC (current behaviour) ==")
    open_popup(ui, obj)
    state(ui, "popup open")
    auto.SendKeys("{ESC}")
    time.sleep(0.8)
    state(ui, "after SendKeys ESC")

    print("\n== D: click the menu bar item again (toggle) ==")
    open_popup(ui, obj)
    state(ui, "popup open")
    ctrl = ui._control_from_window(obj)
    for node, _d in ui._iter_controls(ctrl):
        try:
            if node.ControlTypeName == "MenuItemControl" and node.Name == "Open":
                ui._click_control(node)
                break
        except Exception:
            pass
    time.sleep(0.8)
    state(ui, "after second click")

    return 0


if __name__ == "__main__":
    sys.exit(main())
