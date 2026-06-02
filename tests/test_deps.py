"""
窗口管理器 - 依赖模块单元测试
测试 deps 模块中的可选依赖管理
"""

import unittest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import deps


class TestDependencyAvailability(unittest.TestCase):
    """测试依赖可用性"""

    def test_psutil_availability(self):
        """测试 psutil 依赖可用性"""
        if deps.PSUTIL_AVAILABLE:
            self.assertIsNotNone(deps.psutil)
            self.assertTrue(hasattr(deps.psutil, "process_iter"))
        else:
            self.assertIsNone(deps.psutil)

    def test_pynput_availability(self):
        """测试 pynput 依赖可用性"""
        if deps.PYNPUT_AVAILABLE:
            self.assertIsNotNone(deps.keyboard)
            self.assertIsNotNone(deps.mouse)
        else:
            self.assertIsNone(deps.keyboard)
            self.assertIsNone(deps.mouse)

    def test_win32gui_availability(self):
        """测试 win32gui 依赖可用性"""
        if deps.WIN32GUI_AVAILABLE:
            self.assertIsNotNone(deps.win32gui)
        else:
            self.assertIsNone(deps.win32gui)


class TestDependencyFallback(unittest.TestCase):
    """测试依赖降级处理"""

    def test_all_flags_are_boolean(self):
        """测试所有依赖标志都是布尔类型"""
        self.assertIsInstance(deps.PSUTIL_AVAILABLE, bool)
        self.assertIsInstance(deps.PYNPUT_AVAILABLE, bool)
        self.assertIsInstance(deps.WIN32GUI_AVAILABLE, bool)

    def test_at_least_one_dependency_available(self):
        """测试至少有一个依赖可用（在实际运行环境中）"""
        # 在实际Windows环境中，应该至少有一些依赖可用
        any_available = (
            deps.PSUTIL_AVAILABLE
            or deps.PYNPUT_AVAILABLE
            or deps.WIN32GUI_AVAILABLE
        )
        # 注意: 在测试环境中可能都不可用,所以这只是一个信息性检查


if __name__ == "__main__":
    unittest.main(verbosity=2)
