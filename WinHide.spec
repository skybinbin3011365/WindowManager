# -*- mode: python ; coding: utf-8 -*-
"""
WinHide - 窗口隐藏管理器 PyInstaller 打包配置文件
"""

import sys
import os
from pathlib import Path

block_cipher = None

# 项目根目录
project_root = Path(SPECPATH)
src_dir = project_root / "src"

# 收集所有 src/*.py 模块作为 hiddenimports
src_modules = []
for f in sorted(src_dir.glob("*.py")):
    if f.stem.startswith("_"):
        continue
    if f.stem == "app":
        continue  # 入口文件不需要加入 hiddenimports
    src_modules.append(f.stem)

# 收集 widgets 子包中的模块
for f in sorted((src_dir / "widgets").glob("*.py")):
    if f.stem.startswith("_"):
        continue
    src_modules.append(f"widgets.{f.stem}")

a = Analysis(
    ['src/app.py'],
    pathex=[str(src_dir)],
    binaries=[],
    datas=[
        ('config.json', '.'),
        ('assets', 'assets'),
    ],
    hiddenimports=[
        # PySide6 组件
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtNetwork',
        # 第三方库
        'pynput.keyboard',
        'pynput.mouse',
        'win32gui', 'win32con', 'win32process', 'win32api', 'ctypes',
        'psutil', 'configparser', 'json', 'logging', 'threading',
        # === 自动收集的所有 src 模块 ===
        *src_modules,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'notebook',
        'IPython',
        'jupyter_client',
        'jupyter_core',
        'ipykernel',
        'nbformat',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'cv2',
        'selenium',
        'requests',
        'flask',
        'django',
        'sqlalchemy',
    ],
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
    name='WinHide',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 无控制台窗口
    icon='assets/WinHide2.ico',  # 应用图标
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='WinHide',
)
