# -*- coding: utf-8 -*-
# windowmanager/window_thread.py
"""
窗口刷新线程 - 后台窗口枚举与分类模块
包含 ClassifiedWindows 数据类和 WindowRefreshThread 后台线程类
"""

import logging
import threading
from dataclasses import dataclass
from PySide6.QtCore import QThread, Signal

from window_base import WindowInfo
from core import SafeWindowsAPI
from deps import PSUTIL_AVAILABLE, psutil, win32process

logger = logging.getLogger(__name__)


@dataclass
class ClassifiedWindows:
    """分类后的窗口列表，避免主线程做 Win32 调用

    属性:
        selected: 选中的窗口列表
        foreground: 可见窗口列表（任务栏中可见的，未选中）
        super_windows_by_process: 超级窗口字典 {process_name_lower: SimpleWindowInfo}
            基于 enum_super_windows 的完整结果（含隐藏窗口），one-VW-per-PID
            所有需要"确认窗口"的地方统一从此字典查找
    """

    selected: list
    foreground: list
    super_windows_by_process: dict


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
        keywords: list,
        config=None,
        hidden_process_names: set = None,
        hidden_windows_info: list = None,
        shared_lock=None,
    ):
        super().__init__()
        self.window_manager = window_manager
        self._selected_windows = selected_windows
        self._ignored_windows = ignored_windows
        self._keywords = keywords
        self.config = config
        self._hidden_process_names = hidden_process_names or set()
        self._hidden_windows_info = hidden_windows_info or []

        # P0-2 修复: 使用传入的共享锁（MainWindowTab._lock），而非自建独立锁
        # 两把独立锁无法提供互斥保护，必须使用同一把锁
        self._lock = shared_lock or threading.RLock()

    def run(self):
        """窗口刷新线程主方法 - 增强日志记录和异常处理"""
        logger.debug("WindowRefreshThread: 开始执行")
        try:
            # 前置检查：窗口管理器是否运行
            if not getattr(self.window_manager, "is_running", False):
                logger.warning("WindowRefreshThread: 窗口管理器未运行，跳过刷新")
                self.refresh_finished.emit(ClassifiedWindows([], [], {}))
                return

            if self.isInterruptionRequested():
                logger.debug("WindowRefreshThread: 收到中断请求，退出")
                self.refresh_finished.emit(ClassifiedWindows([], [], {}))
                return

            # 步骤1：扫描隐藏窗口（确保 _hidden_windows 字典最新）
            logger.debug("WindowRefreshThread: 步骤1 - 扫描隐藏窗口...")
            try:
                if self.isInterruptionRequested():
                    self.refresh_finished.emit(ClassifiedWindows([], [], {}))
                    return

                scanned = self.window_manager.scan_hidden_windows()
                if scanned:
                    logger.debug("WindowRefreshThread: 扫描到 %d 个隐藏窗口", len(scanned))
                else:
                    logger.debug("WindowRefreshThread: 未扫描到新隐藏窗口")
            except Exception as e:
                logger.warning("WindowRefreshThread: 扫描隐藏窗口失败: %s", str(e), exc_info=True)

            if self.isInterruptionRequested():
                self.refresh_finished.emit(ClassifiedWindows([], [], {}))
                return

            # 步骤2：获取共享集合的快照（线程安全）
            logger.debug("WindowRefreshThread: 步骤2 - 获取共享集合快照...")
            with self._lock:
                selected_windows_snapshot = set(self._selected_windows)
                ignored_windows_snapshot = set(self._ignored_windows)
            logger.debug(
                "WindowRefreshThread: 快照获取完成 - 选中=%d个, 忽略=%d个",
                len(selected_windows_snapshot), len(ignored_windows_snapshot)
            )

            if self.isInterruptionRequested():
                self.refresh_finished.emit(ClassifiedWindows([], [], {}))
                return

            # 步骤3：使用超级窗口枚举（借鉴 tools/enum_windows.py 的过滤链）
            logger.debug("WindowRefreshThread: 步骤3 - 枚举超级窗口...")
            if (
                self.config
                and hasattr(self.config, "log")
                and hasattr(self.config.log, "enable_window_refresh_log")
                and self.config.log.enable_window_refresh_log
            ):
                logger.debug("使用超级窗口过滤链进行枚举...")

            super_windows, visible_app_windows = SafeWindowsAPI.enum_super_windows()
            logger.debug(
                "WindowRefreshThread: 枚举完成 - 超级窗口=%d个, 可见主应用窗口=%d个",
                len(super_windows), len(visible_app_windows)
            )

            # 构建超级窗口字典：{process_name_lower: SimpleWindowInfo}
            # 基于 enum_super_windows 的完整结果（含隐藏窗口），one-VW-per-PID
            super_windows_by_process = {}
            for sw in super_windows:
                proc_key = sw.process_name.lower() if sw.process_name else ""
                if not proc_key:
                    continue
                if proc_key in super_windows_by_process:
                    existing = super_windows_by_process[proc_key]
                    if not existing.is_visible and sw.is_visible:
                        super_windows_by_process[proc_key] = sw
                else:
                    super_windows_by_process[proc_key] = sw

            # 构建超级窗口 hwnd 集合（用于快速判断 hwnd 是否为超级窗口，替代 is_super_window 调用）
            super_hwnds = {sw.hwnd for sw in super_windows}

            # 分类前总窗口 = 超级窗口列表（含隐藏+可见）
            all_windows = super_windows

            # 排除隐藏进程（这些进程的窗口信息从配置读取，不通过枚举）
            if self._hidden_process_names:
                all_windows = [
                    w for w in all_windows
                    if w.process_name.lower() not in self._hidden_process_names
                ]
                logger.debug(
                    "已排除隐藏进程的窗口，隐藏进程: %s",
                    self._hidden_process_names,
                )

            if self.isInterruptionRequested():
                self.refresh_finished.emit(ClassifiedWindows([], [], {}))
                return

            # 在后台线程中完成窗口分类（避免主线程 Win32 调用）
            selected_windows = []
            foreground_windows = []

            # 记录已处理的窗口句柄（跨4个数据源共享，避免 hwnd 重复）
            processed_hwnds = set()
            # one-VW-per-PID 跟踪（跨4个数据源共享，避免同进程出现多个条目）
            seen_pids: dict[int, int] = {}  # pid → hwnd

            # 打印分类结果
            if (
                self.config
                and hasattr(self.config, "log")
                and hasattr(self.config.log, "enable_window_refresh_log")
                and self.config.log.enable_window_refresh_log
            ):
                logger.debug(
                    "超级窗口枚举结果: %d 个超级窗口, %d 个可见主应用窗口",
                    len(super_windows),
                    len(visible_app_windows),
                )

            # 构建可见主应用窗口的 hwnd 集合（用于快速查找）
            visible_app_hwnds = {w.hwnd for w in visible_app_windows}

            # === Source 1-2: 主循环 — 枚举窗口中匹配 selected / auto_select 的 ===
            for window in all_windows:
                if window.hwnd in ignored_windows_snapshot:
                    logger.debug("窗口 %d 被忽略", window.hwnd)
                    continue

                processed_hwnds.add(window.hwnd)

                # 对于选中的窗口，无论是否可见，都添加到选中窗口列表
                if window.hwnd in selected_windows_snapshot:
                    # one-VW-per-PID: 同进程只取一个 VW
                    if window.pid and window.pid in seen_pids:
                        logger.debug(
                            "选中窗口 PID 去重: PID=%d 已有 VW (hwnd=%d), 跳过 hwnd=%d (%s)",
                            window.pid, seen_pids[window.pid], window.hwnd, window.title,
                        )
                        continue
                    if window.pid:
                        seen_pids[window.pid] = window.hwnd
                    selected_windows.append(window)
                    logger.debug("窗口 %d 已在选中列表中", window.hwnd)
                # 检查是否是自动选中的进程窗口（通过进程名，大小写不敏感）
                elif any(
                    process.lower() in window.process_name.lower()
                    for process in getattr(self.config.filter, "auto_select_processes", [])
                ):
                    # one-VW-per-PID: 同进程只取一个 VW
                    if window.pid and window.pid in seen_pids:
                        logger.debug(
                            "自动选中 PID 去重: PID=%d 已有 VW (hwnd=%d), 跳过 hwnd=%d (%s)",
                            window.pid, seen_pids[window.pid], window.hwnd, window.title,
                        )
                        continue
                    if window.pid:
                        seen_pids[window.pid] = window.hwnd
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

                # 只显示可见主应用窗口到可见窗口列表
                # 使用超级窗口过滤链的结果（借鉴 tools/enum_windows.py）
                if window.hwnd in visible_app_hwnds:
                    foreground_windows.append(window)

            # === Source 3: 处理在选中窗口列表但未在当前窗口枚举中的窗口（被软件隐藏的窗口） ===
            selected_windows, foreground_windows = self._process_missing_selected_windows(
                selected_windows, foreground_windows,
                selected_windows_snapshot, ignored_windows_snapshot, all_windows,
                processed_hwnds, seen_pids, super_hwnds,
            )

            # === Source 4: 从配置添加隐藏窗口（这些窗口的进程被排除在枚举之外） ===
            selected_windows = self._restore_hidden_windows_from_config(
                selected_windows, selected_windows_snapshot,
                ignored_windows_snapshot, processed_hwnds, seen_pids,
                super_windows_by_process,
            )

            # 对可见窗口排序：选中的窗口置顶
            foreground_windows.sort(
                key=lambda w: (w.hwnd not in selected_windows_snapshot, w.title)
            )

            # 步骤5：发送刷新完成信号（包含完整的分类结果）
            logger.debug(
                "WindowRefreshThread: 刷新完成 - 选中窗口=%d个, 可见窗口=%d个, 总计=%d个",
                len(selected_windows), len(foreground_windows),
                len(selected_windows) + len(foreground_windows)
            )
            self.refresh_finished.emit(ClassifiedWindows(
                selected_windows, foreground_windows, super_windows_by_process,
            ))
            logger.debug("WindowRefreshThread: refresh_finished 信号已发送")
        except Exception as e:
            logger.error(
                "WindowRefreshThread: 执行过程中发生未捕获异常: %s",
                str(e), exc_info=True
            )
            # 确保即使出错也发送空结果，避免UI永久等待
            self.refresh_finished.emit(ClassifiedWindows([], [], {}))

    def _restore_hidden_windows_from_config(
        self,
        selected_windows: list,
        _selected_windows_snapshot: set,
        ignored_windows_snapshot: set,
        processed_hwnds: set,
        seen_pids: dict,
        super_windows_by_process: dict,
    ) -> list:
        """从配置恢复隐藏窗口（Source 4）- 使用超级窗口字典作为唯一数据源

        超级窗口字典包含所有超级窗口（含隐藏窗口），按 process_name_lower 索引。
        不管窗口可见还是隐藏，都始终在字典中，确保重启后能正确恢复。

        三种情况：
        1. 精确匹配：字典中该进程的 hwnd 与保存的 hwnd 一致 → 直接恢复
        2. hwnd 变化：字典中该进程的 hwnd 与保存的不同 → 用新 hwnd 替换，发 hwnd_updated 信号
        3. 字典中无该进程：hwnd 有效则非超级窗口跳过，hwnd 无效则进程已退出跳过
        """
        if not self._hidden_windows_info:
            return selected_windows

        for hidden_info in self._hidden_windows_info:
            hwnd = hidden_info.get("hwnd", 0)
            process_name = hidden_info.get("process_name", "")
            title = hidden_info.get("title", "")

            if not hwnd or hwnd in processed_hwnds:
                continue

            proc_key = process_name.lower() if process_name else ""
            super_win = super_windows_by_process.get(proc_key) if proc_key else None

            if not super_win:
                # 字典中无该进程：检查 hwnd 是否仍有效
                if SafeWindowsAPI.is_window(hwnd):
                    logger.debug(
                        "配置恢复: hwnd=%d 有效但不在超级窗口字典中，跳过 (title=%s, process=%s)",
                        hwnd, title, process_name,
                    )
                else:
                    logger.debug(
                        "配置恢复: hwnd=%d 无效，进程可能已退出 (title=%s, process=%s)",
                        hwnd, title, process_name,
                    )
                processed_hwnds.add(hwnd)
                continue

            # 字典中找到该进程的超级窗口
            if super_win.hwnd == hwnd:
                # 精确匹配：保存的 hwnd 与当前超级窗口 hwnd 一致
                if super_win.pid and super_win.pid in seen_pids:
                    logger.debug(
                        "配置恢复 PID 去重: PID=%d 已有VW (hwnd=%d), 跳过 hwnd=%d",
                        super_win.pid, seen_pids[super_win.pid], hwnd,
                    )
                    processed_hwnds.add(hwnd)
                    continue
                if super_win.pid:
                    seen_pids[super_win.pid] = hwnd

                window = WindowInfo.create_hidden(
                    hwnd=hwnd,
                    title=title or super_win.title,
                    process_name=process_name,
                    pid=super_win.pid,
                    is_taskbar=True,
                )
                selected_windows.append(window)
                processed_hwnds.add(hwnd)
                logger.debug(
                    "从配置恢复隐藏窗口(精确匹配): %d - %s (%s)",
                    hwnd, title, process_name,
                )
            else:
                # hwnd 变化：保存的 hwnd 与当前超级窗口 hwnd 不同
                new_hwnd = super_win.hwnd
                if new_hwnd in processed_hwnds:
                    processed_hwnds.add(hwnd)
                    continue

                if super_win.pid and super_win.pid in seen_pids:
                    logger.debug(
                        "配置恢复 PID 去重: PID=%d 已有VW (hwnd=%d), 跳过新hwnd=%d",
                        super_win.pid, seen_pids[super_win.pid], new_hwnd,
                    )
                    processed_hwnds.add(hwnd)
                    processed_hwnds.add(new_hwnd)
                    continue
                if super_win.pid:
                    seen_pids[super_win.pid] = new_hwnd

                window = WindowInfo.create_hidden(
                    hwnd=new_hwnd,
                    title=super_win.title or title,
                    process_name=process_name,
                    pid=super_win.pid,
                    is_taskbar=True,
                )
                selected_windows.append(window)
                processed_hwnds.add(hwnd)
                processed_hwnds.add(new_hwnd)
                self.hwnd_updated.emit(hwnd, new_hwnd)
                logger.info(
                    "配置恢复(hwnd变化): %d → %d - %s (%s)",
                    hwnd, new_hwnd, super_win.title, process_name,
                )

        return selected_windows

    def _process_missing_selected_windows(
        self,
        selected_windows: list,
        foreground_windows: list,
        selected_windows_snapshot: set,
        ignored_windows_snapshot: set,
        all_windows: list,
        processed_hwnds: set,
        seen_pids: dict,
        super_hwnds: set,
    ):
        """处理在选中窗口列表但未在当前窗口中的窗口

        使用外层 processed_hwnds 和 seen_pids 确保跨数据源去重：
        - processed_hwnds: 避免 hwnd 重复（source 4 可能添加相同 hwnd）
        - seen_pids: one-VW-per-PID 去重（同进程只保留一个条目）
        - super_hwnds: 超级窗口 hwnd 集合，替代 is_super_window 调用
        """
        for hwnd in selected_windows_snapshot:
            if hwnd in processed_hwnds:
                continue

            # 立即标记为已处理，防止 source 4 重复添加
            processed_hwnds.add(hwnd)

            # 检查窗口是否在忽略列表中
            if hwnd in ignored_windows_snapshot:
                logger.debug("窗口 %d 被忽略（已从选中列表中移除）", hwnd)
                continue

            # 尝试获取窗口信息
            window = self.window_manager.get_window(hwnd)
            if window:
                # 使用超级窗口集合验证（替代 is_super_window 调用，保持数据源一致性）
                if hwnd not in super_hwnds:
                    logger.debug(
                        "Source3 跳过非超级窗口: hwnd=%d, title=%s",
                        hwnd, window.title,
                    )
                    continue

                # one-VW-per-PID 去重
                if window.pid and window.pid in seen_pids:
                    logger.debug(
                        "Source3 PID 去重: PID=%d 已有 VW (hwnd=%d), 跳过 hwnd=%d (%s)",
                        window.pid, seen_pids[window.pid], window.hwnd, window.title,
                    )
                    continue
                if window.pid:
                    seen_pids[window.pid] = window.hwnd
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
                    ignored_windows_snapshot, processed_hwnds, seen_pids,
                    super_hwnds,
                )

        return selected_windows, foreground_windows

    def _find_window_by_config(
        self,
        selected_windows: list,
        hwnd: int,
        all_windows: list,
        ignored_windows_snapshot: set,
        processed_hwnds: set,
        seen_pids: dict,
        super_hwnds: set,
    ):
        """通过配置查找缺失的窗口 - hwnd为主键，process_name/title仅用于日志辨识

        核心逻辑（符合PROJECT_Planning.md规范）：
        1. 主路径：直接用保存的hwnd查找当前运行的窗口
        2. 回退路径1：hwnd失效时按进程名枚举（不做标题匹配）
        3. 回退路径2：创建占位窗口（仅当进程仍在运行）
        """
        if hwnd in ignored_windows_snapshot:
            logger.debug("窗口 %d 被忽略（已从选中列表中移除）", hwnd)
            return selected_windows

        placeholder_window = None
        try:
            # === 主路径：直接用hwnd查找 ===
            # 遍历当前运行的窗口，看是否有相同hwnd的窗口
            for w in all_windows:
                if w.hwnd == hwnd:
                    # hwnd精确匹配成功！直接使用这个窗口
                    # one-VW-per-PID 去重
                    if w.pid and w.pid in seen_pids:
                        logger.debug(
                            "配置查找 PID 去重: PID=%d 已有 VW (hwnd=%d), 跳过 hwnd=%d",
                            w.pid, seen_pids[w.pid], w.hwnd,
                        )
                        continue
                    if w.pid:
                        seen_pids[w.pid] = w.hwnd
                    selected_windows.append(w)
                    processed_hwnds.add(w.hwnd)
                    logger.debug(
                        "通过hwnd精确匹配找到窗口并添加到选中列表: %d - %s (%s)",
                        w.hwnd, w.title, w.process_name,
                    )
                    return selected_windows

            # === 回退路径1：hwnd失效，尝试验证 ===
            # 检查hwnd是否真的失效了（窗口不存在或进程已退出）
            hwnd_invalid = not SafeWindowsAPI.is_window(hwnd)
            if hwnd_invalid:
                logger.debug("主路径失败: hwnd=%d 已失效，进入回退路径", hwnd)
            else:
                # hwnd有效但未在all_windows中找到（可能是分类器过滤掉了）
                logger.warning(
                    "主路径异常: hwnd=%d 有效但未在枚举结果中找到，可能被分类器过滤",
                    hwnd,
                )

            # === 回退路径2：按进程名查找（仅当hwnd完全失效时）===
            # 关键修改：只有当窗口真正失效（is_window返回False）时才触发回退路径
            # 如果窗口只是被隐藏（is_window返回True但不在可见列表中），不触发回退
            if self.config and hasattr(self.config, "target_windows") and hwnd_invalid:
                for window_info in self.config.target_windows:
                    if isinstance(window_info, dict):
                        saved_hwnd = window_info.get("hwnd", 0)
                        process_name = window_info.get("process_name", "")

                        # 只处理匹配的配置条目（通过saved_hwnd关联）
                        if saved_hwnd != hwnd:
                            continue

                        logger.info(
                            "回退路径: hwnd=%d 失效，尝试按进程名 '%s' 查找新窗口",
                            hwnd, process_name,
                        )

                        # 在当前运行的窗口中按进程名查找（不匹配标题）
                        # 使用超级窗口集合验证（all_windows 已是超级窗口子集，此为防御性检查）
                        found_by_process = False
                        for w in all_windows:
                            if w.process_name.lower() != process_name.lower():
                                continue

                            if w.hwnd not in super_hwnds:
                                logger.debug(
                                    "回退路径跳过非超级窗口: hwnd=%d, title=%s",
                                    w.hwnd, w.title,
                                )
                                continue

                            # one-VW-per-PID 去重
                            if w.pid and w.pid in seen_pids:
                                logger.debug(
                                    "回退路径 PID 去重: PID=%d 已有 VW (hwnd=%d)",
                                    w.pid, seen_pids[w.pid],
                                )
                                continue
                            if w.pid:
                                seen_pids[w.pid] = w.hwnd

                            selected_windows.append(w)
                            processed_hwnds.add(w.hwnd)
                            found_by_process = True
                            logger.info(
                                "回退路径成功: 通过进程名找到替代窗口 %d → %d - %s (%s)",
                                hwnd, w.hwnd, w.title, w.process_name,
                            )
                            # 通知主线程更新hwnd引用
                            self.hwnd_updated.emit(hwnd, w.hwnd)
                            break

                        if found_by_process:
                            return selected_windows

                        # === 回退路径3：创建占位窗口 ===
                        logger.debug(
                            "回退路径2失败: 进程 '%s' 无可见窗口，尝试创建占位窗口",
                            process_name,
                        )
                        placeholder_window = self._create_placeholder_for_config(
                            window_info, hwnd, seen_pids, processed_hwnds
                        )
        except Exception as e:
            logger.error("_find_window_by_config: 查找窗口失败 - %s", str(e), exc_info=True)

        if placeholder_window:
            # one-VW-per-PID 去重（占位窗口）
            if placeholder_window.pid and placeholder_window.pid in seen_pids:
                logger.debug(
                    "占位窗口 PID 去重: PID=%d 已有 VW (hwnd=%d), 跳过 hwnd=%d",
                    placeholder_window.pid, seen_pids[placeholder_window.pid], placeholder_window.hwnd,
                )
                return selected_windows
            if placeholder_window.pid:
                seen_pids[placeholder_window.pid] = placeholder_window.hwnd
            processed_hwnds.add(placeholder_window.hwnd)
            selected_windows.append(placeholder_window)

        return selected_windows

    def _create_placeholder_for_config(
        self, window_info: dict, hwnd: int, seen_pids: dict, _processed_hwnds: set
    ):
        """为配置中的窗口信息创建占位窗口对象

        仅在进程仍在运行时创建占位符，用于表示"进程存在但窗口未找到"的状态。
        hwnd作为唯一标识传入，process_name和title仅用于日志辨识。
        """
        process_name = window_info.get("process_name", "")
        title = window_info.get("title", "")

        pid = 0
        if PSUTIL_AVAILABLE and psutil is not None:
            try:
                proc_found = False
                for proc in psutil.process_iter(["name", "pid"]):
                    try:
                        if proc.info["name"] and proc.info["name"].lower() == process_name.lower():
                            proc_found = True
                            pid = proc.info.get("pid", 0) or 0
                            break
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                if not proc_found:
                    logger.debug(
                        "_create_placeholder_for_config: 进程 '%s' 已退出，不创建占位窗口 (hwnd=%d)",
                        process_name, hwnd,
                    )
                    return None
            except Exception as e:
                logger.debug(
                    "_create_placeholder_for_config: psutil查询失败 - %s", str(e)
                )
        else:
            # psutil 不可用时，用 IsWindow 做基本存活检查
            if not SafeWindowsAPI.is_window(hwnd):
                logger.debug(
                    "_create_placeholder_for_config: hwnd=%d 无效且psutil不可用，跳过", hwnd
                )
                return None

            # 尝试从 hwnd 获取 pid
            try:
                if win32process is not None:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                else:
                    pid = 0
            except Exception:
                pid = 0

        # one-VW-per-PID 去重（创建前检查）
        if pid and pid in seen_pids:
            logger.debug(
                "_create_placeholder_for_config: PID去重 - PID=%d 已有VW (hwnd=%d)",
                pid, seen_pids[pid],
            )
            return None
        if pid:
            seen_pids[pid] = hwnd

        logger.info(
            "_create_placeholder_for_config: 创建占位窗口 hwnd=%d, process='%s', title='%s', pid=%d",
            hwnd, process_name, title, pid,
        )

        return WindowInfo.create_hidden(
            hwnd=hwnd,
            title=title,
            process_name=process_name,
            pid=pid,
        )
