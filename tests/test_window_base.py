"""
窗口管理器 - 单元测试
测试 window_base 模块中的基础类型
"""

from src.window_base import WindowState, MonitorInfo, WindowInfo
import unittest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestWindowState(unittest.TestCase):
    """测试 WindowState 枚举"""

    def test_window_state_values(self):
        """测试 WindowState 枚举的所有值"""
        self.assertEqual(WindowState.NORMAL.value, 1)
        self.assertEqual(WindowState.MINIMIZED.value, 2)
        self.assertEqual(WindowState.MAXIMIZED.value, 3)
        self.assertEqual(WindowState.HIDDEN.value, 4)

    def test_window_state_count(self):
        """测试 WindowState 枚举的数量"""
        states = list(WindowState)
        self.assertEqual(len(states), 4)


class TestMonitorInfo(unittest.TestCase):
    """测试 MonitorInfo 数据类"""

    def test_monitor_info_creation(self):
        """测试 MonitorInfo 创建"""
        monitor = MonitorInfo(
            monitor_id=1,
            left=0,
            top=0,
            right=1920,
            bottom=1080,
            is_primary=True
        )
        self.assertEqual(monitor.monitor_id, 1)
        self.assertEqual(monitor.left, 0)
        self.assertEqual(monitor.top, 0)
        self.assertEqual(monitor.right, 1920)
        self.assertEqual(monitor.bottom, 1080)
        self.assertTrue(monitor.is_primary)

    def test_monitor_info_defaults(self):
        """测试 MonitorInfo 默认值"""
        monitor = MonitorInfo(
            monitor_id=0,
            left=0,
            top=0,
            right=0,
            bottom=0
        )
        self.assertFalse(monitor.is_primary)


class TestWindowInfo(unittest.TestCase):
    """测试 WindowInfo 数据类"""

    def test_window_info_creation(self):
        """测试 WindowInfo 创建"""
        window = WindowInfo(
            hwnd=12345,
            title="Test Window",
            class_name="TestClass",
            pid=1000,
            state=WindowState.NORMAL,
            is_visible=True,
            process_name="test.exe",
            is_foreground=True
        )
        self.assertEqual(window.hwnd, 12345)
        self.assertEqual(window.title, "Test Window")
        self.assertEqual(window.class_name, "TestClass")
        self.assertEqual(window.pid, 1000)
        self.assertEqual(window.state, WindowState.NORMAL)
        self.assertTrue(window.is_visible)
        self.assertEqual(window.process_name, "test.exe")
        self.assertTrue(window.is_foreground)

    def test_window_info_defaults(self):
        """测试 WindowInfo 默认值"""
        window = WindowInfo(hwnd=0)
        self.assertEqual(window.title, "")
        self.assertEqual(window.class_name, "")
        self.assertEqual(window.pid, 0)
        self.assertEqual(window.state, WindowState.NORMAL)
        self.assertTrue(window.is_visible)
        self.assertEqual(window.process_name, "")
        self.assertFalse(window.is_foreground)
        self.assertIsNone(window.monitor_id)
        self.assertEqual(window.monitor_name, "")
        self.assertIsNone(window.is_taskbar)

    def test_get_display_title_with_process(self):
        """测试 get_display_title 方法 - 有进程名的情况"""
        window = WindowInfo(
            hwnd=12345,
            title="Test Window",
            process_name="test.exe"
        )
        display_title = window.get_display_title()
        self.assertEqual(display_title, "test.exe: Test Window")

    def test_get_display_title_without_process(self):
        """测试 get_display_title 方法 - 没有进程名的情况"""
        window = WindowInfo(
            hwnd=12345,
            title="Test Window",
            process_name=""
        )
        display_title = window.get_display_title()
        self.assertEqual(display_title, "Test Window")

    def test_window_info_state_transitions(self):
        """测试 WindowInfo 状态转换"""
        window = WindowInfo(hwnd=12345, state=WindowState.NORMAL)

        # 转换为最小化状态
        window.state = WindowState.MINIMIZED
        self.assertEqual(window.state, WindowState.MINIMIZED)

        # 转换为最大化状态
        window.state = WindowState.MAXIMIZED
        self.assertEqual(window.state, WindowState.MAXIMIZED)

        # 转换为隐藏状态
        window.state = WindowState.HIDDEN
        window.is_visible = False
        self.assertEqual(window.state, WindowState.HIDDEN)
        self.assertFalse(window.is_visible)


class TestWindowInfoVisibility(unittest.TestCase):
    """测试 WindowInfo 可见性相关功能"""

    def test_visible_window(self):
        """测试可见窗口"""
        window = WindowInfo(
            hwnd=12345,
            title="Visible Window",
            state=WindowState.NORMAL,
            is_visible=True
        )
        self.assertTrue(window.is_visible)
        self.assertEqual(window.state, WindowState.NORMAL)

    def test_hidden_window(self):
        """测试隐藏窗口"""
        window = WindowInfo(
            hwnd=12345,
            title="Hidden Window",
            state=WindowState.HIDDEN,
            is_visible=False
        )
        self.assertFalse(window.is_visible)
        self.assertEqual(window.state, WindowState.HIDDEN)

    def test_minimized_window(self):
        """测试最小化窗口"""
        window = WindowInfo(
            hwnd=12345,
            title="Minimized Window",
            state=WindowState.MINIMIZED,
            is_visible=True
        )
        self.assertTrue(window.is_visible)
        self.assertEqual(window.state, WindowState.MINIMIZED)


if __name__ == "__main__":
    # 运行测试
    unittest.main(verbosity=2)
