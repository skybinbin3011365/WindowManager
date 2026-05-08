# windowmanager/window_thread.py
"""
窗口刷新线程 - 后台窗口枚举与分类模块
包含 ClassifiedWindows 数据类和 WindowRefreshThread 后台线程类
"""

import logging
import threading
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QThread, Signal

from window_table import WindowTableWidget
from window_base import WindowInfo, WindowState
from config import Config
from window_classifier import WindowClassifier

logger = logging.getLogger(__name__)

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False


@dataclass
class ClassifiedWindows:
    """分类后的窗口列表，避免主线程做 Win32 调用"""

    selected: list  # 选中的窗口
    foreground: list  # 可见窗口（任务栏中可见的，未选中）


class WindowRefreshThread(QThread):
    """窗口刷新线程 - 在后台线程中完成窗口枚举和分类"""

    refresh_finished = Signal(object)  # 传递 ClassifiedWindows
    auto_selected = Signal(int)  # 自动选中的窗口句柄
    hwnd_updated = Signal(int, int)  # 传递 (old_hwnd, new_hwnd) 用于更新选中窗口集合

    def __init__(
        self,
        window_manager,
        selected_windows: set,
        ignored_windows: set,
        process_whitelist: list,
        keywords: list,
        config=None,
    ):
        super().__init__()
        self.window_manager = window_manager
        self._selected_windows = selected_windows
        self._ignored_windows = ignored_windows
        self._process_whitelist = process_whitelist
        self._keywords = keywords
        self.config = config

        # 创建新的窗口分类器
        self.classifier = WindowClassifier()

        # 添加线程锁保护共享数据
        self._lock = threading.RLock()

    def run(self):
        try:
            if not getattr(self.window_manager, "is_running", False):
                logger.warning("窗口管理器未运行，跳过刷新")
                self.refresh_finished.emit(ClassifiedWindows([], []))
                return

            if self.isInterruptionRequested():
                self.refresh_finished.emit(ClassifiedWindows([], []))
                return

            # 先扫描隐藏窗口，确保 _hidden_windows 字典是最新的
            # 这样被 SW_HIDE 隐藏的窗口才能被正确检测
            try:
                if hasattr(self.window_manager, "scan_hidden_windows"):
                    scanned = self.window_manager.scan_hidden_windows()
                    if scanned:
                        logger.debug("刷新线程扫描到 %d 个隐藏窗口", len(scanned))
            except Exception as e:
                logger.debug("刷新线程扫描隐藏窗口失败: %s", str(e))

            # 先获取共享集合的快照，避免在遍历过程中集合被修改导致 RuntimeError
            with self._lock:
                selected_windows_snapshot = set(self._selected_windows)
                ignored_windows_snapshot = set(self._ignored_windows)

            # 使用新的窗口分类器进行窗口分类
            if (
                self.config
                and hasattr(self.config, "enable_window_refresh_log")
                and self.config.enable_window_refresh_log
            ):
                logger.info("使用新的窗口分类器进行分类...")
            apps, background = self.classifier.classify_windows()

            # 合并所有窗口（不再区分前后台，统一显示在可见窗口列表）
            all_windows = apps + background

            if self.isInterruptionRequested():
                self.refresh_finished.emit(ClassifiedWindows([], []))
                return

            # 在后台线程中完成窗口分类（避免主线程 Win32 调用）
            selected_windows = []
            foreground_windows = []

            # 记录已处理的窗口句柄
            processed_hwnds = set()

            # 打印分类结果
            if (
                self.config
                and hasattr(self.config, "enable_window_refresh_log")
                and self.config.enable_window_refresh_log
            ):
                logger.info(
                    "新分类器结果: %d 个应用窗口, %d 个后台进程",
                    len(apps),
                    len(background),
                )

            # 分类窗口到两个列表：选中窗口、可见窗口
            for window in all_windows:
                if window.hwnd in ignored_windows_snapshot:
                    logger.debug("窗口 %d 被忽略", window.hwnd)
                    continue

                processed_hwnds.add(window.hwnd)

                # 对于选中的窗口，无论是否可见，都添加到选中窗口列表
                if window.hwnd in selected_windows_snapshot:
                    selected_windows.append(window)
                    logger.debug("窗口 %d 已在选中列表中", window.hwnd)
                # 检查是否是自动选中的进程窗口（通过进程名，大小写不敏感）
                elif any(
                    process.lower() in window.process_name.lower()
                    for process in getattr(self.config, "auto_select_processes", [])
                ):
                    # 自动选中窗口
                    selected_windows.append(window)
                    # 通过信号通知主线程添加到选中列表
                    self.auto_selected.emit(window.hwnd)
                    logger.debug(
                        "自动选中窗口: %d - %s (%s)",
                        window.hwnd,
                        window.title,
                        window.process_name,
                    )

                # 只显示 is_taskbar=True 的窗口到可见窗口列表
                # 首次检测和增量更新都只添加任务栏窗口
                if window.title.strip() and window.is_taskbar:
                    foreground_windows.append(window)

            # 处理在选中窗口列表但未在当前窗口中的窗口（被软件隐藏的窗口）
            selected_windows, foreground_windows = self._process_missing_selected_windows(
                selected_windows, foreground_windows,
                selected_windows_snapshot, ignored_windows_snapshot, all_windows
            )

            # 对可见窗口排序：选中的窗口置顶
            foreground_windows.sort(
                key=lambda w: (w.hwnd not in selected_windows_snapshot, w.title)
            )

            self.refresh_finished.emit(ClassifiedWindows(selected_windows, foreground_windows))
        except Exception as e:
            logger.error("窗口刷新线程出错: %s", str(e), exc_info=True)
            self.refresh_finished.emit(ClassifiedWindows([], []))

    def _process_missing_selected_windows(
        self,
        selected_windows: list,
        foreground_windows: list,
        selected_windows_snapshot: set,
        ignored_windows_snapshot: set,
        all_windows: list,
    ):
        """处理在选中窗口列表但未在当前窗口中的窗口"""
        processed_hwnds = {w.hwnd for w in all_windows}

        for hwnd in selected_windows_snapshot:
            if hwnd not in processed_hwnds:
                # 检查窗口是否在忽略列表中
                if hwnd in ignored_windows_snapshot:
                    logger.debug("窗口 %d 被忽略（已从选中列表中移除）", hwnd)
                    continue

                # 尝试获取窗口信息
                window = self.window_manager.get_window(hwnd)
                if window:
                    selected_windows.append(window)
                    logger.debug(
                        "添加被软件隐藏的窗口到选中列表: %d - %s",
                        hwnd,
                        window.title,
                    )
                else:
                    # 窗口不在管理器中，通过配置查找
                    selected_windows = self._find_window_by_config(
                        selected_windows, hwnd, all_windows,
                        ignored_windows_snapshot
                    )

        return selected_windows, foreground_windows

    def _find_window_by_config(
        self,
        selected_windows: list,
        hwnd: int,
        all_windows: list,
        ignored_windows_snapshot: set,
    ):
        """通过配置查找缺失的窗口"""
        if hwnd in ignored_windows_snapshot:
            logger.debug("窗口 %d 被忽略（已从选中列表中移除）", hwnd)
            return selected_windows

        placeholder_window = None
        try:
            if self.config and hasattr(self.config, "target_windows"):
                for window_info in self.config.target_windows:
                    if isinstance(window_info, dict):
                        process_name = window_info.get("process_name", "")
                        title = window_info.get("title", "")

                        # 在当前运行的窗口中查找匹配的窗口
                        for w in all_windows:
                            if w.process_name == process_name and title in w.title:
                                selected_windows.append(w)
                                logger.debug(
                                    "通过进程名和标题找到窗口并添加到选中列表: %d - %s",
                                    w.hwnd,
                                    w.title,
                                )
                                self.hwnd_updated.emit(hwnd, w.hwnd)
                                break
                        else:
                            placeholder_window = self._create_placeholder(
                                process_name, title, hwnd
                            )
        except Exception as e:
            logger.debug("查找窗口失败: %s", e)

        if placeholder_window:
            selected_windows.append(placeholder_window)

        return selected_windows

    def _create_placeholder(self, process_name: str, title: str, hwnd: int):
        """创建占位窗口"""
        if PSUTIL_AVAILABLE:
            try:
                for proc in psutil.process_iter(["name"]):
                    if proc.info["name"].lower() == process_name.lower():
                        return WindowInfo(
                            hwnd=hwnd,
                            title=title,
                            process_name=process_name,
                            is_visible=False,
                            is_taskbar=False,
                            state=WindowState.HIDDEN,
                        )
            except Exception:
                pass

        return WindowInfo(
            hwnd=hwnd,
            title=title,
            process_name=process_name,
            is_visible=False,
            is_taskbar=False,
            state=WindowState.HIDDEN,
        )
