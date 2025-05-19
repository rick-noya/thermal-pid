# -*- mode: python ; coding: utf-8 -*-

# PyInstaller Spec file for Senxor Thermal Control & Analysis application
# Generated automatically for Windows build with GUI (no console).
# Build command example:
#   pyinstaller --clean --noconfirm senxor_app.spec

block_cipher = None

import sys
from pathlib import Path

# Ensure path to project root is included so local modules resolve
project_root = Path.cwd()
pathex = [str(project_root)]

# Include configuration YAML alongside executable
_datas = [
    ('config.yaml', '.')
]

# Hidden imports that PyInstaller may not detect automatically
_hidden_imports = [
    'serial.tools.list_ports',
    'PIL.ImageTk',
    'cv2',
    'cv2.cv2',
    'matplotlib.backends.backend_tkagg',
    'yaml',
    'packaging',
    'crcmod',
]


a = Analysis(
    ['main.py'],
    pathex=pathex,
    binaries=[],
    datas=_datas,
    hiddenimports=_hidden_imports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SenxorApp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # GUI application; set to True if console diagnostics desired
    icon=None,
)

# ----- Updater stub build -----

up_a = Analysis(
    ['updater/update_stub/stub.py'],
    pathex=pathex,
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

up_pyz = PYZ(up_a.pure, up_a.zipped_data, cipher=block_cipher)

up_exe = EXE(
    up_pyz,
    up_a.scripts,
    [],
    exclude_binaries=True,
    name='senxor_updater',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=None,
)

coll = COLLECT(
    exe,
    up_exe,
    a.binaries + up_a.binaries,
    a.zipfiles + up_a.zipfiles,
    a.datas + up_a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SenxorApp',
) 