# windowmanager/core.py
"""
窗口管理器 - 核心模块
简化版本：包含Windows API封装、数据模型
"""
import sys
import os
import logging
import ctypes
from typing import Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum, auto

logger = logging.getLogger(__name__)

try:
    import win32gui
    import win32con
    import win32process
    import win32api
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False
    win32gui = win32con = win32process = win32api = None


class WindowState(Enum):
    NORMAL = auto()
    MINIMIZED = auto()
    MAXIMIZED = auto()
    HIDDEN = auto()


@dataclass
class WindowInfo:
    """窗口信息数据类

    属性:
        hwnd: int - 窗口句柄
        title: str - 窗口标题
        class_name: str - 窗口类名
        pid: int - 进程ID
        state: WindowState - 窗口状态
        is_visible: bool - 窗口是否可见
        process_name: str - 进程名称
    """
    hwnd: int
    title: str = ""
    class_name: str = ""
    pid: int = 0
    state: WindowState = WindowState.NORMAL
    is_visible: bool = True
    process_name: str = ""

    def get_display_title(self) -> str:
        """获取显示标题

        返回带有进程名的标题格式，如 "进程名: 窗口标题"

        返回:
            str - 格式化的显示标题
        """
        if self.process_name:
            return "{}: {}".format(self.process_name, self.title)
        return self.title


