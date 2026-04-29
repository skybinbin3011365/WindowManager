"""
自定义部件包
提供应用程序的 UI 部件
"""

from widgets.hotkey_settings import HotkeySettingsWidget
from widgets.time_settings import TimeSettingsWidget
from widgets.whitelist_settings import WhitelistSettingsWidget

__all__ = [
    "HotkeySettingsWidget",
    "TimeSettingsWidget",
    "WhitelistSettingsWidget",
]
