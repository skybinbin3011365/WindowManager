#!/usr/bin/env python3
"""
常量定义 - 消除魔法数字，提高代码可维护性
"""


# 时间常量（毫秒）
class TimeoutConstants:
    """超时常量"""

    REFRESH_TIMEOUT_MS = 5000  # 窗口刷新超时
    PROCESS_MONITOR_TIMEOUT_MS = 1000  # 进程监听超时
    WINDOW_ENUMERATION_TIMEOUT_MS = 3000  # 窗口枚举超时
    SINGLE_SHOT_DELAY_MS = 1000  # 单次定时器延迟
    AUTO_REFRESH_DELAY_MS = 1500  # 自动刷新延迟
    HOTKEY_RECORDING_TIMEOUT_MS = 3000  # 热键录制超时


# 窗口相关常量
class WindowConstants:
    """窗口相关常量"""

    MAX_WINDOW_TITLE_LENGTH = 100  # 窗口标题最大长度
    MAX_PROCESS_NAME_LENGTH = 50  # 进程名最大长度
    MIN_WINDOW_HWND = 1  # 最小窗口句柄值
    BACKGROUND_PROCESS_HWND_OFFSET = -1  # 后台进程占位窗口句柄偏移量（负数表示占位符）


# UI相关常量
class UIConstants:
    """UI相关常量"""

    WINDOW_DEFAULT_WIDTH = 1000  # 窗口默认宽度
    WINDOW_DEFAULT_HEIGHT = 700  # 窗口默认高度
    MIN_WINDOW_WIDTH = 800  # 最小窗口宽度
    MIN_WINDOW_HEIGHT = 600  # 最小窗口高度
    TABLE_ROW_HEIGHT = 30  # 表格行高


# 日志相关常量
class LogConstants:
    """日志相关常量"""

    MAX_LOG_LENGTH = 1000  # 最大日志长度
    LOG_RETENTION_DAYS = 7  # 日志保留天数


# 配置相关常量
class ConfigConstants:
    """配置相关常量"""

    CONFIG_VERSION = "2.0"  # 配置版本
    MAX_KEYWORDS = 50  # 最大关键字数量
    MAX_PROCESS_WHITELIST = 100  # 最大进程白名单数量


# 热键相关常量
class HotkeyConstants:
    """热键相关常量"""

    MAX_HOTKEY_LENGTH = 50  # 热键字符串最大长度
    MAX_MODIFIER_KEYS = 4  # 最大修饰键数量
    HOTKEY_HEALTH_CHECK_INTERVAL = 5000  # 热键健康检查间隔（毫秒）


# 错误码常量
class ErrorCodes:
    """错误码常量"""

    SUCCESS = 0
    WINDOW_NOT_FOUND = 1001
    PROCESS_NOT_FOUND = 1002
    HOTKEY_CONFLICT = 1003
    CONFIG_ERROR = 1004
    PERMISSION_DENIED = 1005


# 默认值常量
class DefaultValues:
    """默认值常量"""

    AUTO_REFRESH_INTERVAL = 5.0  # 默认自动刷新间隔（秒）
    LOG_LEVEL = "INFO"  # 默认日志级别
    ENABLE_WINDOW_OPERATION_LOG = True  # 默认启用窗口操作日志
    ENABLE_DEBUG_LOG = False  # 默认禁用调试日志


# 应用相关常量
class AppConstants:
    """应用相关常量"""

    APP_TITLE = "窗口管理器"  # 应用标题
    APP_VERSION = "2.0.0"  # 应用版本
    APP_GUID = "{12345678-1234-1234-1234-123456789012}"  # 应用GUID
    ERROR_ALREADY_EXISTS = 183  # 错误码：已存在


# 文件路径常量
class PathConstants:
    """文件路径常量"""

    LOG_DIR_NAME = "logs"  # 日志目录名
    LOG_FILE_NAME = "window_manager.log"  # 日志文件名
    CONFIG_DIR_NAME = "config"  # 配置目录名
    CONFIG_FILE_NAME = "config.json"  # 配置文件名

    # 图标文件路径
    ICON_CANDIDATES = [
        "assets/WinHide2.png",
        "assets/WinHide2.ico",
    ]  # 图标候选文件（优先使用PNG格式）


# 日志格式常量
class LogFormatConstants:
    """日志格式常量"""

    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"  # 日志格式
    LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"  # 日志日期格式


# UI主界面常量
class UIMainConstants:
    """UI主界面常量"""

    # 列宽常量
    COLUMN_WIDTH_SELECT = 50  # 选择列宽度
    COLUMN_WIDTH_TYPE = 60  # 类型列宽度
    COLUMN_WIDTH_PROCESS = 100  # 进程列宽度
    COLUMN_WIDTH_DISPLAY = 80  # 显示器列宽度

    # 时间常量
    INITIAL_REFRESH_DELAY = 1000  # 初始刷新延迟（毫秒）
    THREAD_WAIT_TIMEOUT = 1000  # 线程等待超时（毫秒）

    # 默认配置值
    DEFAULT_AUTO_REFRESH_INTERVAL = 5.0  # 默认自动刷新间隔（秒）


# NTP时间同步常量
class NTPConstants:
    """NTP时间同步常量"""

    DEFAULT_NTP_SERVERS = [
        "time1.aliyun.com",
        "time2.aliyun.com",
        "ntp.ntsc.ac.cn",
        "0.cn.pool.ntp.org",
        "time.cloud.tencent.com",
    ]  # 默认NTP服务器列表
    NTP_PORT = 123  # NTP端口
    NTP_TIMEOUT = 2  # NTP超时时间（秒）- 减少到2秒以加快响应
    NTP_MAX_RETRIES = 2  # NTP最大重试次数 - 减少到2次
    NTP_TIMESTAMP_DELTA = 2208988800  # NTP时间戳偏移量


# WMI进程监听常量
class WMIProcessMonitorConstants:
    """WMI进程监听常量"""

    PROCESS_EVENT_TIMEOUT_MS = 1000  # 进程事件监听超时（毫秒）


# UI通用常量
class UICommonConstants:
    """UI通用常量"""

    LOG_TIMER_INTERVAL_MS = 100  # 日志定时器间隔（毫秒）
    TRAY_MESSAGE_DURATION = 3000  # 托盘消息显示时长（毫秒）
