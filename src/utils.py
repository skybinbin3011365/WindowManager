# -*- coding: utf-8 -*-
# windowmanager/utils.py
"""
工具模块 - 日志设置和辅助函数
"""

import logging
import logging.handlers
import os
import sys
import pathlib
import tempfile
from functools import wraps
from typing import Callable, TypeVar, Any, Optional

from constants import PathConstants, LogFormatConstants
from deps import win32con, win32api

T = TypeVar("T")


class HotkeyFormatter:
    """热键格式化工具类"""

    # 按键名称映射表
    KEY_NAME_MAP = {
        "ALT": "Alt",
        "CTRL": "Ctrl",
        "CONTROL": "Ctrl",
        "SHIFT": "SHIFT",
        "WIN": "Win",
        "LWIN": "Win",
        "RWIN": "Win",
        "TAB": "Tab",
        "ENTER": "Enter",
        "RETURN": "Enter",
        "SPACE": "Space",
        "BACKSPACE": "Backspace",
        "DELETE": "Delete",
        "DEL": "Delete",
        "INSERT": "Insert",
        "HOME": "Home",
        "END": "End",
        "PGUP": "Page Up",
        "PGDOWN": "Page Down",
        "UP": "Up",
        "DOWN": "Down",
        "LEFT": "Left",
        "RIGHT": "Right",
        "ESCAPE": "Esc",
        "ESC": "Esc",
        "F1": "F1",
        "F2": "F2",
        "F3": "F3",
        "F4": "F4",
        "F5": "F5",
        "F6": "F6",
        "F7": "F7",
        "F8": "F8",
        "F9": "F9",
        "F10": "F10",
        "F11": "F11",
        "F12": "F12",
        "LBUTTON": "LBUTTON",
        "RBUTTON": "RBUTTON",
        "MBUTTON": "MBUTTON",
        "XBUTTON1": "X1 Click",
        "XBUTTON2": "X2 Click",
        "CAPITAL": "Caps Lock",
        "NUMLOCK": "Num Lock",
        "SCROLL": "Scroll Lock",
    }

    @staticmethod
    def format(modifiers: int, key: int) -> str:
        """
        将热键格式化为字符串

        Args:
            modifiers: 修饰键
            key: 按键

        Returns:
            格式化后的热键字符串
        """
        parts = []

        if win32con is None:
            return ""

        MOD_LBUTTON = 0x1000
        MOD_RBUTTON = 0x2000
        MOD_MBUTTON = 0x4000

        # 添加修饰键
        if modifiers & win32con.MOD_CONTROL:
            parts.append("Ctrl")
        if modifiers & win32con.MOD_SHIFT:
            parts.append("Shift")
        if modifiers & win32con.MOD_ALT:
            parts.append("Alt")
        if modifiers & win32con.MOD_WIN:
            parts.append("Win")

        # 添加鼠标按键
        if modifiers & MOD_LBUTTON:
            parts.append("Left Click")
        if modifiers & MOD_RBUTTON:
            parts.append("Right Click")
        if modifiers & MOD_MBUTTON:
            parts.append("Middle Click")

        # 添加普通按键
        if key != 0:
            # 尝试获取按键名称
            try:
                if win32api is not None:
                    key_name = win32api.MapVirtualKey(key, 2)
                if key_name:
                    key_name_str = str(key_name).upper()
                    parts.append(HotkeyFormatter.KEY_NAME_MAP.get(key_name_str, key_name_str))
            except Exception:
                parts.append(f"Key_{key}")

        return "+".join(parts)

    @classmethod
    def format_hotkey(cls, hotkey: str) -> str:
        """将热键格式转换为用户友好的显示格式（统一大写）

        Args:
            hotkey: 原始热键字符串

        Returns:
            格式化后的热键字符串（大写）
        """
        if not hotkey:
            return ""

        parts = []
        for part in hotkey.split("+"):
            if not part:
                continue
            part = part.strip()
            if not part:
                continue
            # 统一转为大写显示
            parts.append(cls.KEY_NAME_MAP.get(part.upper(), part).upper())

        return " + ".join(parts)

    @classmethod
    def normalize_hotkey(cls, hotkey_str: str) -> str:
        """标准化热键字符串

        Args:
            hotkey_str: 原始热键字符串

        Returns:
            标准化后的热键字符串
        """
        if not hotkey_str:
            return ""

        parts = []
        for part in hotkey_str.split("+"):
            if not part:
                continue
            part = part.strip().upper()
            if not part:
                continue
            key = next(
                (k for k, v in cls.KEY_NAME_MAP.items() if v.lower() == part.lower()),
                part,
            )
            parts.append(key)

        return "+".join(parts)


