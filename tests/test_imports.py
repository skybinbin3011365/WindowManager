import sys
import traceback

# 添加当前目录到路径
sys.path.insert(0, ".")

try:
    print("测试导入模块...")
    import ui

    print("✓ 导入 ui 成功")
    import manager

    print("✓ 导入 manager 成功")
    import constants

    print("✓ 导入 constants 成功")
    import utils

    print("✓ 导入 utils 成功")
    import config

    print("✓ 导入 config 成功")
    import time_sync

    print("✓ 导入 time_sync 成功")
    print("所有模块导入成功！")
except Exception as e:
    print(f"错误: {e}")
    print("详细错误信息:")
    traceback.print_exc()
