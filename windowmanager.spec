# -*- mode: python ; coding: utf-8 -*-

import sys
import os

# 获取项目根目录
project_root = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(project_root, 'src')

a = Analysis(
    ['src/app.py'],
    pathex=[project_root, src_dir],  # 显式设置项目根目录和src目录路径
    binaries=[],
    datas=[('config.json', '.'), ('src/files', 'files')],
    hiddenimports=[
        'win32gui',
        'win32api', 
        'win32con',
        'pystray',
        'PIL',
        'tkinter',
        'tkinter.ttk',
        'logging',
        'core',
        'manager',
        'hotkey_manager',
        'time_sync',
        'utils',
        'config',
        'constants',
        'ui',
        'ui_main',
        'ui_time_sync',
        'ui_settings',
        'ui_log',
        'ui_about'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='WindowManager',
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
)