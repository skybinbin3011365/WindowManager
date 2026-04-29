# -*- mode: python ; coding: utf-8 -*-
"""
统一的 PyInstaller 配置文件
通过命令行参数 --console 控制是否包含控制台窗口

使用方法：
1. 不带控制台窗口（发布版本）：pyinstaller WinHide.spec
2. 带控制台窗口（调试版本）：pyinstaller WinHide.spec --console
"""

import os
import sys
from pathlib import Path

block_cipher = None

# 获取项目根目录（兼容 PyInstaller 环境）
if getattr(sys, 'frozen', False):
    # 打包环境：从可执行文件目录获取
    project_root = Path(sys.executable).parent.resolve()
else:
    # 开发环境：从当前工作目录获取
    project_root = Path.cwd().resolve()

# 检查命令行参数，判断是否需要控制台窗口
console_mode = False  # 发布模式：默认不显示控制台
for arg in sys.argv:
    if arg == '--console':
        console_mode = True
        break

a = Analysis(
    ['run_spec.py'],  # 使用打包入口脚本
    pathex=[str(project_root), str(project_root / 'src')],
    binaries=[],
    datas=[
        ('config/config.json', 'config'),
        ('assets/WinHide2.png', 'assets'),
        ('assets/WinHide2.ico', 'assets'),
    ],
    hiddenimports=[
        # PySide6 核心模块
        'PySide6',
        'PySide6.QtCore',
        'PySide6.QtWidgets',
        'PySide6.QtGui',
        'PySide6.QtNetwork',
        'PySide6.QtXml',
        'shiboken6',
        # pynput 模块
        'pynput',
        'pynput.keyboard',
        'pynput.mouse',
        'pynput._util',
        'pynput._util.win32',
        # 系统模块
        'psutil',
        'psutil._common',
        'psutil._compat',
        'psutil._pswindows',
        'win32api',
        'win32con',
        'win32gui',
        'win32process',
        'win32com',
        'win32com.shell',
        'win32security',
        'pywintypes',
        # 项目模块
        'ui',
        'ui_main',
        'ui_settings',
        'ui_about',
        'manager',
        'core',
        'hotkey_manager',
        'config',
        'time_sync',
        'constants',
        'utils',
        'theme',
        'app',
        'window_classifier',
        'window_models',
        'hotkey_recorder',
        'hotkey_recorder_core',
        'ui_whitelist',
        'widgets',
        'window_base',  # 新增的基础类型模块
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'test',
        'unittest',
        'doctest',
        'pdb',
        'pydoc',
        'lib2to3',
        'pip',
        'setuptools',
        'wheel',
        'black',
        'flake8',
        'mypy',
        'pytest',
        # 排除不需要的 Qt 模块
        'PySide6.Qt3DAnimation',
        'PySide6.Qt3DCore',
        'PySide6.Qt3DExtras',
        'PySide6.Qt3DInput',
        'PySide6.Qt3DLogic',
        'PySide6.Qt3DRender',
        'PySide6.QtBluetooth',
        'PySide6.QtCharts',
        'PySide6.QtConcurrent',
        'PySide6.QtDBus',
        'PySide6.QtDesigner',
        'PySide6.QtGraphs',
        'PySide6.QtHelp',
        'PySide6.QtLocation',
        'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets',
        'PySide6.QtNetworkAuth',
        'PySide6.QtNfc',
        'PySide6.QtOpenGL',
        'PySide6.QtOpenGLWidgets',
        'PySide6.QtPdf',
        'PySide6.QtPdfWidgets',
        'PySide6.QtPositioning',
        'PySide6.QtQml',
        'PySide6.QtQuick',
        'PySide6.QtQuick3D',
        'PySide6.QtQuickControls2',
        'PySide6.QtQuickEffects',
        'PySide6.QtRemoteObjects',
        'PySide6.QtScxml',
        'PySide6.QtSensors',
        'PySide6.QtSerialBus',
        'PySide6.QtSerialPort',
        'PySide6.QtSpatialAudio',
        'PySide6.QtSql',
        'PySide6.QtStateMachine',
        'PySide6.QtTest',
        'PySide6.QtTextToSpeech',
        'PySide6.QtWebChannel',
        'PySide6.QtWebEngine',
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineQuick',
        'PySide6.QtWebSockets',
        'PySide6.QtWebView',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exename = 'WinHide'
collect_name = 'WinHide' if not console_mode else 'WinHide_Debug'

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=exename,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=console_mode,  # 根据命令行参数决定是否显示控制台
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / 'assets' / 'WinHide2.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=collect_name,
    debug=False,
    optimize=2,
)