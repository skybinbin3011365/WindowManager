"""
窗口管理器 - 常量模块单元测试
测试 constants 模块中的所有常量类
"""

import unittest
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.constants import (
    TimeoutConstants,
    TimeConstants,
    TimeThresholdConstants,
    WindowConstants,
    UIConstants,
    LogConstants,
    ConfigConstants,
    HotkeyConstants,
    ErrorCodes,
    DefaultValues,
    AppConstants,
    PathConstants,
    LogFormatConstants,
    UIMainConstants,
    NTPConstants,
    WMIProcessMonitorConstants,
    UICommonConstants,
)


class TestTimeoutConstants(unittest.TestCase):
    """测试 TimeoutConstants 超时常量类"""

    def test_timeout_values_are_positive(self):
        """测试所有超时值都是正数"""
        self.assertGreater(TimeoutConstants.REFRESH_TIMEOUT_MS, 0)
        self.assertGreater(TimeoutConstants.PROCESS_MONITOR_TIMEOUT_MS, 0)
        self.assertGreater(TimeoutConstants.WINDOW_ENUMERATION_TIMEOUT_MS, 0)
        self.assertGreater(TimeoutConstants.SINGLE_SHOT_DELAY_MS, 0)
        self.assertGreater(TimeoutConstants.AUTO_REFRESH_DELAY_MS, 0)
        self.assertGreater(TimeoutConstants.HOTKEY_RECORDING_TIMEOUT_MS, 0)
        self.assertGreater(TimeoutConstants.HOTKEY_CHECK_INTERVAL_MS, 0)
        self.assertGreater(TimeoutConstants.TIME_DISPLAY_UPDATE_INTERVAL_MS, 0)

    def test_timeout_reasonable_ranges(self):
        """测试超时值在合理范围内"""
        self.assertLessEqual(TimeoutConstants.REFRESH_TIMEOUT_MS, 10000)
        self.assertLessEqual(TimeoutConstants.HOTKEY_CHECK_INTERVAL_MS, 100)


class TestTimeConstants(unittest.TestCase):
    """测试 TimeConstants 时间常量类"""

    def test_time_constants_are_positive(self):
        """测试所有时间常量都是正数"""
        self.assertGreater(TimeConstants.SHORT_SLEEP_SECONDS, 0)
        self.assertGreater(TimeConstants.MEDIUM_SLEEP_SECONDS, 0)
        self.assertGreater(TimeConstants.LOG_TIME_OFFSET_THRESHOLD_SECONDS, 0)

    def test_short_sleep_less_than_medium(self):
        """测试短睡眠时间小于中等睡眠时间"""
        self.assertLess(
            TimeConstants.SHORT_SLEEP_SECONDS,
            TimeConstants.MEDIUM_SLEEP_SECONDS
        )


class TestWindowConstants(unittest.TestCase):
    """测试 WindowConstants 窗口常量类"""

    def test_max_lengths_are_reasonable(self):
        """测试最大长度在合理范围内"""
        self.assertGreater(WindowConstants.MAX_WINDOW_TITLE_LENGTH, 0)
        self.assertLessEqual(WindowConstants.MAX_WINDOW_TITLE_LENGTH, 500)
        self.assertGreater(WindowConstants.MAX_PROCESS_NAME_LENGTH, 0)
        self.assertLessEqual(WindowConstants.MAX_PROCESS_NAME_LENGTH, 100)

    def test_min_hwnd_value(self):
        """测试最小窗口句柄值"""
        self.assertGreaterEqual(WindowConstants.MIN_WINDOW_HWND, 0)

    def test_background_hwnd_offset_is_negative(self):
        """测试后台进程窗口句柄偏移量为负数"""
        self.assertLess(WindowConstants.BACKGROUND_PROCESS_HWND_OFFSET, 0)


class TestUIConstants(unittest.TestCase):
    """测试 UIConstants UI常量类"""

    def test_window_dimensions_are_reasonable(self):
        """测试窗口尺寸在合理范围内"""
        self.assertGreater(UIConstants.WINDOW_DEFAULT_WIDTH, 0)
        self.assertGreater(UIConstants.WINDOW_DEFAULT_HEIGHT, 0)
        self.assertGreater(UIConstants.MIN_WINDOW_WIDTH, 0)
        self.assertGreater(UIConstants.MIN_WINDOW_HEIGHT, 0)
        self.assertLessEqual(UIConstants.MIN_WINDOW_WIDTH, UIConstants.WINDOW_DEFAULT_WIDTH)
        self.assertLessEqual(UIConstants.MIN_WINDOW_HEIGHT, UIConstants.WINDOW_DEFAULT_HEIGHT)

    def test_table_row_height(self):
        """测试表格行高"""
        self.assertGreater(UIConstants.TABLE_ROW_HEIGHT, 0)


class TestConfigConstants(unittest.TestCase):
    """测试 ConfigConstants 配置常量类"""

    def test_config_version_format(self):
        """测试配置版本格式"""
        self.assertIsInstance(ConfigConstants.CONFIG_VERSION, str)
        self.assertTrue(len(ConfigConstants.CONFIG_VERSION) > 0)

    def test_max_limits_are_reasonable(self):
        """测试最大限制在合理范围内"""
        self.assertGreater(ConfigConstants.MAX_KEYWORDS, 0)
        self.assertLessEqual(ConfigConstants.MAX_KEYWORDS, 1000)
        self.assertGreater(ConfigConstants.MAX_PROCESS_WHITELIST, 0)
        self.assertLessEqual(ConfigConstants.MAX_PROCESS_WHITELIST, 10000)


