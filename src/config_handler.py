# -*- coding: utf-8 -*-
# windowmanager/config_handler.py
"""
配置管理 Mixin - 包含 MainWindowTab 的配置管理方法
"""

import logging
from typing import Set, TYPE_CHECKING

from core import SafeWindowsAPI
from window_models import WindowEntryState, WindowEntry

logger = logging.getLogger(__name__)


class ConfigHandlerMixin:  # pylint: disable=no-member
    """配置管理 Mixin - 提供配置保存/加载能力

    注意：_selected_windows, window_manager, config 等属性由宿主类提供
    """

    if TYPE_CHECKING:
        from manager import WindowManager
        from config import Config
        _selected_windows: Set[int]
        window_manager: WindowManager
        config: Config

    def _dedup_by_hwnd(self, entries: list) -> list:
        """按 hwnd 去重（保留最后出现的条目）

        去重规则：
        - 以 hwnd 为 key，相同的 hwnd 只保留最后出现的条目
        - hwnd 为 0 或 None 的条目不做去重处理

        Args:
            entries: 待去重的窗口条目列表

        Returns:
            list: 去重后的条目列表
        """
        seen_hwnds = set()
        deduped = []
        for entry in reversed(entries):
            hwnd = entry.get("hwnd", 0)
            if hwnd and hwnd not in seen_hwnds:
                seen_hwnds.add(hwnd)
                deduped.append(entry)
            elif not hwnd:
                # hwnd 为 0 或 None 的条目不做去重
                deduped.append(entry)
        return list(reversed(deduped))

    def _load_selected_windows_from_config(self) -> None:
        """从配置中加载选中的窗口（根据进程名 + 标题查找当前句柄）"""
        if not self.config or not self.window_manager:
            return

        target_windows = getattr(self.config, "target_windows", [])
        for window_info in target_windows:
            if not isinstance(window_info, dict):
                continue

            saved_hwnd = window_info.get("hwnd", 0)
            process_name = window_info.get("process_name", "")
            title = window_info.get("title", "")

            if saved_hwnd > 0 and self._try_restore_by_hwnd(saved_hwnd, title, process_name):
                continue

            if not process_name:
                logger.warning(
                    "_load_selected_windows_from_config: 配置条目无hwnd且无进程名，跳过 (title='%s')",
                    title,
                )
                continue

            self._try_restore_by_process_name(process_name, title, saved_hwnd)

        self._dedup_selected_by_pid()

    def _try_restore_by_hwnd(self, saved_hwnd: int, title: str, process_name: str, hwnds: list = None) -> bool:
        """尝试通过保存的 hwnd 直接恢复选中窗口

        返回:
            bool: 是否成功恢复
        """
        window = self.window_manager.get_window(saved_hwnd)
        if not window or not SafeWindowsAPI.is_window(saved_hwnd):
            logger.debug(
                "_load_selected_windows_from_config: hwnd=%d 失效，尝试回退路径",
                saved_hwnd,
            )
            return False

        matched_hwnd = saved_hwnd
        matched_title = window.title

        if title and process_name:
            matched_hwnd, matched_title = self._find_better_hidden_match(
                saved_hwnd, title, matched_title, process_name
            )

        with self._lock:
            self._selected_windows.add(matched_hwnd)
        logger.info(
            "_load_selected_windows_from_config: 通过hwnd恢复选中窗口 %d - %s (%s)",
            matched_hwnd, matched_title, process_name,
        )
        return True

    def _find_better_hidden_match(self, saved_hwnd: int, title: str, default_title: str, process_name: str = "") -> tuple:
        """在隐藏窗口中查找更匹配的窗口

        优先从超级窗口字典查找（唯一数据源），字典为空时回退到 enum_all_windows。

        返回:
            tuple: (matched_hwnd, matched_title)
        """
        matched_hwnd = saved_hwnd
        matched_title = default_title

        try:
            super_dict = getattr(self, "_super_windows_by_process", {})
            if super_dict and process_name:
                proc_key = process_name.lower()
                super_win = super_dict.get(proc_key)
                if super_win and not super_win.is_visible:
                    if title and title in super_win.title:
                        with self._lock:
                            if saved_hwnd in self._selected_windows:
                                self._selected_windows.remove(saved_hwnd)
                        matched_hwnd = super_win.hwnd
                        matched_title = super_win.title
                        logger.info(
                            "_load_selected_windows_from_config: 从超级窗口字典找到更匹配的隐藏窗口 %d - %s（原hwnd=%d）",
                            matched_hwnd, matched_title, saved_hwnd,
                        )
                        return matched_hwnd, matched_title

            all_windows = SafeWindowsAPI.enum_all_windows()
            if not all_windows:
                return matched_hwnd, matched_title

            for w in all_windows:
                if (not w.is_visible and
                        title and title in w.title and
                        (not process_name or w.process_name.lower() == process_name.lower())):
                    with self._lock:
                        if saved_hwnd in self._selected_windows:
                            self._selected_windows.remove(saved_hwnd)
                    matched_hwnd = w.hwnd
                    matched_title = w.title
                    logger.info(
                        "_load_selected_windows_from_config: 检测到更匹配的隐藏窗口 %d - %s（原hwnd=%d）",
                        matched_hwnd, matched_title, saved_hwnd,
                    )
                    break
        except Exception as e:
            logger.debug(
                "_load_selected_windows_from_config: 枚举进程窗口失败: %s", str(e)
            )

        return matched_hwnd, matched_title

    def _try_restore_by_process_name(self, process_name: str, title: str, saved_hwnd: int) -> None:
        """尝试通过进程名回退恢复选中窗口"""
        all_windows = self.window_manager.get_all_windows()
        matched_window = self._match_window_by_title(all_windows, process_name, title)

        if not matched_window:
            matched_window = self._match_hidden_keyword_window(all_windows, process_name)

        if not matched_window:
            matched_window = self._match_visible_window(all_windows, process_name)

        if not matched_window:
            matched_window = self._match_first_process_window(all_windows, process_name)

        if matched_window:
            with self._lock:
                self._selected_windows.add(matched_window.hwnd)
            logger.info(
                "_load_selected_windows_from_config: 通过进程名 '%s' 恢复选中窗口 %d → %d - %s",
                process_name, saved_hwnd, matched_window.hwnd, matched_window.title,
            )
        else:
            logger.debug(
                "_load_selected_windows_from_config: 进程 '%s' 无可见窗口 (saved_hwnd=%d)",
                process_name, saved_hwnd,
            )

    @staticmethod
    def _match_window_by_title(all_windows, process_name: str, title: str):
        """按进程名+标题模糊匹配窗口"""
        if not title:
            return None
        for window in all_windows:
            if (window.process_name.lower() == process_name.lower() and
                    title in window.title):
                return window
        return None

    @staticmethod
    def _match_hidden_keyword_window(all_windows, process_name: str):
        """优先选择隐藏窗口"""
        for window in all_windows:
            if window.process_name.lower() == process_name.lower():
                if not window.is_visible:
                    return window
        return None

    @staticmethod
    def _match_visible_window(all_windows, process_name: str):
        """优先选择可见窗口"""
        for window in all_windows:
            if window.process_name.lower() == process_name.lower():
                if window.is_visible:
                    return window
        return None

    @staticmethod
    def _match_first_process_window(all_windows, process_name: str):
        """选择第一个匹配进程名的窗口"""
        for window in all_windows:
            if window.process_name.lower() == process_name.lower():
                return window
        return None

    def _save_selected_windows_to_config(self) -> None:
        """保存选中的窗口到配置（合并模式，不覆盖隐藏窗口）"""
        if not self.config or not self.config_manager or not self.window_manager:
            return

        # 读取现有的 target_windows，以 hwnd 为 key 索引隐藏窗口
        target_windows = getattr(self.config, "target_windows", [])
        existing_hidden = {}
        for entry in target_windows:
            if isinstance(entry, dict) and entry.get("state") == WindowEntryState.HIDDEN.value:
                hwnd = entry.get("hwnd")
                if hwnd:
                    existing_hidden[hwnd] = entry

        # 构建新的选中窗口列表
        with self._lock:
            selected_snapshot = set(self._selected_windows)
        target_windows_info = []
        for hwnd in selected_snapshot:
            window = self.window_manager.get_window(hwnd)
            if window:
                target_windows_info.append({
                    "hwnd": hwnd,
                    "process_name": window.process_name,
                    "title": window.title,
                    "state": WindowEntryState.VISIBLE.value,
                    "source": WindowEntry.SOURCE_MANUAL,
                })

        # 合并：添加隐藏窗口条目（不被选中窗口覆盖）
        for hwnd, entry in existing_hidden.items():
            # 如果隐藏窗口不在当前选中列表中，保留
            exists = any(
                w["hwnd"] == hwnd
                for w in target_windows_info
            )
            if not exists:
                target_windows_info.append(entry)

        self.config.target_windows = self._dedup_by_hwnd(target_windows_info)
        self.config_manager.save(self.config)

    def _add_window(self, hwnd: int) -> None:
        """添加窗口到选中窗口集合"""
        with self._lock:
            self._selected_windows.add(hwnd)
        self._save_selected_windows_to_config()
        self.refresh_windows()

    def _save_hidden_windows(self) -> None:
        """保存隐藏窗口列表到配置"""
        if not self.config or not self.window_manager:
            return

        target_windows = getattr(self.config, "target_windows", [])
        hidden_window_info = {}

        # 获取超级窗口字典（由 WindowRefreshThread 每次刷新时更新）
        super_dict = getattr(self, "_super_windows_by_process", {})
        super_hwnds = {sw.hwnd for sw in super_dict.values()} if super_dict else None

        if hasattr(self.window_manager, "get_software_hidden_windows"):
            hidden_hwnds = self.window_manager.get_software_hidden_windows()
            for hwnd in hidden_hwnds:
                # 仅保存超级窗口字典中存在的hwnd，确保一定是超级窗口
                if super_hwnds is not None and hwnd not in super_hwnds:
                    logger.debug(
                        "_save_hidden_windows: 跳过非超级窗口: hwnd=%d", hwnd,
                    )
                    continue
                window = self.window_manager.get_window(hwnd)
                if window:
                    hidden_window_info[hwnd] = {"hwnd": hwnd, "window": window}
        else:
            for hwnd in self.window_manager.get_hidden_windows():
                if super_hwnds is not None and hwnd not in super_hwnds:
                    logger.debug(
                        "_save_hidden_windows: 跳过非超级窗口: hwnd=%d", hwnd,
                    )
                    continue
                window = self.window_manager.get_window(hwnd)
                if window:
                    hidden_window_info[hwnd] = {"hwnd": hwnd, "window": window}

        updated_target_windows = []
        for entry in target_windows:
            if isinstance(entry, dict):
                hwnd = entry.get("hwnd")
                if hwnd and hwnd in hidden_window_info:
                    entry["state"] = WindowEntryState.HIDDEN.value
                    entry["hwnd"] = hidden_window_info[hwnd]["hwnd"]
                    entry["process_name"] = hidden_window_info[hwnd]["window"].process_name
                    entry["title"] = hidden_window_info[hwnd]["window"].title

                    updated_target_windows.append(entry)
                elif entry.get("state") != WindowEntryState.HIDDEN.value:
                    updated_target_windows.append(entry)

        for hwnd, info in hidden_window_info.items():
            exists = any(
                isinstance(entry, dict)
                and entry.get("hwnd") == hwnd
                for entry in updated_target_windows
            )
            if not exists:
                window = info["window"]
                entry_data = {
                    "process_name": window.process_name, "title": window.title,
                    "hwnd": hwnd, "state": WindowEntryState.HIDDEN.value, "source": WindowEntry.SOURCE_MANUAL,
                }

                updated_target_windows.append(entry_data)

        self.config.target_windows = self._dedup_by_hwnd(updated_target_windows)
        if self.config_manager:
            self.config_manager.save(self.config)

    def _save_hidden_columns_config(self) -> None:
        """保存隐藏列配置到config.ui"""
        if not self.config or not self.config_manager:
            return
        hidden_columns = []
        column_names = ["选择", "状态", "标题", "进程", "显示器"]
        header = self.selected_window_table.horizontalHeader()
        for i in range(self.selected_window_table.columnCount()):
            if header.isSectionHidden(i):
                hidden_columns.append(column_names[i])
        self.config.ui["hidden_columns"] = hidden_columns
        self.config_manager.save(self.config)

    def _apply_hidden_columns_from_config(self) -> None:
        """从配置中应用隐藏列状态"""
        if not self.config:
            return
        hidden_columns = self.config.ui.get("hidden_columns", [])
        column_names = ["选择", "状态", "标题", "进程", "显示器"]
        for table in [
            self.selected_window_table,
            self.foreground_window_table,
            self.switch_window_table,
        ]:
            header = table.horizontalHeader()
            for i in range(table.columnCount()):
                if i < len(column_names) and column_names[i] in hidden_columns:
                    header.hideSection(i)
                else:
                    header.showSection(i)

    def _dedup_selected_by_pid(self) -> None:
        """对 _selected_windows 做 PID 去重（one-VW-per-PID）

        遍历所有选中窗口，每个 PID 只保留一个 hwnd。
        """
        if not self.window_manager:
            return

        pid_to_hwnd: dict[int, int] = {}
        to_remove: set[int] = set()

        with self._lock:
            hwnds = set(self._selected_windows)

        for hwnd in hwnds:
            pid = self._get_pid_for_hwnd(hwnd) if hasattr(self, "_get_pid_for_hwnd") else 0
            if not pid:
                continue
            if pid in pid_to_hwnd:
                # 保留正数 hwnd，移除负数（占位符）或后遇到的
                existing = pid_to_hwnd[pid]
                if existing < 0 < hwnd:
                    to_remove.add(existing)
                    pid_to_hwnd[pid] = hwnd
                else:
                    to_remove.add(hwnd)
            else:
                pid_to_hwnd[pid] = hwnd

        if to_remove:
            with self._lock:
                self._selected_windows -= to_remove
            logger.info("PID 去重: 从选中列表移除 %d 个重复窗口: %s", len(to_remove), to_remove)