def sanitize_title(title: str, max_length: int = 30) -> str:
    """对窗口标题进行脱敏处理，用于日志输出

    截断过长标题并移除可能的敏感路径信息，保留前缀用于识别。

    Args:
        title: 原始窗口标题
        max_length: 最大保留长度，默认30字符

    Returns:
        脱敏后的标题字符串
    """
    if not title:
        return ""
    # 截断过长标题
    if len(title) > max_length:
        return title[:max_length] + "..."
    return title


def get_resource_path(relative_path: str) -> str:
    """获取资源文件的绝对路径

    Args:
        relative_path: 相对路径

    Returns:
        str: 资源文件的绝对路径
    """
    if getattr(sys, "frozen", False) or hasattr(sys, "__nuitka_binary__"):
        # 打包后的路径（兼容 Nuitka standalone 和 PyInstaller）
        # Nuitka standalone: 资源文件与 exe 同目录，使用 sys.executable 父目录
        # PyInstaller onefile: 解压到 sys._MEIPASS（已废弃此模式，统一按 standalone 处理）
        base_path = os.path.dirname(sys.executable)
    else:
        # 开发环境路径
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def is_admin() -> bool:
    """检查当前进程是否以管理员权限运行

    Returns:
        bool: 是否具有管理员权限
    """
    try:
        import ctypes

        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def setup_logging(_config_dir: Optional[str] = None, log_level: str = "INFO"):
    """设置日志系统

    日志文件统一写到程序所在目录（打包）或项目根目录（开发）的 logs/ 子目录，
    不再写到用户主目录，便于集中管理。

    Args:
        config_dir: 保留参数（兼容旧接口），不再作为日志路径使用
        log_level: 日志级别
    """
    # 确定日志目录：打包时用 exe 所在目录，开发时用项目根目录
    if getattr(sys, "frozen", False) or hasattr(sys, "__nuitka_binary__"):
        base_dir = pathlib.Path(sys.executable).parent
    else:
        base_dir = pathlib.Path(__file__).parent.parent  # src 的上级 = 项目根

    logs_dir = base_dir / PathConstants.LOG_DIR_NAME
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
    except (OSError, IOError):
        # 备用：临时目录
        logs_dir = pathlib.Path(tempfile.gettempdir()) / "window_manager_logs"
        try:
            logs_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            logs_dir = pathlib.Path.cwd() / PathConstants.LOG_DIR_NAME
            logs_dir.mkdir(parents=True, exist_ok=True)

    logging.root.handlers = []
    logging.root.propagate = True

    # 设置日志级别
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    log_level_value = level_map.get(log_level, logging.INFO)
    logging.root.setLevel(log_level_value)

    formatter = logging.Formatter(
        LogFormatConstants.LOG_FORMAT, datefmt=LogFormatConstants.LOG_DATE_FORMAT
    )

    # 添加控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level_value)
    console_handler.setFormatter(formatter)
    logging.root.addHandler(console_handler)

    # 添加文件处理器 - 使用轮转日志避免文件过大
    try:
        log_file_path = logs_dir / PathConstants.LOG_FILE_NAME
        # 使用RotatingFileHandler，限制文件大小为10MB，保留3个备份
        file_handler = logging.handlers.RotatingFileHandler(
            log_file_path,
            encoding="utf-8",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=3,
            delay=True,  # 延迟打开文件，避免启动时阻塞
        )
        file_handler.setLevel(logging.INFO)  # 文件只记录 INFO 及以上，避免 DEBUG 刷屏
        file_handler.setFormatter(formatter)
        logging.root.addHandler(file_handler)
        logging.info("日志文件已设置: %s", log_file_path)
    except Exception as e:
        logging.warning("无法创建文件日志处理器: %s", str(e))

    return logs_dir


def win32_error_handler(
    default: T = None, log_level: str = "debug"
) -> Callable[[Callable[..., T]], Callable[..., T | None]]:
    """Windows API 异常处理装饰器

    Args:
        default: 异常时返回的默认值
        log_level: 日志级别，可选值: debug, info, warning, error

    Returns:
        Callable: 装饰器函数
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T | None]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T | None:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                func_name = func.__name__
                log_message = f"{func_name} 出错: {str(e)}"

                # 根据日志级别记录日志
                if log_level == "debug":
                    logging.debug(log_message)
                elif log_level == "info":
                    logging.info(log_message)
                elif log_level == "warning":
                    logging.warning(log_message)
                elif log_level == "error":
                    logging.error(log_message)

                return default

        return wrapper

    return decorator
