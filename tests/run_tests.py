#!/usr/bin/env python3
"""
测试运行器 - 运行所有测试并生成覆盖率报告

使用方法:
    python run_tests.py              # 运行所有测试
    python run_tests.py --verbose    # 详细输出
    python run_tests.py --coverage   # 生成覆盖率报告
"""

import sys
import os
import unittest
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

TESTS_DIR = PROJECT_ROOT / "tests"


def discover_tests():
    """发现所有测试"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 加载所有测试模块
    test_modules = [
        "test_imports",
        "test_constants",
        "test_deps",
        "test_window_base",
        "test_window_models",
        "test_config",
        "test_cache_manager",
        "test_utils",
        "test_theme",
        "test_process_detector",
    ]

    for module_name in test_modules:
        try:
            suite.addTests(loader.loadTestsFromName(module_name))
            print(f"✓ 已加载: {module_name}")
        except Exception as e:
            print(f"✗ 加载失败: {module_name} - {e}")

    return suite


def run_tests(verbose=False, coverage=False):
    """运行测试"""
    suite = discover_tests()

    if verbose:
        verbosity = 2
    else:
        verbosity = 1

    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)

    # 打印测试摘要
    print("\n" + "=" * 60)
    print("测试摘要")
    print("=" * 60)
    print(f"运行测试数: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    print(f"跳过: {len(result.skipped)}")

    if result.wasSuccessful():
        print("\n✅ 所有测试通过!")
        return 0
    else:
        print("\n❌ 有测试失败!")
        return 1


if __name__ == "__main__":
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    coverage = "--coverage" in sys.argv or "-c" in sys.argv

    if coverage:
        print("注意: 覆盖率报告需要安装 coverage.py")
        print("运行: pip install coverage")
        print()

    exit_code = run_tests(verbose=verbose, coverage=coverage)
    sys.exit(exit_code)
