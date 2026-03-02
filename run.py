#!/usr/bin/env python3
"""开发环境入口脚本"""
import sys
import os
import runpy

project_root = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(project_root, 'src')

sys.path.insert(0, src_dir)

# 创建虚拟包结构支持相对导入
import types
windowmanager = types.ModuleType('windowmanager')
windowmanager.__path__ = [src_dir]
sys.modules['windowmanager'] = windowmanager

windowmanager_src = types.ModuleType('windowmanager.src')
windowmanager_src.__path__ = [src_dir]
sys.modules['windowmanager.src'] = windowmanager_src

# 运行应用
runpy.run_module('windowmanager.src.app', run_name='__main__')
