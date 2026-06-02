# -*- coding: utf-8 -*-
# windowmanager/deps.py
"""
依赖检查模块
检测可选依赖是否可用，统一管理所有外部依赖导入
"""

import logging
from typing import Any, TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    psutil: Any = None
    keyboard: Any = None
    mouse: Any = None
    win32gui: Any = None
    win32con: Any = None
    win32process: Any = None
    win32api: Any = None

try:
    import psutil  # pylint: disable=unused-import
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False
    logger.warning("psutil 库未安装，部分功能将不可用")

try:
    from pynput import keyboard, mouse  # pylint: disable=unused-import
    PYNPUT_AVAILABLE = True
except ImportError:
    keyboard = None
    mouse = None
    PYNPUT_AVAILABLE = False
    logger.warning("pynput 库未安装，热键功能将不可用")

try:
    import win32gui  # pylint: disable=unused-import
    import win32con  # pylint: disable=unused-import
    import win32process  # pylint: disable=unused-import
    import win32api  # pylint: disable=unused-import
    WIN32_AVAILABLE = True
    WIN32GUI_AVAILABLE = True
except ImportError:
    win32gui = None
    win32con = None
    win32process = None
    win32api = None
    WIN32_AVAILABLE = False
    WIN32GUI_AVAILABLE = False
    logger.warning("pywin32 库未安装，窗口操作功能将不可用")
