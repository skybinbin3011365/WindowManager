# -*- mode: python ; coding: utf-8 -*-
"""
单文件打包配置 - 无控制台窗口
直接复制src目录内容并修复导入
"""
import sys
import os
import shutil
import re

project_root = os.getcwd()
src_dir = os.path.join(project_root, 'src')
build_dir = os.path.join(project_root, '_build')

# 清理并创建构建目录
if os.path.exists(build_dir):
    shutil.rmtree(build_dir)
os.makedirs(build_dir)

# 直接复制src目录内容
shutil.copytree(src_dir, build_dir, dirs_exist_ok=True)

# 修复_build目录中的导入 - 全部改为绝对导入
for filename in os.listdir(build_dir):
    if filename.endswith('.py'):
        file_path = os.path.join(build_dir, filename)
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 替换所有相对导入
        content = re.sub(r'^from \. import (\w+)', r'import \1', content, flags=re.MULTILINE)
        content = re.sub(r'^from \.(\w+) import', r'from \1 import', content, flags=re.MULTILINE)
        content = re.sub(r'^from \.\.(\w+) import', r'from \1 import', content, flags=re.MULTILINE)
        content = re.sub(r'^import \.(\w+)', r'import \1', content, flags=re.MULTILINE)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"Fixed: {filename}")

# 复制配置文件和图标
shutil.copy(os.path.join(project_root, 'config.json'), os.path.join(build_dir, 'config.json'))
shutil.copy(os.path.join(project_root, 'WinHide.png'), os.path.join(build_dir, 'WinHide.png'))

# 创建打包入口脚本
entry_path = os.path.join(build_dir, '__main__.py')
with open(entry_path, 'w', encoding='utf-8') as f:
    f.write('''#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import main
if __name__ == "__main__":
    main()
''')

a = Analysis(
    [entry_path],
    pathex=[build_dir],
    binaries=[],
    datas=[
        (os.path.join(build_dir, 'config.json'), '.'),
        (os.path.join(build_dir, 'files'), 'files'),
        (os.path.join(build_dir, 'WinHide.png'), '.'),
    ],
    hiddenimports=[
        'win32gui', 'win32api', 'win32con', 'win32process', 'win32security',
        'pystray', 'PIL', 'PIL.Image', 'PIL.ImageDraw',
        'tkinter', 'tkinter.ttk', 'tkinter.messagebox', 'tkinter.scrolledtext',
        'logging', 'win32', 'win32.lib', 'psutil',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='WinHide',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 无控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(project_root, 'WinHide.png'),  # 设置exe图标
)