class TestErrorCodes(unittest.TestCase):
    """测试 ErrorCodes 错误码常量类"""

    def test_error_codes_are_unique(self):
        """测试错误码唯一"""
        codes = [
            ErrorCodes.SUCCESS,
            ErrorCodes.WINDOW_NOT_FOUND,
            ErrorCodes.PROCESS_NOT_FOUND,
            ErrorCodes.HOTKEY_CONFLICT,
            ErrorCodes.CONFIG_ERROR,
            ErrorCodes.PERMISSION_DENIED,
        ]
        self.assertEqual(len(codes), len(set(codes)))

    def test_success_is_zero(self):
        """测试成功码为0"""
        self.assertEqual(ErrorCodes.SUCCESS, 0)


class TestAppConstants(unittest.TestCase):
    """测试 AppConstants 应用常量类"""

    def test_app_title_not_empty(self):
        """测试应用标题非空"""
        self.assertTrue(len(AppConstants.APP_TITLE) > 0)

    def test_app_version_format(self):
        """测试应用版本格式"""
        parts = AppConstants.APP_VERSION.split(".")
        self.assertGreaterEqual(len(parts), 2)
        for part in parts:
            self.assertTrue(part.isdigit())


class TestNTPConstants(unittest.TestCase):
    """测试 NTPConstants NTP常量类"""

    def test_default_servers_not_empty(self):
        """测试默认服务器列表非空"""
        self.assertGreater(len(NTPConstants.DEFAULT_NTP_SERVERS), 0)

    def test_ntp_port_is_valid(self):
        """测试NTP端口有效"""
        self.assertEqual(NTPConstants.NTP_PORT, 123)
        self.assertGreater(NTPConstants.NTP_PORT, 0)
        self.assertLessEqual(NTPConstants.NTP_PORT, 65535)

    def test_ntp_timeout_reasonable(self):
        """测试NTP超时时间合理"""
        self.assertGreater(NTPConstants.NTP_TIMEOUT, 0)
        self.assertLessEqual(NTPConstants.NTP_TIMEOUT, 10)

    def test_ntp_max_retries_reasonable(self):
        """测试NTP最大重试次数合理"""
        self.assertGreater(NTPConstants.NTP_MAX_RETRIES, 0)
        self.assertLessEqual(NTPConstants.NTP_MAX_RETRIES, 10)


class TestUIMainConstants(unittest.TestCase):
    """测试 UIMainConstants UI主界面常量类"""

    def test_column_widths_are_positive(self):
        """测试列宽为正数"""
        self.assertGreater(UIMainConstants.COLUMN_WIDTH_SELECT, 0)
        self.assertGreater(UIMainConstants.COLUMN_WIDTH_TYPE, 0)
        self.assertGreater(UIMainConstants.COLUMN_WIDTH_PROCESS, 0)
        self.assertGreater(UIMainConstants.COLUMN_WIDTH_HWND, 0)

    def test_default_refresh_interval(self):
        """测试默认刷新间隔"""
        self.assertGreater(UIMainConstants.DEFAULT_AUTO_REFRESH_INTERVAL, 0)


class TestLogConstants(unittest.TestCase):
    """测试 LogConstants 日志常量类"""

    def test_max_log_length(self):
        """测试最大日志长度"""
        self.assertGreater(LogConstants.MAX_LOG_LENGTH, 0)
        self.assertLessEqual(LogConstants.MAX_LOG_LENGTH, 100000)

    def test_log_retention_days(self):
        """测试日志保留天数"""
        self.assertGreater(LogConstants.LOG_RETENTION_DAYS, 0)


class TestHotkeyConstants(unittest.TestCase):
    """测试 HotkeyConstants 热键常量类"""

    def test_max_hotkey_length(self):
        """测试最大热键长度"""
        self.assertGreater(HotkeyConstants.MAX_HOTKEY_LENGTH, 0)

    def test_max_modifier_keys(self):
        """测试最大修饰键数量"""
        self.assertGreater(HotkeyConstants.MAX_MODIFIER_KEYS, 0)
        self.assertLessEqual(HotkeyConstants.MAX_MODIFIER_KEYS, 10)


class TestPathConstants(unittest.TestCase):
    """测试 PathConstants 路径常量类"""

    def test_log_file_name_not_empty(self):
        """测试日志文件名非空"""
        self.assertTrue(len(PathConstants.LOG_FILE_NAME) > 0)

    def test_config_file_name_not_empty(self):
        """测试配置文件名非空"""
        self.assertTrue(len(PathConstants.CONFIG_FILE_NAME) > 0)

    def test_icon_candidates_not_empty(self):
        """测试图标候选列表非空"""
        self.assertGreater(len(PathConstants.ICON_CANDIDATES), 0)


class TestDefaultValues(unittest.TestCase):
    """测试 DefaultValues 默认值常量类"""

    def test_auto_refresh_interval_positive(self):
        """测试默认自动刷新间隔为正数"""
        self.assertGreater(DefaultValues.AUTO_REFRESH_INTERVAL, 0)

    def test_log_level_valid(self):
        """测试日志级别有效"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        self.assertIn(DefaultValues.LOG_LEVEL, valid_levels)


if __name__ == "__main__":
    unittest.main(verbosity=2)
