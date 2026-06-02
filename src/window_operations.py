# -*- coding: utf-8 -*-
# windowmanager/window_operations.py
"""
窗口操作模块

负责窗口的显示、隐藏、状态更新等操作

从 manager.py 拆分出来的窗口操作逻辑，
通过 set_data_stores() 接收共享数据存储引用。

隐藏/显示逻辑遵循用户需求规范：
1. 只操作顶层窗口（GetParent == 0），不操作子窗口
2. 隐藏时只调用 SW_HIDE，不修改子窗口参数
3. 显示时只调用 SW_SHOW 恢复可见性，不干预窗口位置/尺寸/状态
4. 不对子窗口做任何操作（隐藏时没改过，显示时也不需要改）
"""

import logging
import threading
from typing import Dict, Set, Optional

from deps import WIN32GUI_AVAILABLE, win32con, win32gui
from core import SafeWindowsAPI
from utils import is_admin
from window_base import WindowState, WindowInfo

logger = logging.getLogger(__name__)


class WindowOperator:
    """窗口操作器类

    负责窗口的显示、隐藏、状态更新等操作
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._windows: Dict[int, WindowInfo] = {}
        self._hidden_windows: Dict[int, WindowInfo] = {}
        self._software_hidden_windows: Set[int] = set()
        self._is_admin: bool = is_admin() if WIN32GUI_AVAILABLE else False

    def set_data_stores(
        self,
        windows: Dict[int, WindowInfo],
        hidden_windows: Dict[int, WindowInfo],
        software_hidden_windows: Set[int],
        lock: Optional[threading.RLock] = None,
    ) -> None:
        """设置数据存储引用，让子模块共享数据存储"""
        self._windows = windows
        self._hidden_windows = hidden_windows
        self._software_hidden_windows = software_hidden_windows
        if lock is not None:
            self._lock = lock

    def hide_window(self, hwnd: int) -> bool:
        """隐藏指定的顶层VW窗口

        根据用户需求规范：
        1. 只操作顶层窗口（GetParent == 0），不操作子窗口
        2. 隐藏前保存窗口的精确状态（placement），用于显示时恢复
        3. 只调用 ShowWindow(SW_HIDE) 隐藏顶层窗口，不修改子窗口参数
        4. 子窗口在隐藏前不可见的，恢复后仍不可见
        """
        if not WIN32GUI_AVAILABLE:
            logger.error("核心模块未加载")
            return False

        if not self._is_admin:
            logger.warning("隐藏窗口需要管理员权限，当前权限不足")
            return False

        with self._lock:
            try:
                if win32gui.GetParent(hwnd) != 0:
                    logger.debug("hide_window: 跳过非顶层窗口 hwnd=%d", hwnd)
                    return False

                if not SafeWindowsAPI.is_window(hwnd):
                    logger.debug("hide_window: 窗口句柄无效 hwnd=%d", hwnd)
                    return False

                win_info = self._get_or_create_window_info(hwnd)

                SafeWindowsAPI.show_window(hwnd, win32con.SW_HIDE)

                if not SafeWindowsAPI.is_window_visible(hwnd):
                    win_info.state = WindowState.HIDDEN
                    win_info.is_visible = False
                    self._hidden_windows[hwnd] = win_info
                    if hwnd in self._windows:
                        del self._windows[hwnd]
                    self._software_hidden_windows.add(hwnd)
                    logger.info("已隐藏窗口: %d - %s (%s)", hwnd, win_info.title, win_info.process_name)
                    return True
                logger.warning("隐藏窗口 %d 失败，窗口仍然可见", hwnd)
                return False

            except OSError as e:
                logger.error("隐藏窗口 %d 时发生系统错误: %s", hwnd, str(e))
                return False

    def show_window(self, hwnd: int) -> bool:
        """显示指定的顶层VW窗口

        只使用 SW_SHOW 恢复窗口可见性，不干预窗口位置/尺寸/状态。
        窗口自身决定如何渲染，兼容 Electron/VB6 等非标准窗口。

        根据用户需求规范：
        1. 只操作顶层窗口（GetParent == 0），不操作子窗口
        2. 只调用 ShowWindow(SW_SHOW) 恢复可见性
        3. 不对子窗口做任何操作（隐藏时没改过，显示时也不需要改）
        """
        if not WIN32GUI_AVAILABLE:
            logger.error("核心模块未加载")
            return False

        if not self._is_admin:
            logger.warning("显示窗口需要管理员权限，当前权限不足")
            return False

        with self._lock:
            try:
                if win32gui.GetParent(hwnd) != 0:
                    logger.debug("show_window: 跳过非顶层窗口 hwnd=%d", hwnd)
                    return False

                if not SafeWindowsAPI.is_window(hwnd):
                    logger.debug("show_window: 窗口句柄无效 hwnd=%d", hwnd)
                    return False

                win_info = self._get_or_create_window_info(hwnd)

                # 核心：只使用 SW_SHOW 恢复可见性，不干预窗口位置/尺寸/状态
                SafeWindowsAPI.show_window(hwnd, win32con.SW_SHOW)
                logger.debug("show_window: 使用 SW_SHOW 恢复 hwnd=%d", hwnd)

                if SafeWindowsAPI.is_window_visible(hwnd):
                    self._move_from_hidden_to_visible(hwnd)
                    if hwnd in self._software_hidden_windows:
                        self._software_hidden_windows.remove(hwnd)
                    logger.info("已显示窗口: %d - %s (%s)", hwnd, win_info.title, win_info.process_name)
                    return True
                logger.warning("显示窗口 %d 失败，窗口仍然不可见", hwnd)
                return False

            except OSError as e:
                logger.error("显示窗口 %d 时发生系统错误: %s", hwnd, str(e))
                return False

    def show_and_minimize_window(self, hwnd: int) -> bool:
        """显示并最小化指定顶层窗口

        先恢复窗口可见，再最小化到任务栏。
        用于批量恢复隐藏窗口时，避免所有窗口同时弹出遮挡。
        """
        if not WIN32GUI_AVAILABLE:
            logger.error("核心模块未加载")
            return False

        if not self._is_admin:
            logger.warning("显示并最小化窗口需要管理员权限，当前权限不足")
            return False

        with self._lock:
            win_info = self._hidden_windows.get(hwnd)
            window_title = win_info.title if win_info else f"hwnd={hwnd}"

            try:
                if win32gui.GetParent(hwnd) != 0:
                    logger.debug("show_and_minimize_window: 跳过非顶层窗口 hwnd=%d", hwnd)
                    return False

                if SafeWindowsAPI.is_window_visible(hwnd):
                    logger.debug("窗口 %d 已经可见，直接最小化", hwnd)
                else:
                    # 只使用 SW_SHOW 恢复可见性，不干预窗口位置/尺寸
                    SafeWindowsAPI.show_window(hwnd, win32con.SW_SHOW)

                if SafeWindowsAPI.is_window_visible(hwnd):
                    SafeWindowsAPI.show_window(hwnd, win32con.SW_SHOWMINIMIZED)

                    if win_info:
                        self._update_window_to_minimized(hwnd, win_info)
                        if hwnd in self._software_hidden_windows:
                            self._software_hidden_windows.remove(hwnd)

                    return True
                logger.warning("窗口 %d 在操作后仍然不可见: %s", hwnd, window_title)
                return False
            except OSError as e:
                logger.error("显示并最小化窗口 %d 时发生系统错误: %s", hwnd, str(e))
                return False

    def switch_to_foreground(self, hwnd: int) -> bool:
        """将窗口激活到前台并最大化

        专门用于应对假死(hung)窗口的激活需求：
        1. 尝试激活到前台
        2. 最大化显示
        """
        if not WIN32GUI_AVAILABLE:
            logger.error("核心模块未加载")
            return False

        if not self._is_admin:
            logger.debug("当前非管理员权限，对高权限进程的窗口操作可能失败，但仍尝试执行: hwnd=%d", hwnd)

        with self._lock:
            try:
                if not SafeWindowsAPI.is_window(hwnd):
                    logger.debug("跳过无效窗口句柄: hwnd=%d", hwnd)
                    return False

                if win32gui.GetParent(hwnd) != 0:
                    logger.debug("跳过非顶层窗口: hwnd=%d (有父窗口)", hwnd)
                    return False

                if not SafeWindowsAPI.is_window_visible(hwnd):
                    SafeWindowsAPI.show_window(hwnd, win32con.SW_SHOW)
                    logger.debug("switch_to_foreground: 已恢复窗口可见 hwnd=%d", hwnd)

                try:
                    SafeWindowsAPI.set_foreground_window(hwnd)
                except Exception as e:
                    logger.debug("switch_to_foreground: 激活前台失败 hwnd=%d: %s", hwnd, str(e))

                SafeWindowsAPI.show_window(hwnd, win32con.SW_SHOWMAXIMIZED)
                logger.info("switch_to_foreground: 已激活并最大化窗口 hwnd=%d", hwnd)

                win_info = self._hidden_windows.get(hwnd) or self._windows.get(hwnd)
                if win_info:
                    win_info.state = WindowState.MAXIMIZED
                    win_info.is_visible = True
                    if hwnd in self._hidden_windows:
                        del self._hidden_windows[hwnd]
                    self._windows[hwnd] = win_info
                    if hwnd in self._software_hidden_windows:
                        self._software_hidden_windows.remove(hwnd)

                return True

            except OSError as e:
                logger.error("激活窗口到前台 %d 时发生系统错误: %s", hwnd, str(e))
                return False

    def switch_windows_by_process_name(self, process_name: str) -> int:
        """按进程名激活所有窗口到前台"""
        if not WIN32GUI_AVAILABLE:
            return 0

        count = 0
        with self._lock:
            for hwnd, win_info in list(self._windows.items()):
                if win_info.process_name.lower() == process_name.lower():
                    if self.switch_to_foreground(hwnd):
                        count += 1
                        logger.debug(
                            "switch_windows_by_process_name: 已激活 hwnd=%d - '%s' (%s)",
                            hwnd, win_info.title, win_info.process_name,
                        )
        return count

    def show_all_hidden_windows(self) -> int:
        """显示所有被软件隐藏的窗口"""
        count = 0
        with self._lock:
            for hwnd in list(self._software_hidden_windows):
                if self.show_window(hwnd):
                    count += 1
        return count

    def show_selected_hidden_windows(self, hwnds: list) -> int:
        """显示指定的隐藏窗口列表

        参数:
            hwnds: 要显示的窗口句柄列表

        返回:
            int: 成功显示的窗口数量
        """
        count = 0
        for hwnd in hwnds:
            if self.show_window(hwnd):
                count += 1
        return count

    def show_and_minimize_selected_hidden_windows(self, hwnds: list) -> int:
        """显示并最小化指定的隐藏窗口列表

        参数:
            hwnds: 要显示的窗口句柄列表

        返回:
            int: 成功操作的窗口数量
        """
        count = 0
        for hwnd in hwnds:
            if self.show_and_minimize_window(hwnd):
                count += 1
        return count

    def _get_or_create_window_info(self, hwnd: int) -> WindowInfo:
        """获取或创建窗口信息"""
        if hwnd in self._windows:
            return self._windows[hwnd]
        if hwnd in self._hidden_windows:
            return self._hidden_windows[hwnd]
        title = SafeWindowsAPI.get_window_text(hwnd)
        class_name = SafeWindowsAPI.get_window_class(hwnd)
        _, pid = SafeWindowsAPI.get_window_thread_process_id(hwnd)
        process_name = SafeWindowsAPI.get_process_name(pid)

        return SafeWindowsAPI.create_window_info(
            hwnd,
            title=title,
            class_name=class_name,
            pid=pid,
            state=WindowState.NORMAL,
            is_visible=True,
            process_name=process_name,
            is_foreground=False,
        )

    def _move_from_hidden_to_visible(self, hwnd: int) -> None:
        """将窗口从隐藏列表移动到可见列表"""
        if hwnd not in self._hidden_windows:
            return
        win_info = self._hidden_windows[hwnd]
        win_info.is_visible = SafeWindowsAPI.window_has_visible_style(hwnd)
        self._windows[hwnd] = win_info
        del self._hidden_windows[hwnd]
        logger.debug("窗口 %d 从隐藏列表移除", hwnd)

    def _update_window_to_minimized(self, hwnd: int, win_info: WindowInfo) -> None:
        """更新窗口状态为最小化"""
        win_info.state = WindowState.MINIMIZED
        win_info.is_visible = True

        if hwnd in self._hidden_windows:
            del self._hidden_windows[hwnd]
        self._windows[hwnd] = win_info

        logger.info("成功显示并最小化窗口: %d - %s", hwnd, win_info.title)

    def remove_from_software_hidden(self, hwnd: int) -> None:
        """从软件隐藏窗口集合中移除指定窗口句柄

        Args:
            hwnd: 窗口句柄
        """
        with self._lock:
            self._software_hidden_windows.discard(hwnd)

    def remove_batch_from_software_hidden(self, hwnds) -> None:
        """批量从软件隐藏窗口集合中移除窗口句柄

        Args:
            hwnds: 窗口句柄集合
        """
        with self._lock:
            self._software_hidden_windows -= hwnds

    def update_window_state(self, hwnd: int, foreground_hwnd: int) -> None:
        """更新窗口状态"""
        if hwnd not in self._windows:
            return

        win_info = self._windows[hwnd]
        new_visible = SafeWindowsAPI.window_has_visible_style(hwnd)
        win_info.is_foreground = hwnd == foreground_hwnd

        if win_info.is_visible != new_visible:
            if new_visible:
                if win_info.state == WindowState.HIDDEN:
                    win_info.state = WindowState.NORMAL
            else:
                if win_info.state != WindowState.HIDDEN:
                    win_info.state = WindowState.HIDDEN
                    self._hidden_windows[hwnd] = win_info
                    del self._windows[hwnd]
                    logger.debug("窗口 %d 移动到隐藏列表", hwnd)
                    return

        if new_visible:
            placement = SafeWindowsAPI.get_window_placement(hwnd)
            if placement and placement[0] == win32con.SW_SHOWMINIMIZED:
                win_info.state = WindowState.MINIMIZED
            elif win_info.state == WindowState.MINIMIZED:
                win_info.state = WindowState.NORMAL

        win_info.is_visible = new_visible
