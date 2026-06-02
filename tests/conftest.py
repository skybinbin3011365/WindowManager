"""
测试配置和夹具 (Fixtures)

提供测试所需的公共配置和辅助函数
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any

# 添加项目根目录和 src 目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(PROJECT_ROOT))


def create_temp_config_dir():
    """创建临时配置目录"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


def create_temp_log_dir():
    """创建临时日志目录"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


class MockConfig:
    """模拟配置对象"""

    def __init__(self, **kwargs):
        self.version = "2.0"
        self.hide_hotkey = "MBUTTON+RBUTTON"
        self.show_hotkey = "SHIFT+RBUTTON"
        self.switch_hotkey = "CTRL+RBUTTON"
        self.switch_processes = []
        self.log_level = "INFO"
        self.enable_window_refresh_log = True
        self.enable_window_operation_log = True
        self.enable_debug_log = False
        self.auto_start = False
        self.auto_refresh_interval = 10.0
        self.keywords = []
        self.process_whitelist = []
        self.auto_select_processes = []
        self.target_windows = []
        self.ui = {
            "width": 1000,
            "height": 700,
            "theme": "light",
            "hidden_columns": [],
        }
        self.ntp_servers = [
            "time1.aliyun.com",
            "time2.aliyun.com",
            "ntp.ntsc.ac.cn",
        ]
        self.auto_sync_enabled = False
        self.auto_sync_interval_hours = 1.0
        self.ntp_check_interval = 60
        self.ntp_error_threshold = 5
        self.ntp_auto_calibrate = False
        self.enable_ntp_log = True
        self.enable_timed_calibration = True
        self.calibration_interval = 30

        for key, value in kwargs.items():
            setattr(self, key, value)


class MockWindowInfo:
    """模拟窗口信息对象"""

    def __init__(self, **kwargs):
        self.hwnd = kwargs.get("hwnd", 0)
        self.title = kwargs.get("title", "")
        self.class_name = kwargs.get("class_name", "")
        self.pid = kwargs.get("pid", 0)
        self.state = kwargs.get("state", 1)
        self.is_visible = kwargs.get("is_visible", True)
        self.process_name = kwargs.get("process_name", "")
        self.is_foreground = kwargs.get("is_foreground", False)
        self.monitor_id = kwargs.get("monitor_id", None)
        self.monitor_name = kwargs.get("monitor_name", "")
        self.is_taskbar = kwargs.get("is_taskbar", None)

    def get_display_title(self):
        """获取显示标题"""
        if self.process_name:
            return f"{self.process_name}: {self.title}"
        return self.title


def get_sample_config_data() -> Dict[str, Any]:
    """获取示例配置数据"""
    return {
        "version": "2.0",
        "hide_hotkey": "Ctrl+Shift+H",
        "show_hotkey": "Ctrl+Shift+S",
        "switch_hotkey": "Ctrl+Shift+W",
        "log_level": "DEBUG",
        "enable_debug_log": True,
        "auto_refresh_interval": 5.0,
        "keywords": ["chrome", "firefox"],
        "process_whitelist": ["explorer.exe"],
        "target_windows": [
            {
                "hwnd": 12345,
                "process_name": "chrome.exe",
                "title": "Google Chrome",
                "state": "visible",
                "source": "manual",
            }
        ],
        "ui": {"width": 1200, "height": 800, "theme": "dark"},
        "ntp_servers": ["time.google.com"],
        "auto_sync_enabled": True,
    }
