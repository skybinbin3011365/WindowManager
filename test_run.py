import sys
import os

# 添加 src 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# 测试导入
try:
    print("测试导入模块...")
    from ui import AppWindow
    from manager import WindowManager
    from constants import AppConstants
    from utils import setup_logging, is_admin
    from config import ConfigManager
    print("所有模块导入成功！")

    # 测试配置管理器
    print("\n测试配置管理器...")
    config_manager = ConfigManager()
    config = config_manager.load()
    print(f"配置加载成功: {config.version}")

    # 测试窗口管理器
    print("\n测试窗口管理器...")
    window_manager = WindowManager()
    print("窗口管理器创建成功！")

    # 测试 QApplication
    print("\n测试 QApplication...")
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    print("QApplication 创建成功！")

    print("\n所有测试通过！程序可以正常启动。")

except Exception as e:
    import traceback
    print(f"\n错误: {e}")
    traceback.print_exc()
