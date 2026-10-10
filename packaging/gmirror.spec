# -*- mode: python ; coding: utf-8 -*-
"""
G-Mirror PyInstaller Spec File
Produces a single-folder distributable for Windows x64.
Run: pyinstaller gmirror.spec (or pyinstaller packaging/gmirror.spec)
"""

import os
from pathlib import Path

block_cipher = None

# Resolve project root regardless of where spec file is invoked from
spec_dir = Path(SPECPATH).resolve()
if spec_dir.name == "packaging":
    root_dir = spec_dir.parent
else:
    root_dir = spec_dir

main_script = str(root_dir / "main.py")
styles_src = str(root_dir / "ui" / "styles" / "*.qss")
icons_ico = str(root_dir / "assets" / "icons" / "*.ico")
icons_png = str(root_dir / "assets" / "icons" / "*.png")
app_icon = str(root_dir / "assets" / "icons" / "gmirror.ico")

a = Analysis(
    [main_script],
    pathex=[str(root_dir)],
    binaries=[],
    datas=[
        (styles_src, 'ui/styles'),
        (icons_ico, 'assets/icons'),
        (icons_png, 'assets/icons'),
    ],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtMultimedia',
        'zeroconf',
        'zeroconf._utils',
        'zeroconf._dns',
        'av',
        'sounddevice',
        'cryptography',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'numpy',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'pandas', 'IPython'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='GMirror',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,   # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=app_icon,
    version_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='GMirror',
)
