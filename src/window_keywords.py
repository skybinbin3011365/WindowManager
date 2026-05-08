# windowmanager/window_keywords.py
"""
关键字管理 Mixin - 包含 MainWindowTab 的关键字相关方法
"""

import logging
from PySide6.QtWidgets import QTableWidgetItem, QMenu, QMessageBox
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt

from window_base import WindowInfo, WindowState

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
        if keyword in self.config.keywords:
            QMessageBox.warning(self, "警告", "关键字已存在")
            return

        self.config.keywords.append(keyword)
        self._load_keywords()
        self.keyword_input.clear()

        # 保存配置
        if self.config_manager:
            self.config_manager.save(self.config)

        # 自动选中匹配新关键字的窗口（内部会触发一次 refresh_windows）
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

        # 从后往前删除，避免索引变化
        for row in sorted(selected_rows, reverse=True):
            if row < len(self.config.keywords):
                del self.config.keywords[row]

        self._load_keywords()

        # 保存配置
        if self.config_manager:
            self.config_manager.save(self.config)

    def _clear_all_keywords(self) -> None:
        """清除所有关键字"""
        if not self.config:
            return
        if not self.config.keywords:
            return

        reply = QMessageBox.question(
            self, "确认", "确定要清除所有关键字吗？", QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.config.keywords.clear()
            self._load_keywords()
            if self.config_manager:
                self.config_manager.save(self.config)

    def _load_keywords(self) -> None:
        """加载关键字列表"""
        if not self.config:
            return

        self.keyword_table.setRowCount(len(self.config.keywords))
        for row, keyword in enumerate(self.config.keywords):
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
        if not self.config or not self.config.keywords:
            return False

        title_lower = window.title.lower()
        process_name_lower = window.process_name.lower()

        for keyword in self.config.keywords:
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

    def _auto_select_keyword_windows(
        self, force_check: bool = False, skip_refresh: bool = False
    ) -> None:
        """自动选中包含关键字的窗口（仅添加，不替换已有选中项）"""
        if not self.window_manager:
            return

        try:
            if not getattr(self.window_manager, "is_running", False):
                logger.warning("窗口管理器未运行，跳过自动选择关键字窗口")
                return
            if not self.config or not self.config.keywords:
                return

            # 先扫描系统中的隐藏窗口
            try:
                if hasattr(self.window_manager, "scan_hidden_windows"):
                    scanned = self.window_manager.scan_hidden_windows()
                    if scanned:
                        logger.debug("扫描到 %d 个隐藏窗口", len(scanned))
            except Exception as e:
                logger.debug("扫描隐藏窗口失败: %s", str(e))

            windows = self.window_manager.get_all_windows()
            background_windows = self.window_manager.check_background_processes(
                self.config.keywords
            )
            windows.extend(background_windows)

            newly_matched = []
            for window in windows:
                if window.hwnd in self._selected_windows:
                    continue

                title_lower = window.title.lower()
                matched = any(
                    keyword.lower() in title_lower
                    for keyword in self.config.keywords
                )
                if not matched:
                    continue

                with self._lock:
                    self._selected_windows.add(window.hwnd)
                    newly_matched.append(window)

                    if window.hwnd not in getattr(self.window_manager, '_hidden_windows', {}):
                        try:
                            window.state = WindowState.HIDDEN
                            window.is_visible = False
                            self.window_manager._hidden_windows[window.hwnd] = window
                        except Exception:
                            pass

            if self.config:
                self._save_selected_windows_to_config()

            if newly_matched and not skip_refresh:
                self.refresh_windows()
        except Exception as e:
            logger.error("自动选中关键字窗口失败: %s", str(e), exc_info=True)

    
