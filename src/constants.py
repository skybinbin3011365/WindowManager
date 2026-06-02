#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
    HOTKEY_CHECK_INTERVAL_MS = 20  # 热键检查间隔
    TIME_DISPLAY_UPDATE_INTERVAL_MS = 1000  # 时间显示更新间隔
    SETTINGS_AUTO_REFRESH_INTERVAL_MS = 60000  # 设置页面自动刷新间隔
    AUTO_CALIBRATION_INTERVAL_MS = 60000  # 自动校时间隔


# 时间常量（秒）
class TimeConstants:
    """时间常量（秒）"""

    SHORT_SLEEP_SECONDS = 0.1  # 短睡眠时长
    MEDIUM_SLEEP_SECONDS = 0.5  # 中等睡眠时长
    LOG_TIME_OFFSET_THRESHOLD_SECONDS = 1.0  # 日志时间偏移阈值


# 时间阈值常量
class TimeThresholdConstants:
    """时间阈值常量"""

    LOG_TIME_OFFSET_THRESHOLD_MS = 1000  # 日志时间偏移阈值（毫秒）


# 窗口相关常量
class WindowConstants:
    """窗口相关常量"""

    UNKNOWN_PROCESS_NAME = "unknown"
    UNKNOWN_PROCESS_DISPLAY_NAME = "<unknown>"
    ERROR_PROCESS_NAME = "<error>"
    SYSTEM_PROCESS_NAME = "<system>"
    UNKNOWN_PROCESS_PID_TEMPLATE = "unknown_{}"

    MAX_WINDOW_TITLE_LENGTH = 100  # 窗口标题最大长度
    MAX_PROCESS_NAME_LENGTH = 50  # 进程名最大长度
    MIN_WINDOW_HWND = 1  # 最小窗口句柄值
    BACKGROUND_PROCESS_HWND_OFFSET = -1  # 后台进程占位窗口句柄偏移量（负数表示占位符）

    # 非用户窗口类名前缀（枚举时排除这些前缀开头的窗口类）
    NON_USER_CLASS_PREFIXES = (
        "DirectUIHWND",
        "Internet Explorer_",
        "Frame Folder",
        "SysTreeView",
        "SysListView",
        "SysTree",
        "SysList",
    )

    # 排除的窗口类名（系统桌面/任务栏/IME等非用户窗口）
    EXCLUDED_CLASSES = {
        "Progman",
        "WorkerW",
        "Shell_TrayWnd",
        "Shell_SecondaryTrayWnd",
        "Button",
        "Static",
        "Edit",
        "#32770",
        "tooltips_class32",
        "MSCTFIME UI",
        "IME",
        "OleMainThreadWndClass",
    }

    # 排除的窗口标题
    EXCLUDED_TITLES = {"", "Program Manager", "Settings"}

    # 系统类名（用于窗口分类器中识别系统级窗口）
    SYSTEM_CLASSES = {"IME", "MSCTFIME UI", "Tooltip"}

    # 系统标题（用于窗口分类器中识别系统级窗口）
    SYSTEM_TITLES = {"", "Program Manager", "Default IME", "MSCTFIME UI"}


# UI相关常量
class UIConstants:
    """UI相关常量"""

    WINDOW_DEFAULT_WIDTH = 1000  # 窗口默认宽度
    WINDOW_DEFAULT_HEIGHT = 700  # 窗口默认高度
    MIN_WINDOW_WIDTH = 800  # 最小窗口宽度
    MIN_WINDOW_HEIGHT = 600  # 最小窗口高度
    TABLE_ROW_HEIGHT = 30  # 表格行高

    # 启动延迟常量（毫秒）
    START_WINDOW_MANAGER_DELAY = 100  # 启动窗口管理器延迟
    POST_START_REFRESH_DELAY = 300  # 启动后延迟刷新
    TRAY_INIT_RETRY_DELAY = 3000  # 托盘初始化重试延迟
    TRAY_VISIBLE_CHECK_DELAY = 1000  # 托盘可见性检查延迟
    TRAY_HEARTBEAT_INTERVAL = 30000  # 托盘心跳检测间隔


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
    COLUMN_WIDTH_HWND = 90  # HWND列宽度

    # 时间常量
    INITIAL_REFRESH_DELAY = 1000  # 初始刷新延迟（毫秒）
    THREAD_WAIT_TIMEOUT = 1000  # 线程等待超时（毫秒）
    THREAD_SHORT_WAIT_TIMEOUT = 100  # 线程短等待超时（毫秒，非阻塞）
    RESTORE_HIDDEN_WINDOWS_DELAY = 500  # 恢复隐藏窗口延迟（毫秒）
    LOAD_SWITCH_PROCESSES_DELAY = 600  # 加载切换进程配置延迟（毫秒）
    AUTO_SELECT_KEYWORD_DELAY = 1500  # 自动选中关键字窗口延迟（毫秒）
    THREAD_CLEANUP_MAX_CHECKS = 10  # 延迟清理最大检查次数
    THREAD_CLEANUP_INTERVAL = 500  # 延迟清理检查间隔（毫秒）
    TEMP_MESSAGE_DURATION = 2000  # 临时消息默认显示时长（毫秒）

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
