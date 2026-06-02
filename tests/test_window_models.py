"""
窗口管理器 - 窗口数据模型单元测试
测试 window_models 模块中的数据类
"""

import unittest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.window_models import (
    WindowEntryState,
    WindowEntry,
    SimpleWindowInfo,
)


class TestWindowEntryState(unittest.TestCase):
    """测试 WindowEntryState 枚举"""

    def test_window_entry_state_values(self):
        """测试 WindowEntryState 所有值"""
        self.assertEqual(WindowEntryState.VISIBLE.value, "visible")
        self.assertEqual(WindowEntryState.HIDDEN.value, "hidden")
        self.assertEqual(WindowEntryState.INVALID.value, "invalid")

    def test_window_entry_state_count(self):
        """测试 WindowEntryState 枚举数量"""
        states = list(WindowEntryState)
        self.assertEqual(len(states), 3)


class TestWindowEntry(unittest.TestCase):
    """测试 WindowEntry 数据类"""

    def test_window_entry_creation(self):
        """测试 WindowEntry 创建"""
        entry = WindowEntry(
            process_name="chrome.exe",
            title="Google Chrome",
            hwnd=12345,
            state=WindowEntryState.VISIBLE,
            source="manual"
        )
        self.assertEqual(entry.process_name, "chrome.exe")
        self.assertEqual(entry.title, "Google Chrome")
        self.assertEqual(entry.hwnd, 12345)
        self.assertEqual(entry.state, WindowEntryState.VISIBLE)
        self.assertEqual(entry.source, "manual")

    def test_window_entry_defaults(self):
        """测试 WindowEntry 默认值"""
        entry = WindowEntry(process_name="test.exe", title="Test Window")
        self.assertIsNone(entry.hwnd)
        self.assertEqual(entry.state, WindowEntryState.INVALID)
        self.assertEqual(entry.source, "manual")

class TestSimpleWindowInfo(unittest.TestCase):
    """测试 SimpleWindowInfo 数据类"""

    def test_simple_window_info_creation(self):
        """测试 SimpleWindowInfo 创建"""
        info = SimpleWindowInfo(
            hwnd=12345,
            title="Test Window",
            class_name="TestClass",
            pid=1000,
            process_name="test.exe",
            is_visible=True,
            is_taskbar=True
        )
        self.assertEqual(info.hwnd, 12345)
        self.assertEqual(info.title, "Test Window")
        self.assertEqual(info.class_name, "TestClass")
        self.assertEqual(info.pid, 1000)
        self.assertEqual(info.process_name, "test.exe")
        self.assertTrue(info.is_visible)
        self.assertTrue(info.is_taskbar)

    def test_simple_window_info_defaults(self):
        """测试 SimpleWindowInfo 默认值"""
        info = SimpleWindowInfo(
            hwnd=0,
            title="",
            class_name="",
            pid=0,
            process_name="",
            is_visible=False
        )
        self.assertFalse(info.is_taskbar)

    def test_is_taskmanager_app_true(self):
        """测试 is_taskmanager_app - 符合条件的窗口"""
        info = SimpleWindowInfo(
            hwnd=12345,
            title="Notepad",
            class_name="Notepad",
            pid=1000,
            process_name="notepad.exe",
            is_visible=True,
            is_taskbar=True
        )
        self.assertTrue(info.is_taskmanager_app())

    def test_is_taskmanager_app_invisible(self):
        """测试 is_taskmanager_app - 不可见窗口"""
        info = SimpleWindowInfo(
            hwnd=12345,
            title="Notepad",
            class_name="Notepad",
            pid=1000,
            process_name="notepad.exe",
            is_visible=False,
            is_taskbar=True
        )
        self.assertFalse(info.is_taskmanager_app())

    def test_is_taskmanager_app_no_title(self):
        """测试 is_taskmanager_app - 无标题窗口"""
        info = SimpleWindowInfo(
            hwnd=12345,
            title="",
            class_name="Notepad",
            pid=1000,
            process_name="notepad.exe",
            is_visible=True,
            is_taskbar=True
        )
        self.assertFalse(info.is_taskmanager_app())


if __name__ == "__main__":
    unittest.main(verbosity=2)
