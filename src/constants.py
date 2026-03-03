# windowmanager/constants.py
"""
常量定义模块
集中管理所有魔法数字和硬编码字符串
"""

# 版本信息
__version__ = "2.0.0"
VERSION_MAJOR = 2
VERSION_MINOR = 0
VERSION_PATCH = 0

# Windows API 错误码
ERROR_ALREADY_EXISTS = 183  # 互斥体已存在错误码

# NTP时间同步常量
NTP_DEFAULT_TIMEOUT = 2  # NTP请求默认超时时间（秒）
NTP_CALIBRATE_TIMEOUT = 3  # NTP校准超时时间（秒）
NTP_MIN_CALIBRATION_INTERVAL = 60  # 最小校准间隔（秒）
NTP_DEFAULT_ERROR_THRESHOLD = 5  # 默认时间误差阈值（秒）

# 配置管理常量
CONFIG_SAVE_DELAY = 2.0  # 配置延迟保存时间（秒）
CONFIG_DIR_NAME = ".window_manager"  # 配置目录名
CONFIG_FILE_NAME = "config.json"  # 配置文件名

# UI常量
WINDOW_REFRESH_INTERVAL = 5.0  # 窗口列表刷新间隔（秒）
WINDOW_MIN_WIDTH = 800  # 窗口最小宽度
WINDOW_MIN_HEIGHT = 600  # 窗口最小高度
WINDOW_DEFAULT_WIDTH = 1000  # 窗口默认宽度
WINDOW_DEFAULT_HEIGHT = 700  # 窗口默认高度

# 日志常量
LOG_DIR_NAME = "logs"  # 日志目录名
LOG_FILE_NAME = "window_manager.log"  # 日志文件名
LOG_FORMAT = "%(asctime)s [%(levelname).1s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 应用信息
APP_NAME = "WindowManager"
APP_GUID = "{window_manager_12345}"
APP_TITLE = "窗口管理器"

# 默认热键配置
DEFAULT_HIDE_HOTKEY = "Middle+Right"
DEFAULT_SHOW_HOTKEY = "Shift+Right"

# 默认NTP服务器列表
DEFAULT_NTP_SERVERS = [
    "ntp1.aliyun.com",
    "ntp2.aliyun.com",
    "ntp3.aliyun.com",
    "ntp1.ntsc.ac.cn",
    "ntp1.tencent.com"
]
