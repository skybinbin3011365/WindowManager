# run_spec.py
"""
打包专用入口脚本
用于 PyInstaller 打包时作为入口点
"""
import sys
from pathlib import Path

# 获取脚本所在目录（打包后是 dist/WinHide_WithConsole 目录）
SCRIPT_DIR = Path(__file__).parent.absolute()

# 添加 src 目录到 Python 路径
src_path = SCRIPT_DIR / "src"
if src_path.exists() and str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# 导入并运行主程序
if __name__ == "__main__":
    from app import main

    sys.exit(main())
