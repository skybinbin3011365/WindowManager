#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
窗口分类器 - 严格按照Windows任务管理器标准分类窗口
符合用户文档要求：应用窗口 vs 后台进程
"""

import logging
from typing import List, Tuple, Optional

from deps import PSUTIL_AVAILABLE, psutil, WIN32GUI_AVAILABLE, win32gui, win32con, win32process
from window_models import SimpleWindowInfo, WindowEntryState, WindowEntry
from core import SafeWindowsAPI
from constants import WindowConstants

logger = logging.getLogger(__name__)


class WindowClassifier:
    """窗口分类器 - 严格按照任务管理器标准"""

    def __init__(self):
        self._ignored_classes = WindowConstants.EXCLUDED_CLASSES

    def classify_windows(self) -> Tuple[List[SimpleWindowInfo], List[SimpleWindowInfo]]:
        """
        严格按照任务管理器标准分类窗口

        Returns:
            Tuple[List[WindowInfo], List[WindowInfo]]: (应用窗口列表, 后台进程列表)
        """
        # Win32 API 不可用时的降级处理
        if not WIN32GUI_AVAILABLE:
            logger.warning("Win32 API 不可用，无法分类窗口")
            return [], []

        apps = []  # 应用窗口（符合任务管理器标准）
        background = []  # 后台进程

        def enum_callback(hwnd, _):
            try:
                # 检查窗口是否应该被忽略
                if self._should_ignore_window(hwnd):
                    return True

                # 判断是否为任务管理器应用窗口
                if self._is_taskmanager_app_window(hwnd):
                    window_info = self._create_window_info(hwnd)
                    if window_info:
                        apps.append(window_info)
                else:
                    # 其他窗口归为后台进程
                    window_info = self._create_window_info(hwnd)
                    if window_info:
                        background.append(window_info)

            except Exception as e:
                logger.debug("窗口枚举错误 (hwnd=%d): %s", hwnd, e)

            return True

        # 枚举所有窗口
        win32gui.EnumWindows(enum_callback, None)

        logger.debug("分类完成: %d 个应用窗口, %d 个后台进程", len(apps), len(background))
        return apps, background

    def _should_ignore_window(self, hwnd: int) -> bool:
        """判断窗口是否应该被忽略"""
        # 1. 必须是顶层窗口（无父窗口）— 过滤子窗口/控件
        try:
            if win32gui.GetParent(hwnd) != 0:
                return True
        except Exception:
            pass

        # 2. 检查窗口类名
        try:
            class_name = win32gui.GetClassName(hwnd)
            if class_name in self._ignored_classes:
                return True
        except Exception:
            pass

        # 3. 检查窗口是否可见
        if not win32gui.IsWindowVisible(hwnd):
            return True

        return False

    def _is_taskmanager_app_window(self, hwnd: int) -> bool:
        """
        判断是否为任务管理器认定的应用窗口
        严格按照用户文档中的标准
        """
        try:
            # 1. 必须可见
            if not win32gui.IsWindowVisible(hwnd):
                return False

            # 2. 必须是顶层窗口（无父窗口）
            if win32gui.GetParent(hwnd) != 0:
                return False

            # 3. 必须有Alt+Tab可切换风格（WS_EX_APPWINDOW）
            exstyle = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            if not (exstyle & win32con.WS_EX_APPWINDOW):
                # 某些应用可能没有WS_EX_APPWINDOW，但有其他可见标志
                # 检查窗口是否有合适的风格
                style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
                if not (style & win32con.WS_VISIBLE):
                    return False

            # 4. 窗口标题不能为空
            title = win32gui.GetWindowText(hwnd).strip()
            if not title:
                return False

            # 5. 排除系统窗口和工具窗口
            if self._is_system_window(hwnd, title):
                return False

            return True

        except Exception as e:
            logger.debug("判断应用窗口失败 (hwnd=%d): %s", hwnd, e)
            return False

    def _is_system_window(self, hwnd: int, title: str) -> bool:
        """判断是否为系统窗口"""
        # 排除空标题或系统标题
        if title in WindowConstants.SYSTEM_TITLES:
            return True

        # 排除特定类名的窗口
        try:
            class_name = win32gui.GetClassName(hwnd)
            if class_name in WindowConstants.SYSTEM_CLASSES:
                return True
        except Exception:
            pass

        return False

    def _create_window_info(self, hwnd: int) -> Optional[SimpleWindowInfo]:
        """创建窗口信息对象"""
        try:
            # 获取窗口标题
            title = win32gui.GetWindowText(hwnd)

            # 获取窗口类名
            class_name = win32gui.GetClassName(hwnd)

            # 获取进程ID和进程名
            _, pid = win32process.GetWindowThreadProcessId(hwnd)

            if pid == 0:
                return None

            try:
                if PSUTIL_AVAILABLE:
                    process = psutil.Process(pid)
                    process_name = process.name()
                else:
                    process_name = WindowConstants.UNKNOWN_PROCESS_PID_TEMPLATE.format(pid)
            except Exception:
                process_name = WindowConstants.UNKNOWN_PROCESS_PID_TEMPLATE.format(pid)

            # 判断可见性
            is_visible = win32gui.IsWindowVisible(hwnd)

            # 判断是否为任务栏窗口
            is_taskbar = self._is_taskbar_window(hwnd)

            return SimpleWindowInfo(
                hwnd=hwnd,
                title=title,
                class_name=class_name,
                pid=pid,
                process_name=process_name,
                is_visible=is_visible,
                is_taskbar=is_taskbar,
            )

        except Exception as e:
            logger.debug("创建窗口信息失败 (hwnd=%d): %s", hwnd, e)
            return None

    def _is_taskbar_window(self, hwnd: int) -> bool:
        """判断窗口是否为VW（任务栏可见窗口）

        委托给 SafeWindowsAPI.is_taskbar_window()，
        根据PROJECT_Planning.md规范的4个条件判定：
        1. 顶层窗口（GetParent == 0）
        2. 有窗口标题（非空）
        3. 有最大化/最小化按钮
        4. 非隐藏状态
        """
        return SafeWindowsAPI.is_taskbar_window(hwnd)

    def find_window_by_process(
        self, process_name: str, title_pattern: str = ""
    ) -> Optional[SimpleWindowInfo]:
        """
        根据进程名和标题模式查找窗口

        Args:
            process_name: 进程名
            title_pattern: 标题模式（支持部分匹配）

        Returns:
            Optional[SimpleWindowInfo]: 找到的窗口信息，未找到返回None
        """
        apps, background = self.classify_windows()
        all_windows = apps + background

        for window in all_windows:
            # 按进程名查找（hwnd为主键，process_name仅作为辅助辨识参数）
            if window.process_name.lower() == process_name.lower():
                # 标题匹配是可选的（用于进一步筛选，但不是必须的）
                if not title_pattern or title_pattern.lower() in window.title.lower():
                    logger.debug(
                        "find_window_by_process_name: 找到窗口 hwnd=%d - '%s' (%s)",
                        window.hwnd, window.title, window.process_name,
                    )
                    return window

        logger.debug(
            "find_window_by_process_name: 未找到进程 '%s' 的窗口 (title_pattern='%s')",
            process_name, title_pattern,
        )
        return None

    def update_target_window_status(self, target_windows: List[WindowEntry]) -> List[WindowEntry]:
        """
        更新设定窗口的状态

        Args:
            target_windows: 设定窗口列表

        Returns:
            List[WindowEntry]: 更新状态后的设定窗口列表
        """
        # 获取当前所有窗口
        apps, background = self.classify_windows()
        all_windows = {w.hwnd: w for w in apps + background}

        updated_windows = []

        for entry in target_windows:
            # === 主路径：通过hwnd查找（如果配置中保存了hwnd）===
            found_window = None
            if entry.hwnd and entry.hwnd > 0:
                found_window = all_windows.get(entry.hwnd)
                if found_window:
                    logger.debug(
                        "update_target_window_status: 通过hwnd=%d 找到窗口 '%s' (%s)",
                        entry.hwnd, found_window.title, found_window.process_name,
                    )
                else:
                    logger.debug(
                        "update_target_window_status: hwnd=%d 未在当前窗口中找到，尝试回退",
                        entry.hwnd,
                    )

            # === 回退路径：按进程名+标题查找（仅当hwnd无效时）===
            if not found_window:
                for window in all_windows.values():
                    # 按进程名查找（标题作为辅助筛选条件）
                    if window.process_name.lower() != entry.process_name.lower():
                        continue

                    # 标题部分匹配（兼容标题变化的情况）
                    if not entry.title or entry.title.lower() in window.title.lower():
                        found_window = window
                        logger.info(
                            "update_target_window_status: 回退路径成功 - "
                            "通过进程名 '%s' 找到窗口 hwnd=%d - '%s'",
                            entry.process_name, window.hwnd, window.title,
                        )
                        break

            # 更新状态
            if found_window:
                # 更新entry的hwnd为实际找到的窗口句柄
                if entry.hwnd != found_window.hwnd:
                    logger.info(
                        "update_target_window_status: 更新hwnd %d → %d (process='%s')",
                        entry.hwnd, found_window.hwnd, entry.process_name,
                    )
                    entry.hwnd = found_window.hwnd
                # 检查窗口是否被隐藏
                if found_window.is_visible:
                    entry.state = WindowEntryState.VISIBLE
                else:
                    entry.state = WindowEntryState.HIDDEN
            else:
                entry.hwnd = None
                entry.state = WindowEntryState.INVALID

            updated_windows.append(entry)

        return updated_windows
