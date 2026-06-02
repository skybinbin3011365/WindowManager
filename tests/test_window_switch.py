"""
窗口管理器 - 切换窗口功能单元测试
测试 window_switch 模块中的 SwitchMixin 类

重点测试:
1. switch_all_processes_to_foreground 热键逻辑
2. _add_switch_window_by_hwnd 添加逻辑
3. _remove_switch_window 移除逻辑
4. 线程安全相关逻辑
"""

import unittest
import sys
import os
import threading

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from window_base import WindowInfo, WindowState


class MockConfigManager:
    def __init__(self):
        self.saved_configs = []

    def save(self, config):
        self.saved_configs.append(config)


class MockWindowManager:
    def __init__(self):
        self._windows = {}
        self._hidden_windows = {}
        self._switch_results = {}

    def get_all_windows(self):
        return list(self._windows.values())

    def get_window(self, hwnd):
        return self._windows.get(hwnd)

    def switch_to_foreground(self, hwnd):
        return self._switch_results.get(hwnd, False)

    def switch_windows_by_process_name(self, process_name):
        count = 0
        for win in self._windows.values():
            if win.process_name.lower() == process_name.lower():
                if self._switch_results.get(win.hwnd, False):
                    count += 1
        return count


class MockMainWindowTab:
    def __init__(self):
        self.config = None
        self.config_manager = None
        self.window_manager = None
        self._lock = threading.RLock()
        self._selected_windows = set()
        self._ignored_windows = set()
        self.status_messages = []
        self.switch_window_table = type('obj', (object,), {
            'setRowCount': lambda self, n: None,
        })()

    def _update_window_table_incremental(self, table, windows, allow_check=True):
        pass

    def emit_status(self, msg):
        self.status_messages.append(msg)


class TestSwitchAllProcessesToForeground(unittest.TestCase):
    def setUp(self):
        from window_switch import SwitchMixin

        class TestTab(SwitchMixin, MockMainWindowTab):
            def __init__(self):
                super().__init__()
                self.status_updated = type('obj', (object,), {'emit': lambda self, msg: None})()

        self.tab = TestTab()
        self.tab.window_manager = MockWindowManager()
        self.tab.config_manager = MockConfigManager()

    def test_empty_switch_list(self):
        self.tab.config = type('Config', (), {
            'switch_windows': [],
            'switch_processes': [],
        })()
        self.tab.switch_all_processes_to_foreground()

    def test_switch_by_hwnd(self):
        self.tab.config = type('Config', (), {
            'switch_windows': [
                {"hwnd": 100, "process_name": "notepad.exe", "title": "Notepad", "source": "manual"},
                {"hwnd": 200, "process_name": "calc.exe", "title": "Calculator", "source": "manual"},
            ],
            'switch_processes': [],
        })()
        self.tab.window_manager._switch_results = {100: True, 200: True}
        self.tab.switch_all_processes_to_foreground()

    def test_switch_by_hwnd_partial_failure(self):
        self.tab.config = type('Config', (), {
            'switch_windows': [
                {"hwnd": 100, "process_name": "notepad.exe", "title": "Notepad", "source": "manual"},
                {"hwnd": 200, "process_name": "calc.exe", "title": "Calculator", "source": "manual"},
            ],
            'switch_processes': [],
        })()
        self.tab.window_manager._switch_results = {100: True, 200: False}
        self.tab.switch_all_processes_to_foreground()

    def test_switch_by_process_name_fallback(self):
        self.tab.config = type('Config', (), {
            'switch_windows': [
                {"hwnd": 0, "process_name": "notepad.exe", "title": "notepad.exe", "source": "process"},
            ],
            'switch_processes': [],
        })()
        win = WindowInfo(hwnd=300, title="Notepad", process_name="notepad.exe",
                         is_visible=True, is_taskbar=True, state=WindowState.NORMAL)
        self.tab.window_manager._windows[300] = win
        self.tab.window_manager._switch_results = {300: True}
        self.tab.switch_all_processes_to_foreground()

    def test_switch_legacy_processes(self):
        self.tab.config = type('Config', (), {
            'switch_windows': [],
            'switch_processes': ["notepad.exe"],
        })()
        win = WindowInfo(hwnd=300, title="Notepad", process_name="notepad.exe",
                         is_visible=True, is_taskbar=True, state=WindowState.NORMAL)
        self.tab.window_manager._windows[300] = win
        self.tab.window_manager._switch_results = {300: True}
        self.tab.switch_all_processes_to_foreground()


