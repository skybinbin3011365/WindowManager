"""
窗口管理器 - 日志工具单元测试
测试 log_utils 模块中的日志处理功能
"""

# -*- coding: utf-8 -*-
import unittest as ut
import sys
import os
import unittest
import logging
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path
from src.log_utils import (
    LogLevel,
    LogEntry,
    BufferedLogHandler,
    PerformanceLogger,
    StructuredLogger,
    setup_logging,
)


if __name__ == "__main__":
    # 运行测试
    unittest.main(verbosity=2)
