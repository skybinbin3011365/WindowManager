# -*- coding: utf-8 -*-
# windowmanager/manager.py
"""
窗口管理器模块

协调窗口操作、进程检测和缓存管理功能
"""

import threading
import logging
from typing import Dict, List, Optional, Set

from window_base import WindowState, WindowInfo
from window_operations import WindowOperator
from process_detector import ProcessDetector
from cache_manager import CacheManager
from deps import psutil, win32con

logger = logging.getLogger(__name__)


class WindowManager:
    """窗口管理器类

    协调窗口操作、进程检测和缓存管理功能
    """

    def __init__(self):
        """初始化窗口管理器"""
        self._lock = threading.RLock()

        self._windows: Dict[int, WindowInfo] = {}
        self._hidden_windows: Dict[int, WindowInfo] = {}
        self._software_hidden_windows: Set[int] = set()
        self._running: bool = False

        self._cache_manager = CacheManager()
        self._window_operator = WindowOperator()
        self._process_detector = ProcessDetector()

        self._setup_data_references()

        self._cache_manager.load_cache()

    def _setup_data_references(self) -> None:
        """设置数据引用，让子模块共享数据存储"""
        self._window_operator.set_data_stores(
            self._windows,
            self._hidden_windows,
            self._software_hidden_windows,
            self._lock
        )
        self._process_detector.set_data_stores(
            {},
            self._hidden_windows
        )

    @property
    def is_running(self) -> bool:
        """检查窗口管理器是否正在运行

        Returns:
            bool: 运行状态
        """
        return self._running

    @property
    def windows(self) -> List[WindowInfo]:
        """获取所有窗口列表（只读）

        Returns:
            List[WindowInfo]: 窗口信息列表
        """
        with self._lock:
            return list(self._windows.values())

    def init_cache(self) -> None:
        """初始化缓存（向后兼容方法）"""
        self._cache_manager.load_cache()

    def start(self) -> None:
        """启动窗口管理器"""
        self._running = True
        self.init_cache()
        self.refresh_windows()
        logger.info("窗口管理器已启动")

    def stop(self) -> None:
        """停止窗口管理器"""
        self._running = False
        logger.info("窗口管理器已停止")

    def refresh_windows(self) -> List[WindowInfo]:
        """刷新窗口列表

        Returns:
            List[WindowInfo]: 窗口信息列表
        """
        from core import SafeWindowsAPI

        with self._lock:
            foreground_windows = self.scan_visible_processes()
            foreground_hwnd = SafeWindowsAPI.get_foreground_window()

            foreground_hwnds = {win.hwnd for win in foreground_windows}
            previous_hwnds = set(self._windows.keys()) | set(self._hidden_windows.keys())

            added_hwnds = foreground_hwnds - previous_hwnds
            removed_hwnds = previous_hwnds - foreground_hwnds

            for hwnd in removed_hwnds:
                # 对于被软件隐藏的窗口，保留其信息
                if hwnd in self._software_hidden_windows:
                    window = self._hidden_windows.get(hwnd)
                    if window and window.pid:
                        try:
                            if psutil and psutil.pid_exists(window.pid):
                                # 进程仍在运行，保留窗口信息
                                continue
                        except Exception:
                            pass
                    # 进程不存在，移除被软件隐藏的窗口
                    logger.debug("进程不存在，移除被软件隐藏的窗口: %d", hwnd)
                    if hwnd in self._software_hidden_windows:
                        self._software_hidden_windows.remove(hwnd)
                    if hwnd in self._hidden_windows:
                        del self._hidden_windows[hwnd]
                else:
                    # 不是被软件隐藏的窗口，正常删除
                    if hwnd in self._windows:
                        del self._windows[hwnd]
                    if hwnd in self._hidden_windows:
                        del self._hidden_windows[hwnd]

            for win in foreground_windows:
                if win.hwnd in added_hwnds:
                    self._add_new_window(win.hwnd, foreground_hwnd)
                else:
                    self._window_operator.update_window_state(win.hwnd, foreground_hwnd)

            logger.info(
                "已刷新 %d 个窗口, %d 个隐藏",
                len(self._windows),
                len(self._hidden_windows),
            )
            return list(self._windows.values())

    def _add_new_window(self, hwnd: int, foreground_hwnd: int) -> None:
        """添加新窗口

        Args:
            hwnd: 窗口句柄
            foreground_hwnd: 前台窗口句柄
        """
        from core import SafeWindowsAPI
        from window_base import WindowState

        try:
            title = SafeWindowsAPI.get_window_text(hwnd)
            class_name = SafeWindowsAPI.get_window_class(hwnd)
            is_visible = SafeWindowsAPI.window_has_visible_style(hwnd)

            _, pid = SafeWindowsAPI.get_window_thread_process_id(hwnd)
            process_name = SafeWindowsAPI.get_process_name(pid)

            if is_visible:
                state = WindowState.NORMAL
                placement = SafeWindowsAPI.get_window_placement(hwnd)
                if placement and placement[0] == win32con.SW_SHOWMINIMIZED:
                    state = WindowState.MINIMIZED

                monitor = SafeWindowsAPI.get_window_monitor(hwnd)
                monitor_id = monitor.monitor_id if monitor else None
                if monitor:
                    monitor_name = "主显" if monitor.is_primary else "副显"
                else:
                    monitor_name = "未知显示器"

                win_info = SafeWindowsAPI.create_window_info(
                    hwnd,
                    title=title,
                    class_name=class_name,
                    pid=pid,
                    state=state,
                    is_visible=True,
                    process_name=process_name,
                    is_foreground=(hwnd == foreground_hwnd),
                    monitor_id=monitor_id,
                    monitor_name=monitor_name,
                )
                self._windows[hwnd] = win_info
            else:
                win_info = SafeWindowsAPI.create_window_info(
                    hwnd,
                    title=title,
                    class_name=class_name,
                    pid=pid,
                    state=WindowState.HIDDEN,
                    is_visible=False,
                    process_name=process_name,
                    is_foreground=False,
                    monitor_id=None,
                    monitor_name="未知显示器",
                )
                self._hidden_windows[hwnd] = win_info
        except Exception as e:
            logger.debug("获取窗口 %d 信息失败: %s", hwnd, str(e))

    def scan_visible_processes(self) -> List[WindowInfo]:
        """增量扫描可见进程窗口，避免全量扫描

        Win32 API 调用（EnumWindows）在锁外执行，避免长时间持锁阻塞其他线程。

        Returns:
            List[WindowInfo]: 前台窗口列表
        """
        foreground_windows: List[WindowInfo] = []

        try:
            all_procs = list(psutil.process_iter(["pid", "name"]))
        except Exception as e:
            logger.warning("获取进程列表失败：%s", e)
            return foreground_windows

        with self._lock:
            hidden_hwnds = set(self._hidden_windows.keys())

        for proc in all_procs:
            try:
                pname = proc.info["name"].lower()
                pid = proc.info["pid"]

                is_fore, hwnds = self._process_detector.get_process_visible_hwnds(pid, pname)

                if not is_fore:
                    continue

                for hwnd in hwnds:
                    if hwnd in hidden_hwnds:
                        continue

                    existing = self._windows.get(hwnd)
                    # hwnd是主键，process_name仅用于验证（避免hwnd被系统复用后指向错误进程的窗口）
                    if existing and existing.process_name.lower() == pname:
                        foreground_windows.append(existing)
                        continue

                    try:
                        win_info = self._create_window_info(hwnd, pid, proc.info["name"])
                        foreground_windows.append(win_info)
                    except Exception as e:
                        logger.debug("创建窗口信息失败: %s", e)

            except Exception:
                continue

        return foreground_windows

    def _create_window_info(self, hwnd: int, pid: int, name: str) -> "WindowInfo":
        """创建窗口信息对象

        Args:
            hwnd: 窗口句柄
            pid: 进程ID
            name: 进程名

        Returns:
            WindowInfo: 窗口信息对象
        """
        from core import SafeWindowsAPI

        title = SafeWindowsAPI.get_window_text(hwnd)
        class_name = SafeWindowsAPI.get_window_class(hwnd)
        return SafeWindowsAPI.create_window_info(
            hwnd,
            title=title,
            class_name=class_name,
            pid=pid,
            state=WindowState.NORMAL,
            is_visible=True,
            process_name=name,
            is_foreground=False,
        )

    def get_all_windows(self) -> List[WindowInfo]:
        """获取所有窗口列表

        Returns:
            List[WindowInfo]: 窗口信息列表（包括可见和隐藏的窗口）
        """
        with self._lock:
            all_windows = list(self._windows.values()) + list(self._hidden_windows.values())
            return all_windows

    def get_window(self, hwnd: int) -> Optional[WindowInfo]:
        """获取指定窗口信息

        Args:
            hwnd: 窗口句柄

        Returns:
            Optional[WindowInfo]: 窗口信息对象或None
        """
        with self._lock:
            return self._windows.get(hwnd) or self._hidden_windows.get(hwnd)

    def get_hidden_windows(self) -> List[WindowInfo]:
        """获取被软件隐藏的窗口列表

        Returns:
            List[WindowInfo]: 隐藏窗口列表
        """
        with self._lock:
            return [
                self._hidden_windows[hwnd]
                for hwnd in self._software_hidden_windows
                if hwnd in self._hidden_windows
            ]

    def set_software_hidden_windows(self, hwnds: List[int]) -> None:
        """设置被软件隐藏的窗口列表

        Args:
            hwnds: 窗口句柄列表
        """
        with self._lock:
            self._software_hidden_windows = set(hwnds)

    def get_software_hidden_windows(self) -> List[int]:
        """获取被软件隐藏的窗口列表

        Returns:
            List[int]: 窗口句柄列表
        """
        with self._lock:
            return list(self._software_hidden_windows)

    def hide_window(self, hwnd: int) -> bool:
        """隐藏指定的窗口

        Args:
            hwnd: 窗口句柄

        Returns:
            bool: 隐藏成功返回True，否则返回False
        """
        return self._window_operator.hide_window(hwnd)

    def show_window(self, hwnd: int) -> bool:
        """显示指定的窗口

        Args:
            hwnd: 窗口句柄

        Returns:
            bool: 显示成功返回True，否则返回False
        """
        return self._window_operator.show_window(hwnd)

    def show_and_minimize_window(self, hwnd: int) -> bool:
        """显示并最小化指定窗口

        Args:
            hwnd: 窗口句柄

        Returns:
            bool: 操作成功返回True，否则返回False
        """
        return self._window_operator.show_and_minimize_window(hwnd)

    def show_all_hidden_windows(self) -> int:
        """显示所有被软件隐藏的窗口

        Returns:
            int: 成功显示的窗口数量
        """
        return self._window_operator.show_all_hidden_windows()

    def show_selected_hidden_windows(self, hwnds: List[int]) -> int:
        """显示选中的隐藏窗口

        Args:
            hwnds: 要显示的窗口句柄列表

        Returns:
            int: 成功显示的窗口数量
        """
        return self._window_operator.show_selected_hidden_windows(hwnds)

    def show_and_minimize_selected_hidden_windows(self, hwnds: List[int]) -> int:
        """显示并最小化选中的隐藏窗口

        Args:
            hwnds: 要显示的窗口句柄列表

        Returns:
            int: 成功显示的窗口数量
        """
        return self._window_operator.show_and_minimize_selected_hidden_windows(hwnds)

    def restore_windows_by_process(self, process_name: str) -> List[int]:
        """恢复指定进程的所有隐藏窗口

        Args:
            process_name: 进程名，如 "book.exe"

        Returns:
            List[int]: 成功恢复的窗口句柄列表
        """
        with self._lock:
            restored_hwnds = []

            for hwnd in list(self._software_hidden_windows):
                window = self._hidden_windows.get(hwnd)
                # 按进程名匹配（用户请求的是"恢复某某进程的窗口"，所以这里用进程名是合理的）
                # 但底层操作仍使用hwnd作为主键
                if window and window.process_name.lower() == process_name.lower():
                    try:
                        self.show_window(hwnd)
                        restored_hwnds.append(hwnd)
                        logger.info(
                            "恢复进程 '%s' 的窗口: hwnd=%d - '%s'",
                            process_name, hwnd, window.title,
                        )
                    except Exception as e:
                        logger.error("恢复窗口失败 %d: %s", hwnd, str(e))

            return restored_hwnds

    def detect_target_windows(self, keywords: List[str]) -> List[WindowInfo]:
        """检测与关键字相关的目标进程窗口

        Args:
            keywords: 关键字列表

        Returns:
            List[WindowInfo]: 匹配的目标进程窗口列表
        """
        return self._process_detector.detect_target_windows(keywords)

    def get_process_visible_hwnds(self, pid: int, process_name: str) -> tuple[bool, list[int]]:
        """获取单个进程的所有可见窗口句柄

        Args:
            pid: 进程ID
            process_name: 进程名

        Returns:
            tuple[bool, list[int]]:
                - 第一个元素：是否找到该进程的可见窗口
                - 第二个元素：找到的窗口句柄列表
        """
        return self._process_detector.get_process_visible_hwnds(pid, process_name)

    def find_visible_hwnds_by_process_name(self, process_name: str) -> List[int]:
        """通过进程名查找有可见窗口的句柄

        Args:
            process_name: 进程名

        Returns:
            List[int]: 有可见窗口的句柄列表
        """
        return self._process_detector.find_visible_hwnds_by_process_name(process_name)

    def find_all_hwnds_by_process_name(self, process_name: str) -> List[int]:
        """通过进程名查找所有窗口句柄（包括隐藏窗口）

        Args:
            process_name: 进程名

        Returns:
            List[int]: 窗口句柄列表
        """
        return self._process_detector.find_all_hwnds_by_process_name(process_name)

    def switch_to_foreground(self, hwnd: int) -> bool:
        """将窗口切换到前台并最大化

        用于切换窗口功能：恢复可见 → 激活前台 → 最大化
        不管之前什么状态，直接设置为最大化。

        Args:
            hwnd: 窗口句柄

        Returns:
            bool: 操作成功返回True，否则返回False
        """
        return self._window_operator.switch_to_foreground(hwnd)

    def restore_hidden_window(self, hwnd: int) -> bool:
        """恢复被隐藏的窗口（正常显示，SW_SHOW）

        右键菜单"恢复窗口"使用此方法。

        Args:
            hwnd: 窗口句柄

        Returns:
            bool: 恢复成功返回True，否则返回False
        """
        return self._window_operator.show_window(hwnd)

    def switch_windows_by_process_name(self, process_name: str) -> int:
        """根据进程名切换窗口到前台并最大化

        原名 show_windows_by_process_name（实际行为是显示+最小化，已重命名）。

        Args:
            process_name: 进程名

        Returns:
            int: 成功切换的窗口数量
        """
        hwnds = self.find_all_hwnds_by_process_name(process_name)
        if not hwnds:
            return 0

        count = 0
        for hwnd in hwnds:
            if self.switch_to_foreground(hwnd):
                count += 1
        return count

    def show_windows_by_process_name(self, process_name: str) -> int:
        """根据进程名显示并最小化所有窗口（向后兼容）

        注意：此方法行为是"显示并最小化"而非"正常显示"。
        如需切换到前台并最大化，请使用 switch_windows_by_process_name。

        Args:
            process_name: 进程名

        Returns:
            int: 成功显示的窗口数量
        """
        hwnds = self.find_all_hwnds_by_process_name(process_name)
        if not hwnds:
            return 0

        count = 0
        for hwnd in hwnds:
            if self.show_and_minimize_window(hwnd):
                count += 1
        return count

    def get_windows_by_process_name_with_screen_info(
        self, process_name: str
    ) -> List[dict]:
        """根据进程名获取窗口信息，包括是否在主显示器

        Args:
            process_name: 进程名

        Returns:
            List[dict]: 每项包含 hwnd, title, is_primary
        """
        return self._process_detector.get_windows_by_process_name_with_screen_info(process_name)

    def save_cache(self) -> None:
        """保存缓存"""
        self._cache_manager.save_cache()

    def scan_hidden_windows(self) -> Dict[int, WindowInfo]:
        """扫描系统中被 SW_HIDE 隐藏的窗口，更新内部跟踪

        双保险机制：即使配置丢失/损坏，也能通过 EnumWindows + WS_VISIBLE 检测
        发现被上次运行隐藏但未恢复的窗口。

        利用已有的 SafeWindowsAPI.enum_hidden_windows() 实现，只更新属于
        已跟踪进程的隐藏窗口到 _hidden_windows 字典。

        返回:
            Dict[int, WindowInfo]: 本次扫描发现的隐藏窗口 {hwnd: WindowInfo}
        """
        from core import SafeWindowsAPI

        # 收集当前跟踪的所有进程名
        tracked_process_names: set = set()
        with self._lock:
            for win_info in self._hidden_windows.values():
                if win_info.process_name:
                    tracked_process_names.add(win_info.process_name.lower())
            for hwnd in self._software_hidden_windows:
                win_info = self._hidden_windows.get(hwnd)
                if win_info and win_info.process_name:
                    tracked_process_names.add(win_info.process_name.lower())

        if not tracked_process_names:
            logger.debug("scan_hidden_windows: 无已跟踪进程，跳过扫描")
            return {}

        # 利用已有的 enum_hidden_windows_for_processes 精确扫描
        try:
            results = SafeWindowsAPI.enum_hidden_windows_for_processes(
                process_names=list(tracked_process_names)
            )
        except Exception as e:
            logger.debug("scan_hidden_windows 扫描失败: %s", str(e))
            return {}

        if not results:
            return {}

        # 只关注不可见的窗口（is_visible=False 表示被 SW_HIDE）
        discovered: Dict[int, WindowInfo] = {}
        with self._lock:
            for info in results:
                hwnd = info.get("hwnd", 0)
                if not hwnd:
                    continue
                # 跳过已跟踪的窗口
                if hwnd in self._hidden_windows:
                    continue
                # 只处理被隐藏的窗口
                if info.get("is_visible", True):
                    continue
                # 额外验证: is_super_window（排除工具窗口、子窗口等非主窗口）
                if not SafeWindowsAPI.is_super_window(hwnd):
                    continue

                pid = info.get("pid", 0)
                process_name = info.get("process_name", "")
                title = info.get("title", "")

                win_info = WindowInfo.create_hidden(
                    hwnd=hwnd,
                    title=title,
                    process_name=process_name,
                    pid=pid,
                )
                self._hidden_windows[hwnd] = win_info
                # P1-3 修复: 同时加入 _software_hidden_windows，防止下次 refresh 时被清除
                self._software_hidden_windows.add(hwnd)
                discovered[hwnd] = win_info
                logger.info(
                    "scan_hidden_windows 发现未跟踪的隐藏窗口: hwnd=%d, title=%s, process=%s",
                    hwnd, title, process_name,
                )

        if discovered:
            logger.info("scan_hidden_windows 新发现 %d 个未跟踪的隐藏窗口", len(discovered))
        return discovered

    def add_hidden_window(self, hwnd: int, win_info: WindowInfo) -> None:
        """添加隐藏窗口到跟踪集合

        Args:
            hwnd: 窗口句柄
            win_info: 窗口信息
        """
        with self._lock:
            self._hidden_windows[hwnd] = win_info

    def remove_hidden_window(self, hwnd: int) -> bool:
        """从隐藏窗口集合中移除指定窗口

        同时从 _software_hidden_windows 和 _window_operator 中移除。

        Args:
            hwnd: 窗口句柄

        Returns:
            bool: 是否成功移除
        """
        with self._lock:
            removed = False
            if hwnd in self._software_hidden_windows:
                self._software_hidden_windows.remove(hwnd)
                removed = True
            if hwnd in self._hidden_windows:
                del self._hidden_windows[hwnd]
                removed = True
            if hasattr(self, "_window_operator"):
                self._window_operator.remove_from_software_hidden(hwnd)
            return removed

    def remove_hidden_windows(self, hwnds) -> None:
        """批量从隐藏窗口集合中移除窗口

        同时从 _software_hidden_windows 和 _window_operator 中移除。

        Args:
            hwnds: 窗口句柄集合
        """
        with self._lock:
            self._software_hidden_windows -= hwnds
            for hwnd in hwnds:
                self._hidden_windows.pop(hwnd, None)
                self._windows.pop(hwnd, None)
            if hasattr(self, "_window_operator"):
                self._window_operator.remove_batch_from_software_hidden(hwnds)

    def get_hidden_window(self, hwnd: int) -> Optional[WindowInfo]:
        """获取指定隐藏窗口信息

        Args:
            hwnd: 窗口句柄

        Returns:
            Optional[WindowInfo]: 窗口信息或None
        """
        with self._lock:
            return self._hidden_windows.get(hwnd)

    def has_hidden_window(self, hwnd: int) -> bool:
        """检查指定窗口是否在隐藏窗口集合中

        Args:
            hwnd: 窗口句柄

        Returns:
            bool: 是否存在
        """
        with self._lock:
            return hwnd in self._hidden_windows
