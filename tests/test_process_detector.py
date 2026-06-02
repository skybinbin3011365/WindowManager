"""
窗口管理器 - 进程检测模块单元测试
测试 process_detector 模块中的 ProcessDetector 类

注意: 部分功能依赖 Windows API,这些测试主要验证类的接口和逻辑
"""

import unittest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestProcessDetectorInitialization(unittest.TestCase):
    """测试 ProcessDetector 初始化"""

    def test_process_detector_initialization(self):
        """测试 ProcessDetector 初始化"""
        try:
            from src.process_detector import ProcessDetector
            detector = ProcessDetector()
            self.assertIsNotNone(detector._lock)
            self.assertEqual(detector._last_all_pids, set())
            self.assertEqual(detector._keyword_process_map, {})
            self.assertEqual(detector._process_keyword_map, {})
        except ImportError:
            self.skipTest("Cannot import ProcessDetector in test environment")

    def test_non_user_class_prefixes(self):
        """测试非用户窗口类名前缀"""
        try:
            from src.process_detector import ProcessDetector
            prefixes = ProcessDetector._NON_USER_CLASS_PREFIXES
            self.assertIsInstance(prefixes, tuple)
            self.assertGreater(len(prefixes), 0)
            self.assertIn("DirectUIHWND", prefixes)
        except ImportError:
            self.skipTest("Cannot import ProcessDetector in test environment")

    def test_update_last_pids(self):
        """测试 update_last_pids 公共方法"""
        try:
            from src.process_detector import ProcessDetector
            detector = ProcessDetector()
            test_pids = {100, 200, 300}
            detector.update_last_pids(test_pids)
            self.assertEqual(detector._last_all_pids, test_pids)
        except ImportError:
            self.skipTest("Cannot import ProcessDetector in test environment")

    def test_detect_target_windows_empty_keywords(self):
        """测试空关键字列表"""
        try:
            from src.process_detector import ProcessDetector
            detector = ProcessDetector()
            result = detector.detect_target_windows([])
            self.assertEqual(result, [])
        except ImportError:
            self.skipTest("Cannot import ProcessDetector in test environment")

    def test_detect_target_windows_none_keywords(self):
        """测试 None 关键字"""
        try:
            from src.process_detector import ProcessDetector
            detector = ProcessDetector()
            result = detector.detect_target_windows(None)
            self.assertEqual(result, [])
        except ImportError:
            self.skipTest("Cannot import ProcessDetector in test environment")


if __name__ == "__main__":
    unittest.main(verbosity=2)
