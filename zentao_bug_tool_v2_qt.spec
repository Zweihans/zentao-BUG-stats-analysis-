# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['zentao_bug_tool_v2_qt.py'],
    pathex=[],
    binaries=[],
    datas=[
        # 不打包数据文件，保持外部可编辑
    ],
    hiddenimports=['PyQt6', 'PyQt6.QtCore', 'PyQt6.QtWidgets', 'PyQt6.QtGui',
                   'playwright', 'playwright.sync_api', 'playwright._impl',
                   'greenlet', 'pandas', 'openpyxl', 'json', 'logging',
                   'threading', 'pathlib', 'datetime', 'zentao_importer'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
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
    name='禅道BUG分析工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
