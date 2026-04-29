import sys
import traceback

# 添加当前目录到路径
sys.path.insert(0, ".")

try:
    from app import main

    print("导入成功，正在运行 main()...")
    main()
except Exception as e:
    print(f"错误: {e}")
    print("详细错误信息:")
    traceback.print_exc()
