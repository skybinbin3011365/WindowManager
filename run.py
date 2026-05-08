#!/usr/bin/env python3
"""开发环境入口脚本

将 src 目录加入 sys.path 后直接运行 app 模块。
"""
import sys
import os
import runpy

project_root = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(project_root, 'src')

# 将 src 目录加入路径，使绝对导入生效
sys.path.insert(0, src_dir)

# 直接运行 app 模块
runpy.run_module('app', run_name='__main__')
