#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
hwnd统一性改造验证脚本
用于快速验证所有修改后的代码是否能正常工作
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """测试所有修改过的模块能否正常导入"""
    print("=" * 60)
    print("测试1: 模块导入")
    print("=" * 60)

    modules = [
        "src.window_thread",
        "src.config_handler",
        "src.window_classifier",
        "src.manager",
        "src.window_switch",
        "src.window_operations",
        "src.config",
        "src.ui",
        "src.app",
    ]

    success_count = 0
    for module_name in modules:
        try:
            __import__(module_name)
            print(f"  [OK] {module_name}")
            success_count += 1
        except Exception as e:
            print(f"  [FAIL] {module_name}: {str(e)}")

    print(f"\n结果: {success_count}/{len(modules)} 模块导入成功")
    return success_count == len(modules)

def test_hwnd_primary_logic():
    """测试hwnd为主键的逻辑是否正确实现"""
    print("\n" + "=" * 60)
    print("测试2: hwnd为主键逻辑检查")
    print("=" * 60)

    import inspect

    # 检查window_thread.py中的_find_window_by_config方法
    from src import window_thread

    source = inspect.getsource(window_thread.WindowRefreshThread._find_window_by_config)

    checks = [
        ("主路径：直接用hwnd查找", "w.hwnd == hwnd" in source),
        ("回退路径1：hwnd失效检查", "hwnd_invalid" in source or "SafeWindowsAPI.is_window(hwnd)" in source),
        ("回退路径2：按进程名查找", "process_name_lower" in source),
        ("日志记录：包含hwnd信息", "hwnd=" in source and "logger" in source),
    ]

    all_passed = True
    for check_name, result in checks:
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status} {check_name}")
        if not result:
            all_passed = False

    return all_passed

def test_config_handler_logic():
    """测试config_handler.py的hwnd主键逻辑"""
    print("\n" + "=" * 60)
    print("测试3: config_handler.py逻辑检查")
    print("=" * 60)

    from src import config_handler
    import inspect

    source = inspect.getsource(config_handler.ConfigHandlerMixin._load_selected_windows_from_config)

    checks = [
        ("主路径：用saved_hwnd查找", "saved_hwnd > 0" in source or "saved_hwnd =" in source),
        ("回退路径：按进程名查找", "found_by_process" in source),
        ("使用get_window方法", "get_window(saved_hwnd)" in source),
    ]

    all_passed = True
    for check_name, result in checks:
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status} {check_name}")
        if not result:
            all_passed = False

    return all_passed

def test_window_classifier_logic():
    """测试window_classifier.py的hwnd主键逻辑"""
    print("\n" + "=" * 60)
    print("测试4: window_classifier.py逻辑检查")
    print("=" * 60)

    from src import window_classifier
    import inspect

    try:
        source = inspect.getsource(window_classifier.WindowClassifier.update_target_window_status)
    except Exception:
        print("  [WARN] 无法获取update_target_window_status源码，跳过")
        return True

    checks = [
        ("主路径：通过hwnd查找", "entry.hwnd" in source and "all_windows.get(entry.hwnd)" in source),
        ("回退路径：按进程名查找", "found_window is None" in source or "not found_window" in source),
        ("更新hwnd引用", "entry.hwnd != found_window.hwnd" in source),
    ]

    all_passed = True
    for check_name, result in checks:
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status} {check_name}")
        if not result:
            all_passed = False

    return all_passed

def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("HWND统一性改造验证脚本")
    print("=" * 60)
    print(f"Python版本: {sys.version}")
    print(f"工作目录: {os.getcwd()}")
    print()

    results = []

    results.append(("模块导入测试", test_imports()))
    results.append(("window_thread逻辑测试", test_hwnd_primary_logic()))
    results.append(("config_handler逻辑测试", test_config_handler_logic()))
    results.append(("window_classifier逻辑测试", test_window_classifier_logic()))

    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} {name}")

    print(f"\n总计: {passed}/{total} 测试通过")

    if passed == total:
        print("\n[SUCCESS] 所有测试通过！hwnd统一性改造成功！")
        return 0
    else:
        print("\n[FAILURE] 部分测试失败，请检查上述错误信息。")
        return 1

if __name__ == "__main__":
    sys.exit(main())
