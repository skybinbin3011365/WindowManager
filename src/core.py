# windowmanager/core.py
"""
窗口管理器 - 核心模块
简化版本：包含Windows API封装、数据模型
"""

import os
import logging
import threading
import ctypes
from typing import Optional, List, Tuple, Dict

from utils import win32_error_handler
from window_base import WindowState, MonitorInfo, WindowInfo, WindowInfoParams

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

# 尝试导入 psutil（可选依赖）
try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False


class SafeWindowsAPI:
    """安全的Windows API封装类

    提供安全的Windows API调用，包含异常处理和错误日志
    """

    # ctypes 结构体定义（提取公共定义避免重复）
    class _MONITORINFO(ctypes.Structure):
        """MonitorInfo 结构体（内部使用）"""
        _fields_ = [
            ("cbSize", ctypes.c_ulong),
            ("rcMonitor", ctypes.c_int * 4),
            ("rcWork", ctypes.c_int * 4),
            ("dwFlags", ctypes.c_ulong),
        ]

    class _MONITORINFOEX(ctypes.Structure):
        """MonitorInfoEx 结构体（内部使用）"""
        _fields_ = [
            ("cbSize", ctypes.c_ulong),
            ("rcMonitor", ctypes.c_int * 4),
            ("rcWork", ctypes.c_int * 4),
            ("dwFlags", ctypes.c_ulong),
            ("szDevice", ctypes.c_char * 32),
        ]

    EXCLUDED_CLASSES = {
        "Progman",
        "WorkerW",
        "Shell_TrayWnd",
        "Button",
        "tooltips_class32",
        "MSCTFIME UI",
        "IME",
        "OleMainThreadWndClass",
    }
    EXCLUDED_TITLES = {"", "Program Manager", "Settings"}

    @staticmethod
    @win32_error_handler(default=False, log_level="debug")
    def is_window(hwnd: int) -> bool:
        """检查句柄是否为有效的窗口

        参数:
            hwnd: int - 窗口句柄

        返回:
            bool - 是否为有效窗口
        """
        if not WIN32_AVAILABLE:
            return False
        return bool(win32gui.IsWindow(hwnd))

    @staticmethod
    @win32_error_handler(default=False, log_level="debug")
    def is_window_visible(hwnd: int) -> bool:
        """检查窗口是否可见

        参数:
            hwnd: int - 窗口句柄

        返回:
            bool - 窗口是否可见
        """
        if not WIN32_AVAILABLE:
            return False
        return bool(win32gui.IsWindowVisible(hwnd))

    @staticmethod
    @win32_error_handler(default=False, log_level="debug")
    def window_has_visible_style(hwnd: int) -> bool:
        """通过窗口样式位检查 WS_VISIBLE（与 AHK WinHide/WinShow 一致）

        直接读取 GWL_STYLE 并检查 WS_VISIBLE (0x10000000) 位，
        这与 AutoHotkey 的 WinHide/WinShow 和 Win32 API ShowWindow
        的行为完全一致。

        参数:
            hwnd: int - 窗口句柄

        返回:
            bool - True 表示 WS_VISIBLE 样式位存在（窗口可见），
                   False 表示被 WinHide 隐藏
        """
        if not WIN32_AVAILABLE:
            return True
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        return bool(style & 0x10000000)

    @staticmethod
    @win32_error_handler(default="", log_level="debug")
    def get_window_text(hwnd: int) -> str:
        """获取窗口标题

        参数:
            hwnd: int - 窗口句柄

        返回:
            str - 窗口标题
        """
        if not WIN32_AVAILABLE:
            return ""
        return win32gui.GetWindowText(hwnd)

    @staticmethod
    @win32_error_handler(default="", log_level="debug")
    def get_window_class(hwnd: int) -> str:
        """获取窗口类名

        参数:
            hwnd: int - 窗口句柄

        返回:
            str - 窗口类名
        """
        if not WIN32_AVAILABLE:
            return ""
        return win32gui.GetClassName(hwnd)

    @staticmethod
    @win32_error_handler(default=(0, 0), log_level="debug")
    def get_window_thread_process_id(hwnd: int) -> Tuple[int, int]:
        """获取窗口的线程ID和进程ID

        参数:
            hwnd: int - 窗口句柄

        返回:
            Tuple[int, int] - (线程ID, 进程ID)
        """
        if not WIN32_AVAILABLE:
            return (0, 0)
        return win32process.GetWindowThreadProcessId(hwnd)

    @staticmethod
    @win32_error_handler(default=False, log_level="debug")
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
        return bool(win32gui.ShowWindow(hwnd, cmd))

    @staticmethod
    @win32_error_handler(default=False, log_level="debug")
    def set_foreground_window(hwnd: int) -> bool:
        """将窗口设置为前台窗口

        参数:
            hwnd: int - 窗口句柄

        返回:
            bool - 操作是否成功
        """
        if not WIN32_AVAILABLE:
            return False
        win32gui.SetForegroundWindow(hwnd)
        return True

    @staticmethod
    def enum_windows() -> List[int]:
        """枚举所有窗口

        排除系统窗口和空标题窗口，只返回有效的应用窗口
        包含所有显示器上的窗口，包括后台窗口

        返回:
            List[int] - 窗口句柄列表
        """
        if not WIN32_AVAILABLE:
            return []
        windows = []

        # 预编译排除列表，提高查找速度
        excluded_classes = SafeWindowsAPI.EXCLUDED_CLASSES
        excluded_titles = SafeWindowsAPI.EXCLUDED_TITLES

        def callback(hwnd, _):
            try:
                # 检查窗口是否有效
                if not SafeWindowsAPI.is_window(hwnd):
                    return True

                # 排除子窗口，只关注顶级窗口
                if win32gui.GetParent(hwnd) != 0:
                    return True

                # 获取窗口类名和标题
                class_name = SafeWindowsAPI.get_window_class(hwnd)
                title = SafeWindowsAPI.get_window_text(hwnd)

                # 快速检查排除列表
                if class_name in excluded_classes:
                    return True
                if title in excluded_titles:
                    return True
                if not title:
                    return True

                # 使用 WS_VISIBLE 样式位判断可见性
                style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
                if not (style & win32con.WS_VISIBLE):
                    return True

                windows.append(hwnd)
            except Exception as e:
                logger.debug("enum_windows 回调出错: %s", str(e))
                # 继续枚举其他窗口
                pass
            return True

        try:
            win32gui.EnumWindows(callback, None)
        except Exception as e:
            logger.debug("enum_windows 出错: %s", str(e))
            # 返回已枚举的窗口列表
            pass
        return windows

    @staticmethod
    @win32_error_handler(default=None, log_level="debug")
    def get_window_rect(hwnd: int) -> Optional[Tuple[int, int, int, int]]:
        """获取窗口矩形区域

        参数:
            hwnd: int - 窗口句柄

        返回:
            Optional[Tuple[int, int, int, int]] - (left, top, right, bottom) 或 None
        """
        if not WIN32_AVAILABLE:
            return None
        return win32gui.GetWindowRect(hwnd)

    # 进程名称缓存
    _process_name_cache: Dict[int, tuple] = {}  # (process_name, timestamp)
    _cache_lock = threading.RLock()
    _cache_timeout = 300  # 缓存过期时间（秒）
    _max_cache_size = 1000  # 缓存最大条目数
    _last_cleanup_time: float = 0  # 上次清理时间戳
    _cleanup_interval = 60  # 清理节流间隔（秒）

    @staticmethod
    def clear_process_name_cache() -> None:
        """清空进程名称缓存"""
        with SafeWindowsAPI._cache_lock:
            SafeWindowsAPI._process_name_cache.clear()
            logger.debug("进程名称缓存已清空")

    @staticmethod
    def _cleanup_expired_cache() -> None:
        """清理过期缓存条目"""
        import time

        current_time = time.time()

        with SafeWindowsAPI._cache_lock:
            expired_keys = [
                pid
                for pid, (_, timestamp) in SafeWindowsAPI._process_name_cache.items()
                if current_time - timestamp >= SafeWindowsAPI._cache_timeout
            ]
            for pid in expired_keys:
                del SafeWindowsAPI._process_name_cache[pid]

            # 如果缓存仍然过大，清理最老的条目
            if len(SafeWindowsAPI._process_name_cache) > SafeWindowsAPI._max_cache_size:
                sorted_items = sorted(
                    SafeWindowsAPI._process_name_cache.items(), key=lambda x: x[1][1]
                )
                for pid, _ in sorted_items[: len(sorted_items) // 2]:
                    del SafeWindowsAPI._process_name_cache[pid]
                logger.debug("进程名称缓存已清理，过期和多余条目已移除")

    @staticmethod
    def create_window_info(
        hwnd_or_params,
        title: Optional[str] = None,
        class_name: Optional[str] = None,
        pid: Optional[int] = None,
        state: WindowState = WindowState.NORMAL,
        is_visible: bool = True,
        is_foreground: bool = False,
        monitor_id: Optional[int] = None,
        monitor_name: str = "",
        process_name: Optional[str] = None,
        is_taskbar: Optional[bool] = None,
    ) -> WindowInfo:
        """统一的 WindowInfo 构造方法，减少重复代码
        
        支持两种调用方式：
            1. 传统参数方式：create_window_info(hwnd, title=..., ...)
            2. 参数对象方式：create_window_info(params)
        
        参数:
            hwnd_or_params: int 或 WindowInfoParams - 窗口句柄或参数对象
            title: Optional[str] - 窗口标题，默认自动获取
            class_name: Optional[str] - 窗口类名，默认自动获取
            pid: Optional[int] - 进程ID，默认自动获取
            state: WindowState - 窗口状态，默认 NORMAL
            is_visible: bool - 窗口是否可见，默认 True
            is_foreground: bool - 是否为前台窗口，默认 False
            monitor_id: Optional[int] - 窗口所在显示器ID
            monitor_name: str - 窗口所在显示器名称
            process_name: Optional[str] - 进程名称，默认自动获取
            is_taskbar: Optional[bool] - 是否在任务栏显示，默认 None（未分类）

        返回:
            WindowInfo - 窗口信息对象
        """
        # 处理参数对象方式
        if isinstance(hwnd_or_params, WindowInfoParams):
            params = hwnd_or_params
            return SafeWindowsAPI.create_window_info(
                hwnd=params.hwnd,
                title=params.title,
                class_name=params.class_name,
                pid=params.pid,
                state=params.state,
                is_visible=params.is_visible,
                is_foreground=params.is_foreground,
                monitor_id=params.monitor_id,
                monitor_name=params.monitor_name,
                process_name=params.process_name,
                is_taskbar=params.is_taskbar,
            )
        
        # 处理传统参数方式
        hwnd = hwnd_or_params
        title = title or SafeWindowsAPI.get_window_text(hwnd)
        class_name = class_name or SafeWindowsAPI.get_window_class(hwnd)
        if pid is None:
            _, pid = SafeWindowsAPI.get_window_thread_process_id(hwnd)
        if process_name is None:
            process_name = SafeWindowsAPI.get_process_name(pid)
        return WindowInfo(
            hwnd=hwnd,
            title=title,
            class_name=class_name,
            pid=pid,
            state=state,
            is_visible=is_visible,
            process_name=process_name,
            is_foreground=is_foreground,
            monitor_id=monitor_id,
            monitor_name=monitor_name,
            is_taskbar=is_taskbar,
        )

    @staticmethod
    def get_process_name(pid: int) -> str:
        """获取进程名称

        参数:
            pid: int - 进程ID

        返回:
            str - 进程名称
        """
        if pid <= 0:
            return "unknown"

        import time

        current_time = time.time()

        # 定期清理过期缓存（节流：每 60 秒最多清理一次）
        if current_time - SafeWindowsAPI._last_cleanup_time >= SafeWindowsAPI._cleanup_interval:
            SafeWindowsAPI._cleanup_expired_cache()
            SafeWindowsAPI._last_cleanup_time = current_time

        # 检查缓存
        with SafeWindowsAPI._cache_lock:
            if pid in SafeWindowsAPI._process_name_cache:
                process_name, timestamp = SafeWindowsAPI._process_name_cache[pid]
                # 检查缓存是否过期
                if current_time - timestamp < SafeWindowsAPI._cache_timeout:
                    return process_name

        process_name = "unknown"

        # 优先使用 psutil（更可靠）
        if PSUTIL_AVAILABLE and psutil is not None:
            try:
                process = psutil.Process(pid)
                process_name = process.name()
            except Exception as e:
                logger.debug("get_process_name (psutil) 出错: %s", str(e))

        # 备选方案：使用 win32 API
        if process_name == "unknown" and WIN32_AVAILABLE:
            try:
                handle = win32api.OpenProcess(
                    win32con.PROCESS_QUERY_INFORMATION, False, pid)
                if handle:
                    try:
                        module_name = win32process.GetModuleFileNameEx(
                            handle, 0)
                        process_name = os.path.basename(module_name)
                    finally:
                        win32api.CloseHandle(handle)
            except Exception as e:
                logger.debug("get_process_name (win32) 出错: %s", str(e))

        # 更新缓存
        with SafeWindowsAPI._cache_lock:
            SafeWindowsAPI._process_name_cache[pid] = (
                process_name, current_time)

        return process_name

    @staticmethod
    @win32_error_handler(default=None, log_level="debug")
    def get_foreground_window() -> Optional[int]:
        """获取当前前台窗口

        返回:
            Optional[int] - 前台窗口句柄或 None
        """
        if not WIN32_AVAILABLE:
            return None
        return win32gui.GetForegroundWindow()

    @staticmethod
    @win32_error_handler(default=None, log_level="debug")
    def get_window_placement(hwnd: int) -> Optional[object]:
        """获取窗口放置信息

        参数:
            hwnd: int - 窗口句柄

        返回:
            Optional[object] - 窗口放置信息对象或 None
        """
        if not WIN32_AVAILABLE:
            return None
        return win32gui.GetWindowPlacement(hwnd)

    @staticmethod
    def get_class_name(hwnd: int) -> str:
        """获取窗口类名（兼容别名）

        .. deprecated::
            请使用 :meth:`get_window_class` 代替

        参数:
            hwnd: int - 窗口句柄

        返回:
            str - 窗口类名
        """
        import warnings

        warnings.warn(
            "get_class_name 已弃用，请使用 get_window_class", DeprecationWarning, stacklevel=2
        )
        return SafeWindowsAPI.get_window_class(hwnd)

    # 显示器信息缓存
    _monitors_cache: Optional[List[MonitorInfo]] = None
    _monitors_last_update: float = 0
    _monitors_cache_timeout = 60  # 缓存超时时间（秒）

    @staticmethod
    def enum_monitors() -> List[MonitorInfo]:
        """枚举所有显示器

        返回:
            List[MonitorInfo] - 显示器信息列表
        """
        import time

        if not WIN32_AVAILABLE:
            return []

        # 检查缓存是否有效
        current_time = time.time()
        if (
            SafeWindowsAPI._monitors_cache is not None
            and current_time - SafeWindowsAPI._monitors_last_update
            < SafeWindowsAPI._monitors_cache_timeout
        ):
            return SafeWindowsAPI._monitors_cache

        monitors = []
        monitor_id = 0

        try:
            # 使用 ctypes 来获取显示器信息，这是一种更可靠的方法
            import ctypes

            def monitor_callback(hmonitor, hdc, lprect, dwData):
                nonlocal monitor_id

                info = SafeWindowsAPI._MONITORINFOEX()
                info.cbSize = ctypes.sizeof(SafeWindowsAPI._MONITORINFOEX)

                if ctypes.windll.user32.GetMonitorInfoA(hmonitor, ctypes.byref(info)):
                    left, top, right, bottom = info.rcMonitor
                    # MONITORINFOF_PRIMARY
                    is_primary = (info.dwFlags & 1) != 0

                    monitor_info = MonitorInfo(
                        monitor_id=monitor_id,
                        left=left,
                        top=top,
                        right=right,
                        bottom=bottom,
                        is_primary=is_primary,
                    )
                    monitors.append(monitor_info)
                    monitor_id += 1

                return True

            # 定义回调函数类型
            MonitorEnumProc = ctypes.WINFUNCTYPE(
                ctypes.c_bool,
                ctypes.c_ulong,
                ctypes.c_ulong,
                ctypes.POINTER(ctypes.c_int * 4),
                ctypes.c_ulong,
            )
            callback = MonitorEnumProc(monitor_callback)

            # 枚举显示器
            ctypes.windll.user32.EnumDisplayMonitors(None, None, callback, 0)

        except Exception as e:
            logger.debug("enum_monitors 出错: %s", str(e))
            # 回退到 win32gui 方法
            try:

                def win32_callback(hmonitor, hdc, rect, data):
                    nonlocal monitor_id
                    left, top, right, bottom = rect

                    # 简单判断主显示器
                    is_primary = left == 0 and top == 0

                    monitor_info = MonitorInfo(
                        monitor_id=monitor_id,
                        left=left,
                        top=top,
                        right=right,
                        bottom=bottom,
                        is_primary=is_primary,
                    )
                    monitors.append(monitor_info)
                    monitor_id += 1
                    return True

                win32gui.EnumDisplayMonitors(None, None, win32_callback, None)
            except Exception as e2:
                logger.debug("win32gui enum_monitors 出错: %s", str(e2))

        # 更新缓存
        SafeWindowsAPI._monitors_cache = monitors
        SafeWindowsAPI._monitors_last_update = current_time

        return monitors

    @staticmethod
    def get_window_monitor(hwnd: int) -> Optional[MonitorInfo]:
        """获取窗口所在的显示器

        使用 MonitorFromWindow API 获取"覆盖面积最大"的显示器，
        然后使用 GetMonitorInfo 获取显示器详细信息。

        参数:
            hwnd: int - 窗口句柄

        返回:
            Optional[MonitorInfo] - 显示器信息或 None
        """
        logger.debug("get_window_monitor 被调用，hwnd: %d", hwnd)
        if not WIN32_AVAILABLE:
            logger.debug("WIN32_AVAILABLE is False")
            return None

        try:
            logger.debug("Calling MonitorFromWindow for hwnd: %d", hwnd)
            # 使用 ctypes 调用 MonitorFromWindow API
            user32 = ctypes.windll.user32
            MONITOR_DEFAULTTOPRIMARY = 1
            hmonitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTOPRIMARY)

            if not hmonitor:
                logger.debug("MonitorFromWindow 返回无效句柄: %d", hwnd)
                return None
            logger.debug("Got monitor handle: %d", hmonitor)

            logger.debug(
                "Calling GetMonitorInfo for monitor handle: %d", hmonitor)

            # 使用 ctypes 调用 GetMonitorInfo API
            info = SafeWindowsAPI._MONITORINFO()
            info.cbSize = ctypes.sizeof(SafeWindowsAPI._MONITORINFO)
            logger.debug(
                "Calling GetMonitorInfoA with info.cbSize: %d", info.cbSize)
            success = user32.GetMonitorInfoA(hmonitor, ctypes.byref(info))
            logger.debug("GetMonitorInfoA 返回: %s", success)

            is_primary = False
            left, top, right, bottom = 0, 0, 0, 0

            if success:
                # 解析显示器矩形
                left, top, right, bottom = info.rcMonitor
                logger.debug(
                    "Monitor rect: left=%d, top=%d, right=%d, bottom=%d", left, top, right, bottom
                )

                # 判断是否为主显示器：dwFlags & 1 == 1 代表主显示器
                is_primary = (info.dwFlags & 1) == 1
                logger.debug("Monitor flags: %d, is_primary: %s",
                             info.dwFlags, is_primary)
            else:
                # GetMonitorInfo 失败，使用默认值
                logger.debug("GetMonitorInfo 失败，使用默认值")

            # 从缓存的显示器列表中查找匹配项，以获取 monitor_id
            monitors = SafeWindowsAPI.enum_monitors()
            logger.debug("Found %d monitors in enum_monitors", len(monitors))
            monitor_id = 0
            for i, m in enumerate(monitors):
                if m.left == left and m.top == top and m.right == right and m.bottom == bottom:
                    monitor_id = m.monitor_id
                    logger.debug(
                        "Found matching monitor with id: %d", monitor_id)
                    break

            result = MonitorInfo(
                monitor_id=monitor_id,
                left=left,
                top=top,
                right=right,
                bottom=bottom,
                is_primary=is_primary,
            )
            logger.debug("Created MonitorInfo: %s", result)
            return result

        except Exception as e:
            logger.error("get_window_monitor 出错: %s", str(e))
            import traceback

            logger.error("Traceback: %s", traceback.format_exc())
            return None

    @staticmethod
    def is_hwnd_on_primary_screen(hwnd: int) -> bool:
        """判断指定窗口句柄是否在主显示器

        参数:
            hwnd: int - 窗口句柄

        返回:
            bool - 是否在主显示器
        """
        if not WIN32_AVAILABLE:
            return False

        try:
            # 使用 ctypes 调用 MonitorFromWindow API
            user32 = ctypes.windll.user32
            MONITOR_DEFAULTTONEAREST = 2
            hmonitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)

            if not hmonitor:
                return False

            # 使用 ctypes 调用 GetMonitorInfo API
            info = SafeWindowsAPI._MONITORINFO()
            info.cbSize = ctypes.sizeof(SafeWindowsAPI._MONITORINFO)
            if not user32.GetMonitorInfoA(hmonitor, ctypes.byref(info)):
                return False

            # 标志位 1 = 主显示器
            return (info.dwFlags & 1) == 1

        except Exception as e:
            logger.debug("is_hwnd_on_primary_screen 出错: %s", str(e))
            return False

    @staticmethod
    @win32_error_handler(default=False, log_level="debug")
    def is_alt_tab_window(hwnd: int) -> bool:
        """判断窗口是否能被ALT+TAB切换（核心判定逻辑）

        参数:
            hwnd: int - 窗口句柄

        返回:
            bool - 是否为ALT+TAB可见窗口
        """
        if not WIN32_AVAILABLE:
            return False

        try:
            # 1. 排除隐藏窗口（WS_VISIBLE标记必须存在）
            if not win32gui.IsWindowVisible(hwnd):
                return False

            # 2. 排除工具窗口（工具窗口不会出现在ALT+TAB列表中）
            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            if ex_style & win32con.WS_EX_TOOLWINDOW:
                return False

            # 3. 排除无标题的窗口（ALT+TAB不显示无标题的系统/后台窗口）
            window_title = win32gui.GetWindowText(hwnd)
            if not window_title.strip():
                return False

            # 4. 排除子窗口（只保留顶级窗口）
            if win32gui.GetParent(hwnd) != 0:
                return False

            return True
        except Exception as e:
            logger.debug("is_alt_tab_window 出错: %s", str(e))
            return False

    @staticmethod
    @win32_error_handler(default=False, log_level="debug")
    def is_taskbar_window(hwnd: int) -> bool:
        """检查窗口是否在任务栏中显示

        参数:
            hwnd: int - 窗口句柄

        返回:
            bool - 是否为任务栏窗口
        """
        # 现在使用ALT+TAB可见窗口的判断逻辑
        return SafeWindowsAPI.is_alt_tab_window(hwnd)

    @staticmethod
    def enum_hidden_windows() -> List[int]:
        """枚举被 SW_HIDE 隐藏但窗口句柄仍然有效的窗口

        用于程序启动时扫描上次运行中被隐藏但未恢复的窗口。
        这些窗口的 WS_VISIBLE 样式位被清除，但进程仍在运行。

        排除规则：
        - 系统窗口类（同 EXCLUDED_CLASSES）
        - 无标题窗口
        - 窗口大小太小的窗口
        - 子窗口（非顶级窗口）

        返回:
            List[int] - 隐藏窗口的句柄列表
        """
        if not WIN32_AVAILABLE:
            return []

        hidden_windows = []
        excluded_classes = SafeWindowsAPI.EXCLUDED_CLASSES

        def callback(hwnd, _):
            try:
                if not SafeWindowsAPI.is_window(hwnd):
                    return True

                # 通过 WS_VISIBLE 样式位检查（与 AHK WinHide 一致）
                if SafeWindowsAPI.window_has_visible_style(hwnd):
                    return True

                # 排除子窗口，只关注顶级窗口
                if win32gui.GetParent(hwnd) != 0:
                    return True

                # 获取窗口信息
                class_name = SafeWindowsAPI.get_window_class(hwnd)
                title = SafeWindowsAPI.get_window_text(hwnd)

                # 排除系统窗口类
                if class_name in excluded_classes:
                    return True

                # 排除无标题窗口
                if not title or not title.strip():
                    return True

                # 注意：不检查窗口尺寸，因为被 SW_HIDE 的窗口
                # GetWindowRect 返回 0x0，不能作为有效判断依据

                hidden_windows.append(hwnd)
            except Exception as e:
                logger.debug("enum_hidden_windows 回调出错: %s", str(e))
            return True

        try:
            win32gui.EnumWindows(callback, None)
        except Exception as e:
            logger.debug("enum_hidden_windows 出错: %s", str(e))

        logger.info("扫描到 %d 个被隐藏的窗口", len(hidden_windows))
        return hidden_windows

    @staticmethod
    def get_total_window_count() -> int:
        """获取系统中的窗口总数（用于进度条分母）

        Returns:
            int - 顶级窗口数量
        """
        if not WIN32_AVAILABLE:
            return 0
        count = [0]

        def callback(hwnd, _):
            count[0] += 1
            return True

        try:
            win32gui.EnumWindows(callback, None)
        except Exception:
            pass
        return count[0]

    @staticmethod
    def enum_hidden_windows_for_processes(
        process_names: List[str] = None,
        pids: List[int] = None,
    ) -> List[dict]:
        """枚举指定进程中被 WinHide (SW_HIDE) 隐藏的窗口

        优化策略（参考 AHK 检测模式）：
        1. 先通过 psutil 或用户输入收集目标 PID 集合
        2. 单次 EnumWindows 遍历，在回调中：
           - 快速过滤：无效窗口 → 子窗口 → 无标题 → 系统类
           - 获取 PID 匹配目标集合（O(1) 查找）
           - 用 GetWindowLong + WS_VISIBLE 样式位判断是否被隐藏
        3. 毫秒级完成，只做目标进程的精确扫描

        参数:
            process_names: 进程名列表（不区分大小写），如 ["book.exe", "workbuddy.exe"]
            pids: PID 列表，如 [12024, 12345]

        返回:
            List[dict] - 每项包含 hwnd, title, class_name, pid, process_name, is_visible, rect
        """
        if not WIN32_AVAILABLE:
            return []

        # 1. 收集目标 PID
        target_pids = set()

        # 从 PID 列表添加
        if pids:
            target_pids.update(pids)

        # 从进程名查找 PID
        if process_names:
            name_lower_set = {name.lower()
                              for name in process_names if name.strip()}
            if name_lower_set and PSUTIL_AVAILABLE and psutil is not None:
                try:
                    for proc in psutil.process_iter(["pid", "name"]):
                        try:
                            proc_name = proc.info["name"]
                            if proc_name and proc_name.lower() in name_lower_set:
                                target_pids.add(proc.info["pid"])
                        except (
                            psutil.NoSuchProcess,
                            psutil.AccessDenied,
                            psutil.ZombieProcess,
                        ):
                            continue
                except Exception as e:
                    logger.debug(
                        "enum_hidden_windows_for_processes psutil 遍历出错: %s", str(e))

        if not target_pids:
            logger.info("未找到匹配的进程或 PID")
            return []

        logger.info(
            "指定进程扫描：目标 PID %s",
            sorted(target_pids),
        )

        # 2. 单次 EnumWindows 遍历
        results = []
        excluded_classes = SafeWindowsAPI.EXCLUDED_CLASSES

        def callback(hwnd, _):
            try:
                if not win32gui.IsWindow(hwnd):
                    return True

                # 排除子窗口，只关注顶级窗口
                if win32gui.GetParent(hwnd) != 0:
                    return True

                # 快速获取标题过滤无标题窗口（减少后续 Win32 调用）
                title = win32gui.GetWindowText(hwnd)
                if not title or not title.strip():
                    return True

                # 快速获取类名过滤系统窗口
                class_name = win32gui.GetClassName(hwnd)
                if class_name in excluded_classes:
                    return True

                # 获取 PID，O(1) 检查是否在目标集合中
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid not in target_pids:
                    return True

                # 通过 WS_VISIBLE 样式位判断可见性（与 AHK WinHide 一致）
                style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
                is_visible = bool(style & 0x10000000)

                # 获取进程名
                process_name = SafeWindowsAPI.get_process_name(
                    pid) if pid else "unknown"

                # 获取窗口位置
                rect = SafeWindowsAPI.get_window_rect(hwnd)

                results.append(
                    {
                        "hwnd": hwnd,
                        "title": title,
                        "class_name": class_name,
                        "pid": pid,
                        "process_name": process_name,
                        "is_visible": is_visible,
                        "rect": rect,
                    }
                )
            except Exception as e:
                logger.debug(
                    "enum_hidden_windows_for_processes 回调出错: %s", str(e))
            return True

        try:
            win32gui.EnumWindows(callback, None)
        except Exception as e:
            logger.debug("enum_hidden_windows_for_processes 出错: %s", str(e))

        # 统计隐藏窗口数量
        hidden_count = sum(1 for r in results if not r["is_visible"])
        logger.info(
            "指定进程扫描完成：目标 PID %d 个，发现 %d 个窗口（其中 %d 个被隐藏）",
            len(target_pids),
            len(results),
            hidden_count,
        )
        return results

    @staticmethod
    def enum_hidden_windows_progress(
        on_progress=None,
        cancel_event=None,
    ) -> List[dict]:
        """枚举被 SW_HIDE 隐藏的窗口（带进度回调）

        参数:
            on_progress: 进度回调函数 on_progress(current, total, hwnd, title)
            cancel_event: threading.Event，设置后取消扫描

        返回:
            List[dict] - 每项包含 hwnd, title, class_name, pid, process_name, rect
        """
        if not WIN32_AVAILABLE:
            return []

        results = []
        excluded_classes = SafeWindowsAPI.EXCLUDED_CLASSES
        total = [0]
        checked = [0]

        def callback(hwnd, _):
            if cancel_event and cancel_event.is_set():
                return False  # 停止枚举

            total[0] += 1
            checked[0] += 1

            try:
                # 快速过滤：有效 + 不可见 + 顶级
                if not SafeWindowsAPI.is_window(hwnd):
                    if on_progress:
                        on_progress(checked[0], total[0], hwnd, "")
                    return True

                if SafeWindowsAPI.window_has_visible_style(hwnd):
                    if on_progress:
                        on_progress(checked[0], total[0], hwnd, "")
                    return True

                if win32gui.GetParent(hwnd) != 0:
                    if on_progress:
                        on_progress(checked[0], total[0], hwnd, "")
                    return True

                class_name = SafeWindowsAPI.get_window_class(hwnd)
                title = SafeWindowsAPI.get_window_text(hwnd)

                if class_name in excluded_classes:
                    if on_progress:
                        on_progress(checked[0], total[0], hwnd, "")
                    return True

                if not title or not title.strip():
                    if on_progress:
                        on_progress(checked[0], total[0], hwnd, "")
                    return True

                # 获取进程信息
                _, pid = SafeWindowsAPI.get_window_thread_process_id(hwnd)
                process_name = SafeWindowsAPI.get_process_name(
                    pid) if pid else "unknown"

                # 获取窗口位置（隐藏的窗口返回 0x0）
                rect = SafeWindowsAPI.get_window_rect(hwnd)

                results.append(
                    {
                        "hwnd": hwnd,
                        "title": title,
                        "class_name": class_name,
                        "pid": pid,
                        "process_name": process_name,
                        "rect": rect,
                    }
                )

                if on_progress:
                    on_progress(checked[0], total[0], hwnd, title)

            except Exception as e:
                logger.debug("enum_hidden_windows_progress 回调出错: %s", str(e))
                if on_progress:
                    on_progress(checked[0], total[0], hwnd, "")

            return True

        try:
            win32gui.EnumWindows(callback, None)
        except Exception as e:
            logger.debug("enum_hidden_windows_progress 出错: %s", str(e))

        logger.info(
            "进度扫描完成：检查 %d 个窗口，发现 %d 个被隐藏的窗口",
            total[0],
            len(results),
        )
        return results
