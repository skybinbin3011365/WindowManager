"""
窗口管理器 - 日志工具单元测试
测试 log_utils 模块中的日志处理功能
"""

import unittest
import sys
import os
import logging
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestLogLevel(unittest.TestCase):
    """测试 LogLevel 枚举"""

    def test_loglevel_values(self):
        """测试 LogLevel 枚举值"""
        from src.log_utils import LogLevel
        self.assertIsNotNone(LogLevel.DEBUG)
        self.assertIsNotNone(LogLevel.INFO)
        self.assertIsNotNone(LogLevel.WARNING)
        self.assertIsNotNone(LogLevel.ERROR)
        self.assertIsNotNone(LogLevel.CRITICAL)

    def test_loglevel_from_value(self):
        """测试通过值获取 LogLevel"""
        from src.log_utils import LogLevel
        self.assertEqual(LogLevel(1), LogLevel.DEBUG)
        self.assertEqual(LogLevel(2), LogLevel.INFO)


class TestLogEntry(unittest.TestCase):
    """测试 LogEntry 数据类"""

    def test_log_entry_creation(self):
        """测试 LogEntry 创建"""
        from src.log_utils import LogEntry
        entry = LogEntry(
            timestamp=datetime.now(),
            level="INFO",
            logger_name="test",
            message="Test message"
        )
        self.assertEqual(entry.level, "INFO")
        self.assertEqual(entry.message, "Test message")
        self.assertEqual(entry.logger_name, "test")

    def test_log_entry_with_exception(self):
        """测试带异常信息的 LogEntry"""
        from src.log_utils import LogEntry
        entry = LogEntry(
            timestamp=datetime.now(),
            level="ERROR",
            logger_name="test",
            message="Error occurred",
            exception_info="Traceback..."
        )
        self.assertEqual(entry.exception_info, "Traceback...")


if __name__ == "__main__":
    unittest.main(verbosity=2)
