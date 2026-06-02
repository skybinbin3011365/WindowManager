# -*- coding: utf-8 -*-
# windowmanager/window_keywords.py
"""
关键字管理 Mixin - 包含 MainWindowTab 的关键字相关方法
"""

import logging
from PySide6.QtWidgets import QTableWidgetItem, QMenu, QMessageBox
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt

from window_base import WindowInfo, WindowState
from core import SafeWindowsAPI

logger = logging.getLogger(__name__)


class KeywordMixin:
    """关键字管理 Mixin - 提供关键字管理能力"""

    def _add_keyword(self) -> None:
        """添加关键字"""
        keyword = self.keyword_input.text().strip()
        if not keyword:
            return
        if not self.config:
            return
        if keyword in self.config.filter.keywords:
            QMessageBox.warning(self, "警告", "关键字已存在")
            return

        self.config.filter.keywords.append(keyword)
        self._load_keywords()
        self.keyword_input.clear()

        if self.config_manager:
            self.config_manager.save(self.config)

        self._auto_select_keyword_windows()

    def _remove_selected_keyword(self) -> None:
        """删除选中的关键字"""
        if not self.config:
            return

        selected_rows = set()
        for item in self.keyword_table.selectedItems():
            selected_rows.add(item.row())

        if not selected_rows:
            return

        for row in sorted(selected_rows, reverse=True):
            if row < len(self.config.filter.keywords):
                del self.config.filter.keywords[row]

        self._load_keywords()

        if self.config_manager:
            self.config_manager.save(self.config)

    def clear_all_keywords(self) -> None:
        """清除所有关键字"""
        if not self.config:
            return
        if not self.config.filter.keywords:
            return

        reply = QMessageBox.question(
            self, "确认", "确定要清除所有关键字吗？", QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.config.filter.keywords.clear()
            self._load_keywords()
            if self.config_manager:
                self.config_manager.save(self.config)

    def _load_keywords(self) -> None:
        """加载关键字列表"""
        if not self.config:
            return

        self.keyword_table.setRowCount(len(self.config.filter.keywords))
        for row, keyword in enumerate(self.config.filter.keywords):
            item = QTableWidgetItem(keyword)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.keyword_table.setItem(row, 0, item)

    def _on_keyword_context_menu(self, position) -> None:
        """关键字列表右键菜单"""
        menu = QMenu()
        delete_action = QAction("删除", self)
        delete_action.triggered.connect(self._remove_selected_keyword)
        menu.addAction(delete_action)
        menu.exec(self.keyword_table.mapToGlobal(position))

    def _is_keyword_matched(self, window: WindowInfo) -> bool:
        """检查窗口标题或进程名是否匹配关键字列表"""
        if not self.config or not self.config.filter.keywords:
            return False

        title_lower = window.title.lower()
        process_name_lower = window.process_name.lower()

        for keyword in self.config.filter.keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in title_lower:
                logger.debug("标题匹配成功: %s 在 %s 中", keyword, window.title)
                return True
            if keyword_lower in process_name_lower:
                logger.debug("进程名匹配成功: %s 在 %s 中", keyword, window.process_name)
                return True
            if f"{keyword_lower}.exe" in process_name_lower:
                logger.debug("关键字进程名匹配: %s -> %s", keyword, process_name_lower)
                return True
        return False

    def _collect_keyword_windows(self) -> list:
        """收集所有与关键字匹配的窗口（含隐藏窗口扫描）"""
        try:
            scanned = self.window_manager.scan_hidden_windows()
            if scanned:
                logger.debug("扫描到 %d 个隐藏窗口", len(scanned))
        except Exception as e:
            logger.debug("扫描隐藏窗口失败: %s", str(e))

        windows = self.window_manager.get_all_windows()
        background_windows = self.window_manager.detect_target_windows(
            self.config.filter.keywords
        )
        windows.extend(background_windows)
        return windows

    def _auto_select_keyword_windows(
        self, _force_check: bool = False, skip_refresh: bool = False
    ) -> None:
        """自动选中包含关键字的窗口（仅添加，不替换已有选中项）

        遵循 PROJECT_Planning.md 规范：
        - 仅操作 is_taskbar_window 窗口（任务栏可见窗口）
        - 每个进程（PID）只取唯一的 VW 窗口
        - 与 process_detector.py 的10步过滤链保持一致
        """
        if not self.window_manager:
            return

        try:
            if not getattr(self.window_manager, "is_running", False):
                logger.warning("窗口管理器未运行，跳过自动选择关键字窗口")
                return
            if not self.config or not self.config.filter.keywords:
                return

            windows = self._collect_keyword_windows()

            newly_matched = []
            found_hwnd_per_pid: dict = {}

            logger.debug("_auto_select_keyword_windows: 开始扫描 _selected_windows 中的 PID...")
            with self._lock:
                existing_hwnds = list(self._selected_windows)
            logger.debug("_auto_select_keyword_windows: _selected_windows 有 %d 个项", len(existing_hwnds))

            for existing_hwnd in existing_hwnds:
                existing_window = self.window_manager.get_window(existing_hwnd) if self.window_manager else None
                if existing_window and existing_window.pid:
                    found_hwnd_per_pid[existing_window.pid] = existing_hwnd
            logger.debug("_auto_select_keyword_windows: PID 扫描完成, found %d 个PID", len(found_hwnd_per_pid))

            for window in windows:
                if window.hwnd in self._ignored_windows:
                    logger.debug(
                        "窗口 %d 已被用户忽略，跳过自动选中",
                        window.hwnd,
                    )
                    continue

                if not SafeWindowsAPI.is_super_window(window.hwnd):
                    logger.debug(
                        "关键字匹配但非超级窗口，跳过: HWND=%d, 标题='%s'",
                        window.hwnd, window.title,
                    )
                    continue

                if window.pid in found_hwnd_per_pid:
                    logger.debug(
                        "进程 PID=%d 已有VW (HWND=%d)，跳过重复窗口: HWND=%d, 标题='%s'",
                        window.pid, found_hwnd_per_pid[window.pid],
                        window.hwnd, window.title,
                    )
                    continue
                found_hwnd_per_pid[window.pid] = window.hwnd

                title_lower = window.title.lower()
                process_name_lower = window.process_name.lower()
                matched = any(
                    keyword.lower() in title_lower
                    or keyword.lower() in process_name_lower
                    or f"{keyword.lower()}.exe" in process_name_lower
                    for keyword in self.config.filter.keywords
                )
                if not matched:
                    continue

                with self._lock:
                    self._selected_windows.add(window.hwnd)
                    newly_matched.append(window)

                    if not self.window_manager.has_hidden_window(window.hwnd):
                        try:
                            window.state = WindowState.HIDDEN
                            window.is_visible = False
                            self.window_manager.add_hidden_window(window.hwnd, window)
                            logger.info(
                                "关键字自动选中 VW: HWND=%d, 标题='%s', PID=%d, 进程=%s",
                                window.hwnd, window.title, window.pid, window.process_name,
                            )
                        except Exception:
                            pass

            if self.config:
                self._save_selected_windows_to_config()

            if newly_matched and not skip_refresh:
                self.refresh_windows()
        except Exception as e:
            logger.error("自动选中关键字窗口失败: %s", str(e), exc_info=True)
