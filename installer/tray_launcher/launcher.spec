# PyInstaller spec for Z1N MF Analyser tray launcher.
# Build:  pyinstaller installer/tray_launcher/launcher.spec --clean --noconfirm

import os

block_cipher = None

a = Analysis(
    ['launcher.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('wizard.py', '.'),
    ],
    hiddenimports=[
        'pystray._win32',     # Windows backend
        'PIL._tkinter_finder',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'pandas', 'scipy'],  # not used by launcher
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Z1NLauncher',
    icon=os.path.join('..', 'assets', 'z1n.ico') if os.path.exists(
        os.path.join('..', 'assets', 'z1n.ico')
    ) else None,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,            # UPX often flagged by AV; skip
    console=False,        # --windowed: no console window
    runtime_tmpdir=None,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
