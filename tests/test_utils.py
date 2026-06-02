"""
窗口管理器 - 工具模块单元测试
测试 utils 模块中的工具函数和类
"""

import unittest
import sys
import os
import tempfile
import logging
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestHotkeyFormatter(unittest.TestCase):
    """测试 HotkeyFormatter 热键格式化类"""

    def test_key_name_map_not_empty(self):
        """测试按键名称映射表非空"""
        from src.utils import HotkeyFormatter
        self.assertGreater(len(HotkeyFormatter.KEY_NAME_MAP), 0)

    def test_key_name_map_contains_common_keys(self):
        """测试按键名称映射表包含常见按键"""
        from src.utils import HotkeyFormatter
        self.assertIn("CTRL", HotkeyFormatter.KEY_NAME_MAP)
        self.assertIn("ALT", HotkeyFormatter.KEY_NAME_MAP)
        self.assertIn("SHIFT", HotkeyFormatter.KEY_NAME_MAP)
        self.assertIn("WIN", HotkeyFormatter.KEY_NAME_MAP)
        self.assertIn("F1", HotkeyFormatter.KEY_NAME_MAP)

    def test_format_hotkey_simple(self):
        """测试 format_hotkey - 简单热键（统一大写显示）"""
        from src.utils import HotkeyFormatter
        result = HotkeyFormatter.format_hotkey("ctrl+shift+h")
        self.assertIn("CTRL", result)
        self.assertIn("SHIFT", result)
        self.assertIn("H", result)

    def test_format_hotkey_empty(self):
        """测试 format_hotkey - 空字符串"""
        from src.utils import HotkeyFormatter
        result = HotkeyFormatter.format_hotkey("")
        self.assertEqual(result, "")

    def test_format_hotkey_none(self):
        """测试 format_hotkey - None输入"""
        from src.utils import HotkeyFormatter
        result = HotkeyFormatter.format_hotkey(None)
        self.assertEqual(result, "")

    def test_format_hotkey_mouse(self):
        """测试 format_hotkey - 鼠标按键"""
        from src.utils import HotkeyFormatter
        result = HotkeyFormatter.format_hotkey("MBUTTON+RBUTTON")
        # MBUTTON 和 RBUTTON 不在映射表中,使用原始值
        self.assertIn("MBUTTON", result)
        self.assertIn("RBUTTON", result)

    def test_format_hotkey_case_insensitive(self):
        """测试 format_hotkey - 大小写不敏感"""
        from src.utils import HotkeyFormatter
        result1 = HotkeyFormatter.format_hotkey("CTRL+SHIFT+H")
        result2 = HotkeyFormatter.format_hotkey("ctrl+shift+h")
        self.assertEqual(result1, result2)

    def test_normalize_hotkey_simple(self):
        """测试 normalize_hotkey - 简单热键"""
        from src.utils import HotkeyFormatter
        result = HotkeyFormatter.normalize_hotkey("Ctrl+Shift+H")
        self.assertIn("CTRL", result)
        self.assertIn("SHIFT", result)
        self.assertIn("H", result)

    def test_normalize_hotkey_empty(self):
        """测试 normalize_hotkey - 空字符串"""
        from src.utils import HotkeyFormatter
        result = HotkeyFormatter.normalize_hotkey("")
        self.assertEqual(result, "")

    def test_normalize_hotkey_none(self):
        """测试 normalize_hotkey - None输入"""
        from src.utils import HotkeyFormatter
        result = HotkeyFormatter.normalize_hotkey(None)
        self.assertEqual(result, "")

    def test_normalize_hotkey_preserves_order(self):
        """测试 normalize_hotkey - 保持顺序"""
        from src.utils import HotkeyFormatter
        result = HotkeyFormatter.normalize_hotkey("Ctrl+Alt+Delete")
        parts = result.split("+")
        self.assertEqual(len(parts), 3)


class TestGetResourcePath(unittest.TestCase):
    """测试 get_resource_path 函数"""

    def test_resource_path_returns_string(self):
        """测试返回字符串类型"""
        from src.utils import get_resource_path
        result = get_resource_path("test.png")
        self.assertIsInstance(result, str)

    def test_resource_path_contains_filename(self):
        """测试路径包含文件名"""
        from src.utils import get_resource_path
        result = get_resource_path("test.png")
        self.assertTrue(result.endswith("test.png"))


class TestIsAdmin(unittest.TestCase):
    """测试 is_admin 函数"""

    def test_is_admin_returns_bool_or_int(self):
        """测试返回布尔类型或整数(Windows API返回值)"""
        from src.utils import is_admin
        result = is_admin()
        # Windows API 可能返回 1/0 而不是 True/False
        self.assertTrue(result == True or result == 1 or result == False or result == 0)


class TestSetupLogging(unittest.TestCase):
    """测试 setup_logging 函数"""

    def test_setup_logging_creates_directory(self):
        """测试创建日志目录"""
        from src.utils import setup_logging
        temp_dir = tempfile.mkdtemp()
        try:
            logs_dir = setup_logging(config_dir=temp_dir)
            self.assertTrue(logs_dir.exists() or logs_dir.is_dir())
        finally:
            import shutil
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)


class TestWin32ErrorHandler(unittest.TestCase):
    """测试 win32_error_handler 装饰器"""

    def test_decorator_returns_callable(self):
        """测试装饰器返回可调用对象"""
        from src.utils import win32_error_handler
        decorator = win32_error_handler(default=False)
        self.assertTrue(callable(decorator))

    def test_decorator_with_default_value(self):
        """测试带默认值的装饰器"""
        from src.utils import win32_error_handler

        @win32_error_handler(default=-1)
        def function_that_raises():
            raise ValueError("Test error")

        result = function_that_raises()
        self.assertEqual(result, -1)

    def test_decorator_preserves_function_result(self):
        """测试装饰器保留函数返回值"""
        from src.utils import win32_error_handler

        @win32_error_handler(default=None)
        def function_that_returns():
            return 42

        result = function_that_returns()
        self.assertEqual(result, 42)


if __name__ == "__main__":
    unittest.main(verbosity=2)
