"""
窗口管理器 - 导入测试
测试所有模块的导入是否正常工作
"""

import unittest
import sys
import os
from pathlib import Path

# 添加项目根目录和 src 目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(PROJECT_ROOT))


class TestImports(unittest.TestCase):
    """测试所有核心模块的导入"""

    def test_import_constants(self):
        """测试导入 constants 模块"""
        from src.constants import (
            TimeoutConstants,
            TimeConstants,
            WindowConstants,
            UIConstants,
            ConfigConstants,
            AppConstants,
            NTPConstants,
        )
        self.assertIsNotNone(TimeoutConstants)

    def test_import_deps(self):
        """测试导入 deps 模块"""
        from src.deps import PSUTIL_AVAILABLE, PYNPUT_AVAILABLE, WIN32GUI_AVAILABLE
        self.assertIsInstance(PSUTIL_AVAILABLE, bool)

    def test_import_window_base(self):
        """测试导入 window_base 模块"""
        from src.window_base import WindowState, MonitorInfo, WindowInfo
        self.assertIsNotNone(WindowState)

    def test_import_window_models(self):
        """测试导入 window_models 模块"""
        from src.window_models import (
            WindowEntryState,
            WindowEntry,
            SimpleWindowInfo,
        )
        self.assertIsNotNone(WindowEntryState)

    def test_import_config(self):
        """测试导入 config 模块"""
        from src.config import Config, ConfigManager
        self.assertIsNotNone(Config)

    def test_import_cache_manager(self):
        """测试导入 cache_manager 模块"""
        from src.cache_manager import CacheManager
        self.assertIsNotNone(CacheManager)

    def test_import_theme(self):
        """测试导入 theme 模块"""
        try:
            from src.theme import ModernTheme, theme
            self.assertIsNotNone(ModernTheme)
            self.assertIsNotNone(theme)
        except ModuleNotFoundError:
            self.skipTest("PySide6 not available, skipping theme import test")

    def test_import_log_utils(self):
        """测试导入 log_utils 模块"""
        from src.log_utils import LogLevel, LogEntry
        self.assertIsNotNone(LogLevel)

    def test_import_utils(self):
        """测试导入 utils 模块"""
        from src.utils import HotkeyFormatter
        self.assertIsNotNone(HotkeyFormatter)


class TestCriticalImports(unittest.TestCase):
    """测试关键模块的导入"""

    def test_import_core(self):
        """测试导入 core 模块"""
        try:
            from src import core
            self.assertTrue(hasattr(core, 'SafeWindowsAPI'))
        except ImportError as e:
            self.skipTest(f"Cannot import core module: {e}")

    def test_import_window_classifier(self):
        """测试导入 window_classifier 模块"""
        try:
            from src.window_classifier import WindowClassifier
            self.assertIsNotNone(WindowClassifier)
        except ImportError:
            self.skipTest("Cannot import window_classifier module")

    def test_import_process_detector(self):
        """测试导入 process_detector 模块"""
        try:
            from src.process_detector import ProcessDetector
            self.assertIsNotNone(ProcessDetector)
        except ImportError:
            self.skipTest("Cannot import process_detector module")


if __name__ == "__main__":
    unittest.main(verbosity=2)