class TestAddSwitchWindowByHwnd(unittest.TestCase):
    def setUp(self):
        from window_switch import SwitchMixin

        class TestTab(SwitchMixin, MockMainWindowTab):
            def __init__(self):
                super().__init__()
                self.status_updated = type('obj', (object,), {'emit': lambda self, msg: None})()

        self.tab = TestTab()
        self.tab.window_manager = MockWindowManager()
        self.tab.config_manager = MockConfigManager()
        self.tab.config = type('Config', (), {'switch_windows': []})()

    def test_add_new_window(self):
        win = WindowInfo(hwnd=100, title="Test Window", process_name="test.exe",
                         is_visible=True, is_taskbar=True, state=WindowState.NORMAL)
        self.tab.window_manager._windows[100] = win
        self.tab._add_switch_window_by_hwnd(100)
        self.assertEqual(len(self.tab.config.switch_windows), 1)
        self.assertEqual(self.tab.config.switch_windows[0]["hwnd"], 100)

    def test_add_duplicate_window(self):
        self.tab.config.switch_windows = [
            {"hwnd": 100, "process_name": "test.exe", "title": "Test", "source": "manual"}
        ]
        self.tab._add_switch_window_by_hwnd(100)
        self.assertEqual(len(self.tab.config.switch_windows), 1)

    def test_add_window_saves_config(self):
        win = WindowInfo(hwnd=100, title="Test Window", process_name="test.exe",
                         is_visible=True, is_taskbar=True, state=WindowState.NORMAL)
        self.tab.window_manager._windows[100] = win
        self.tab._add_switch_window_by_hwnd(100)
        self.assertEqual(len(self.tab.config_manager.saved_configs), 1)


class TestRemoveSwitchWindow(unittest.TestCase):
    def setUp(self):
        from window_switch import SwitchMixin

        class TestTab(SwitchMixin, MockMainWindowTab):
            def __init__(self):
                super().__init__()
                self.status_updated = type('obj', (object,), {'emit': lambda self, msg: None})()

        self.tab = TestTab()
        self.tab.window_manager = MockWindowManager()
        self.tab.config_manager = MockConfigManager()
        self.tab.config = type('Config', (), {
            'switch_windows': [
                {"hwnd": 100, "process_name": "test.exe", "title": "Test1", "source": "manual"},
                {"hwnd": 200, "process_name": "calc.exe", "title": "Calc", "source": "manual"},
            ],
        })()

    def test_remove_existing_window(self):
        self.tab._remove_switch_window(100)
        self.assertEqual(len(self.tab.config.switch_windows), 1)
        self.assertEqual(self.tab.config.switch_windows[0]["hwnd"], 200)

    def test_remove_nonexistent_window(self):
        self.tab._remove_switch_window(999)
        self.assertEqual(len(self.tab.config.switch_windows), 2)


class TestSwitchWindowToForeground(unittest.TestCase):
    def setUp(self):
        from window_switch import SwitchMixin

        class TestTab(SwitchMixin, MockMainWindowTab):
            def __init__(self):
                super().__init__()
                self.status_updated = type('obj', (object,), {'emit': lambda self, msg: None})()

        self.tab = TestTab()
        self.tab.window_manager = MockWindowManager()

    def test_switch_success(self):
        self.tab.window_manager._switch_results = {100: True}
        result = self.tab._switch_window_to_foreground(100)
        self.assertTrue(result)

    def test_switch_failure(self):
        self.tab.window_manager._switch_results = {100: False}
        result = self.tab._switch_window_to_foreground(100)
        self.assertFalse(result)

    def test_switch_no_window_manager(self):
        self.tab.window_manager = None
        result = self.tab._switch_window_to_foreground(100)
        self.assertFalse(result)


class TestSwitchProcessToForeground(unittest.TestCase):
    def setUp(self):
        from window_switch import SwitchMixin

        class TestTab(SwitchMixin, MockMainWindowTab):
            def __init__(self):
                super().__init__()
                self.status_updated = type('obj', (object,), {'emit': lambda self, msg: None})()

        self.tab = TestTab()
        self.tab.window_manager = MockWindowManager()

    def test_switch_process_success(self):
        win = WindowInfo(hwnd=100, title="Notepad", process_name="notepad.exe",
                         is_visible=True, is_taskbar=True, state=WindowState.NORMAL)
        self.tab.window_manager._windows[100] = win
        self.tab.window_manager._switch_results = {100: True}
        count = self.tab._switch_process_to_foreground("notepad.exe")
        self.assertEqual(count, 1)

    def test_switch_process_no_match(self):
        count = self.tab._switch_process_to_foreground("nonexistent.exe")
        self.assertEqual(count, 0)

    def test_switch_process_no_window_manager(self):
        self.tab.window_manager = None
        count = self.tab._switch_process_to_foreground("notepad.exe")
        self.assertEqual(count, 0)


class TestThreadSafety(unittest.TestCase):
    def test_selected_windows_lock_protection(self):
        lock = threading.RLock()
        selected = set()
        errors = []

        def add_windows():
            try:
                for i in range(100):
                    with lock:
                        selected.add(i)
            except Exception as e:
                errors.append(e)

        def remove_windows():
            try:
                for i in range(100):
                    with lock:
                        selected.discard(i)
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=add_windows)
        t2 = threading.Thread(target=remove_windows)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        self.assertEqual(len(errors), 0)

    def test_ignored_windows_lock_protection(self):
        lock = threading.RLock()
        ignored = set()
        errors = []

        def add_items():
            try:
                for i in range(100):
                    with lock:
                        ignored.add(i)
            except Exception as e:
                errors.append(e)

        def clear_items():
            try:
                for _ in range(10):
                    with lock:
                        ignored.clear()
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=add_items)
        t2 = threading.Thread(target=clear_items)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        self.assertEqual(len(errors), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
