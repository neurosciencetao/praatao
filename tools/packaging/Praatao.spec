# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Praatao.

Build with::

    python -m PyInstaller --noconfirm tools\\packaging\\Praatao.spec

The result is ``dist\\Praatao\\Praatao.exe``.  It is a *windowed* build
(no console window) and an *onedir* build (the folder starts instantly, a
one-file build would unpack itself on every start).

``Praat.exe`` is copied next to the executable by
``tools\\packaging\\build.py``, because the launcher looks for it there.
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

ROOT = Path(SPECPATH).resolve().parents[1]

datas = [
    (str(ROOT / "praatao" / "content"), "praatao/content"),
]
datas += collect_data_files("praatao")

hiddenimports = [
    "uiautomation",
    "win32api",
    "win32gui",
    "win32process",
    "win32con",
    "win32com.client",
    "yaml",
    "PySide6.QtWidgets",
    "PySide6.QtGui",
    "PySide6.QtCore",
]

a = Analysis(
    [str(ROOT / "run.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["matplotlib", "numpy", "pytest", "IPython"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Praatao",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "Praat.exe") if (ROOT / "Praat.exe").exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Praatao",
)