class SafeWindowsAPI:
    """安全的Windows API封装类

    提供安全的Windows API调用，包含异常处理和错误日志
    """
    EXCLUDED_CLASSES = {
        "Progman", "WorkerW", "Shell_TrayWnd", "Button",
        "tooltips_class32", "MSCTFIME UI", "IME", "OleMainThreadWndClass"
    }
    EXCLUDED_TITLES = {"", "Program Manager", "Settings"}

    @staticmethod
    def is_window(hwnd: int) -> bool:
        """检查句柄是否为有效的窗口

        参数:
            hwnd: int - 窗口句柄

        返回:
            bool - 是否为有效窗口
        """
        if not WIN32_AVAILABLE:
            return False
        try:
            return bool(win32gui.IsWindow(hwnd))
        except (win32gui.error, OSError) as e:
            logger.debug("Error in is_window: %s", str(e))
            return False
        except Exception as e:
            logger.error("Unexpected error in is_window: %s", str(e))
            return False

    @staticmethod
    def is_window_visible(hwnd: int) -> bool:
        """检查窗口是否可见

        参数:
            hwnd: int - 窗口句柄

        返回:
            bool - 窗口是否可见
        """
        if not WIN32_AVAILABLE:
            return False
        try:
            return bool(win32gui.IsWindowVisible(hwnd))
        except (win32gui.error, OSError) as e:
            logger.debug("Error in is_window_visible: %s", str(e))
            return False
        except Exception as e:
            logger.error("Unexpected error in is_window_visible: %s", str(e))
            return False

    @staticmethod
    def get_window_text(hwnd: int) -> str:
        """获取窗口标题

        参数:
            hwnd: int - 窗口句柄

        返回:
            str - 窗口标题
        """
        if not WIN32_AVAILABLE:
            return ""
        try:
            return win32gui.GetWindowText(hwnd)
        except (win32gui.error, OSError) as e:
            logger.debug("Error in get_window_text: %s", str(e))
            return ""
        except Exception as e:
            logger.error("Unexpected error in get_window_text: %s", str(e))
            return ""

    @staticmethod
    def get_window_class(hwnd: int) -> str:
        """获取窗口类名

        参数:
            hwnd: int - 窗口句柄

        返回:
            str - 窗口类名
        """
        if not WIN32_AVAILABLE:
            return ""
        try:
            return win32gui.GetClassName(hwnd)
        except (win32gui.error, OSError) as e:
            logger.debug("Error in get_window_class: %s", str(e))
            return ""
        except Exception as e:
            logger.error("Unexpected error in get_window_class: %s", str(e))
            return ""

    @staticmethod
    def get_window_thread_process_id(hwnd: int) -> Tuple[int, int]:
        """获取窗口的线程ID和进程ID

        参数:
            hwnd: int - 窗口句柄

        返回:
            Tuple[int, int] - (线程ID, 进程ID)
        """
        if not WIN32_AVAILABLE:
            return (0, 0)
        try:
            return win32process.GetWindowThreadProcessId(hwnd)
        except (win32process.error, OSError) as e:
            logger.debug("Error in get_window_thread_process_id: %s", str(e))
            return (0, 0)
        except Exception as e:
            logger.error("Unexpected error in get_window_thread_process_id: %s", str(e))
            return (0, 0)

    @staticmethod
    def show_window(hwnd: int, cmd: int) -> bool:
        """显示或隐藏窗口

        参数:
            hwnd: int - 窗口句柄
            cmd: int - 显示命令（如win32con.SW_SHOW, win32con.SW_HIDE等）

        返回:
            bool - 操作是否成功
        """
        if not WIN32_AVAILABLE:
            return False
        try:
            return bool(win32gui.ShowWindow(hwnd, cmd))
        except (win32gui.error, OSError) as e:
            logger.debug("Error in show_window: %s", str(e))
            return False
        except Exception as e:
            logger.error("Unexpected error in show_window: %s", str(e))
            return False

    @staticmethod
    def set_foreground_window(hwnd: int) -> bool:
        """将窗口设置为前台窗口

        参数:
            hwnd: int - 窗口句柄

        返回:
            bool - 操作是否成功
        """
        if not WIN32_AVAILABLE:
            return False
        try:
            win32gui.SetForegroundWindow(hwnd)
            return True
        except (win32gui.error, OSError) as e:
            logger.debug("Error in set_foreground_window: %s", str(e))
            return False
        except Exception as e:
            logger.error("Unexpected error in set_foreground_window: %s", str(e))
            return False

    @staticmethod
    def enum_windows() -> List[int]:
        """枚举所有可见窗口

        排除系统窗口和空标题窗口，只返回有效的应用窗口

        返回:
            List[int] - 窗口句柄列表
        """
        if not WIN32_AVAILABLE:
            return []
        windows = []

        def callback(hwnd, _):
            try:
                if not SafeWindowsAPI.is_window(hwnd):
                    return True

                class_name = SafeWindowsAPI.get_window_class(hwnd)
                title = SafeWindowsAPI.get_window_text(hwnd)

                if class_name in SafeWindowsAPI.EXCLUDED_CLASSES:
                    return True
                if title in SafeWindowsAPI.EXCLUDED_TITLES:
                    return True
                if not title:
                    return True

                rect = SafeWindowsAPI.get_window_rect(hwnd)
                if rect:
                    width = rect[2] - rect[0]
                    height = rect[3] - rect[1]
                    if width >= 50 and height >= 50:
                        windows.append(hwnd)
            except Exception as e:
                logger.debug("Error in enum_windows callback: %s", str(e))
                pass
            return True

        try:
            win32gui.EnumWindows(callback, None)
        except Exception as e:
            logger.debug("Error in enum_windows: %s", str(e))
            pass
        return windows

    @staticmethod
    def get_window_rect(hwnd: int) -> Optional[Tuple[int, int, int, int]]:
        """获取窗口矩形区域

        参数:
            hwnd: int - 窗口句柄

        返回:
            Optional[Tuple[int, int, int, int]] - (left, top, right, bottom) 或 None
        """
        if not WIN32_AVAILABLE:
            return None
        try:
            return win32gui.GetWindowRect(hwnd)
        except (win32gui.error, OSError) as e:
            logger.debug("Error in get_window_rect: %s", str(e))
            return None
        except Exception as e:
            logger.error("Unexpected error in get_window_rect: %s", str(e))
            return None

    @staticmethod
    def get_process_name(pid: int) -> str:
        """获取进程名称

        参数:
            pid: int - 进程ID

        返回:
            str - 进程名称
        """
        if not WIN32_AVAILABLE or pid <= 0:
            return "unknown"
        try:
            import psutil
            process = psutil.Process(pid)
            return process.name()
        except Exception as e:
            logger.debug("Error in get_process_name (psutil): %s", str(e))
            try:
                handle = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION, False, pid)
                if handle:
                    try:
                        module_name = win32process.GetModuleFileNameEx(handle, 0)
                        return os.path.basename(module_name)
                    finally:
                        win32api.CloseHandle(handle)
            except Exception as e2:
                logger.debug("Error in get_process_name (win32): %s", str(e2))
                pass
        return "unknown"

    @staticmethod
    def get_foreground_window() -> Optional[int]:
        """获取当前前台窗口

        返回:
            Optional[int] - 前台窗口句柄或 None
        """
        if not WIN32_AVAILABLE:
            return None
        try:
            return win32gui.GetForegroundWindow()
        except (win32gui.error, OSError) as e:
            logger.debug("Error in get_foreground_window: %s", str(e))
            return None
        except Exception as e:
            logger.error("Unexpected error in get_foreground_window: %s", str(e))
            return None
