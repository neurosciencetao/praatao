"""Create the desktop shortcut for Praatao.

One double-click then starts Praat and the coach.  The shortcut points at
the packaged executable (``dist\\Praatao\\Praatao.exe``) when it has been
built, and at ``Start-Praatao.cmd`` otherwise, so the launcher itself
stays the single place where the start-up logic lives.

    python tools/make_shortcut.py

Options:
    --name NAME     the name of the shortcut (default: "Praatao 助教")
    --desktop       also create it on the desktop (default)
    --start-menu    also create it in the Start menu
    --cmd           point at the .cmd launcher even when the exe exists
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "Start-Praatao.cmd"
PRAAT_EXE = ROOT / "Praat.exe"
PACKAGED = ROOT / "dist" / "Praatao" / "Praatao.exe"


def target_for(force_cmd: bool = False) -> tuple[Path, str, str]:
    """The program the shortcut starts, its folder and its icon."""

    if not force_cmd and PACKAGED.exists():
        # The packaged build carries its own Praat.exe next to it.
        return PACKAGED, str(PACKAGED.parent), str(PACKAGED.parent / "Praat.exe")
    return LAUNCHER, str(ROOT), str(PRAAT_EXE)


def make_shortcut(target: Path, program: Path, working: str,
                  arguments: str = "", description: str = "") -> bool:
    """Write one ``.lnk`` file.  Returns False when pywin32 is missing.

    pywin32's late-bound ``WScript.Shell`` mangles a path that holds
    Chinese characters (it arrives as ``??``), so the shortcut is written
    under a plain ASCII name and renamed afterwards - the file system
    handles the name perfectly well.
    """

    try:
        from win32com.client import Dispatch  # type: ignore
    except Exception:  # noqa: BLE001
        return False

    temporary = target.with_name("praatao_shortcut_tmp.lnk")
    if temporary.exists():
        temporary.unlink()
    shell = Dispatch("WScript.Shell")
    link = shell.CreateShortCut(str(temporary))
    link.Targetpath = str(program)
    link.Arguments = arguments
    link.WorkingDirectory = working
    link.Description = description or "Praat with the Praatao coach"
    link.IconLocation = f"{working}\\Praat.exe,0" if (
        Path(working) / "Praat.exe"
    ).exists() else ""
    # 7 = minimised, 3 = maximised; a windowed program has no console,
    # so the window state only matters for the .cmd fallback.
    link.WindowStyle = 7 if program.suffix.casefold() == ".exe" else 1
    link.save()
    if temporary != target:
        if target.exists():
            target.unlink()
        os.replace(temporary, target)
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create the Praatao shortcut")
    parser.add_argument("--name", default="Praatao 助教")
    parser.add_argument("--desktop", action="store_true", default=True)
    parser.add_argument("--no-desktop", dest="desktop", action="store_false")
    parser.add_argument("--start-menu", action="store_true")
    parser.add_argument("--cmd", action="store_true",
                        help="point at the .cmd launcher even when the "
                             "packaged executable exists")
    args = parser.parse_args(argv)

    program, working, _icon = target_for(args.cmd)
    if not program.exists():
        print(f"the program the shortcut needs is missing: {program}")
        return 1

    made: list[Path] = []
    if args.desktop:
        desktop = Path(os.path.expandvars(r"%USERPROFILE%\Desktop"))
        made.append(desktop / f"{args.name}.lnk")
    if args.start_menu:
        menu = Path(os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"))
        made.append(menu / f"{args.name}.lnk")

    if not made:
        print("nothing to do")
        return 1

    for path in made:
        path.parent.mkdir(parents=True, exist_ok=True)
        if make_shortcut(path, program, working):
            print("created", path)
        else:
            print("could not create", path, "(pywin32 is missing)")
            return 1
    print("it starts:", program)
    return 0


if __name__ == "__main__":
    sys.exit(main())
