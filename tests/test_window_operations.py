"""
窗口管理器 - 窗口操作模块单元测试
测试 window_operations 模块中的 WindowOperator 类

注意: 由于 Python 3.12 在某些 Windows 环境下 import unittest.mock
会触发 asyncio 导入错误 (OSError: [WinError 10038])，本测试文件
不使用 unittest.mock，而是通过直接构造测试数据来验证逻辑。
"""

import unittest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestWindowOperatorInitialization(unittest.TestCase):
    """测试 WindowOperator 初始化"""

    def test_window_operator_initialization(self):
        """测试 WindowOperator 基本初始化"""
        try:
            from src.window_operations import WindowOperator
            operator = WindowOperator()
            self.assertIsNotNone(operator._lock)
            self.assertIsInstance(operator._windows, dict)
            self.assertIsInstance(operator._hidden_windows, dict)
            self.assertIsInstance(operator._software_hidden_windows, set)
            self.assertIn(operator._is_admin, (0, 1, True, False))
        except ImportError:
            self.skipTest("Cannot import WindowOperator in test environment")

    def test_set_data_stores(self):
        """测试设置数据存储引用"""
        try:
            from src.window_operations import WindowOperator
            from src.window_base import WindowInfo, WindowState

            operator = WindowOperator()
            windows = {1: WindowInfo(hwnd=1)}
            hidden_windows = {2: WindowInfo(hwnd=2, state=WindowState.HIDDEN)}
            sw_set = {2}

            operator.set_data_stores(
                windows=windows,
                hidden_windows=hidden_windows,
                software_hidden_windows=sw_set,
            )

            self.assertEqual(operator._windows, windows)
            self.assertEqual(operator._hidden_windows, hidden_windows)
            self.assertEqual(operator._software_hidden_windows, sw_set)
        except ImportError:
            self.skipTest("Cannot import WindowOperator in test environment")


class TestWindowOperatorShowLogic(unittest.TestCase):
    """测试 show_window 的逻辑分支（不依赖 mock）"""

    def test_show_window_not_in_hidden(self):
        """测试显示不在隐藏列表中的窗口应返回 False"""
        try:
            from src.window_operations import WindowOperator

            operator = WindowOperator()
            operator.set_data_stores(
                windows={},
                hidden_windows={},
                software_hidden_windows=set(),
            )
            result = operator.show_window(99999)
            self.assertFalse(result)
        except ImportError:
            self.skipTest("Cannot import WindowOperator in test environment")


class TestWindowOperatorBatchOperations(unittest.TestCase):
    """测试批量操作方法"""

    def test_show_selected_hidden_windows_empty(self):
        """测试显示空的选中列表"""
        try:
            from src.window_operations import WindowOperator
            operator = WindowOperator()
            operator.set_data_stores({}, {}, set())
            count = operator.show_selected_hidden_windows([])
            self.assertEqual(count, 0)
        except ImportError:
            self.skipTest("Import error")

    def test_show_all_hidden_windows_empty(self):
        """测试显示所有隐藏窗口（空列表情况）"""
        try:
            from src.window_operations import WindowOperator
            operator = WindowOperator()
            operator.set_data_stores({}, {}, set())
            count = operator.show_all_hidden_windows()
            self.assertEqual(count, 0)
        except ImportError:
            self.skipTest("Import error")


class TestSanitizeTitle(unittest.TestCase):
    """测试 sanitize_title 脱敏函数"""

    def test_sanitize_title_short(self):
        """测试短标题不截断"""
        from src.utils import sanitize_title
        result = sanitize_title("Hello World")
        self.assertEqual(result, "Hello World")

    def test_sanitize_title_long(self):
        """测试长标题截断"""
        from src.utils import sanitize_title
        long_title = "A" * 50
        result = sanitize_title(long_title)
        self.assertEqual(len(result), 33)  # 30 + "..."
        self.assertTrue(result.endswith("..."))

    def test_sanitize_title_empty(self):
        """测试空标题"""
        from src.utils import sanitize_title
        result = sanitize_title("")
        self.assertEqual(result, "")

    def test_sanitize_title_custom_length(self):
        """测试自定义最大长度"""
        from src.utils import sanitize_title
        result = sanitize_title("Hello World", max_length=5)
        self.assertEqual(result, "Hello...")


if __name__ == "__main__":
    unittest.main(verbosity=2)
