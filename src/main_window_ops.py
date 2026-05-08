# windowmanager/main_window_ops.py
"""
窗口操作 Mixin - 包含 MainWindowTab 的隐藏/显示/恢复等操作方法
"""

import logging
import threading
from PySide6.QtWidgets import QLabel, QApplication, QMessageBox
from PySide6.QtCore import Qt, QTimer

from core import SafeWindowsAPI

logger = logging.getLogger(__name__)


class WindowOperationsMixin:
    """窗口操作 Mixin - 提供窗口隐藏/显示能力"""

    def hide_selected_windows(self) -> None:
        """隐藏选中的窗口（强制操作，不考虑窗口是否真实存在）"""
        if not self.window_manager:
            return
        if not self._selected_windows:
            self._show_temp_message("没有选中的窗口")
            return

        def hide_windows_in_background():
            count = 0
            for hwnd in self._selected_windows:
                if hwnd < 0:
                    continue
                try:
                    if not SafeWindowsAPI.is_window(hwnd):
                        continue
                    self.window_manager.hide_window(hwnd)
                    count += 1
                except Exception as e:
                    logger.error("隐藏窗口 %s 失败: %s", hwnd, str(e))

            if self.config and getattr(self.config, "enable_window_operation_log", True):
                logger.info("已隐藏 %d 个窗口", count)
            self.request_save_hidden_windows.emit()
            self.request_refresh.emit()

        threading.Thread(target=hide_windows_in_background, daemon=True).start()

    def show_and_minimize_selected_hidden_windows(self) -> None:
        """显示选中的隐藏窗口并最小化"""
        if not self.window_manager:
            return
        if not self._selected_windows:
            self._show_temp_message("没有选中的窗口")
            return

        def show_windows_in_background():
            count = 0
            removed_count = 0
            hidden_hwnds = set()
            if hasattr(self.window_manager, "get_software_hidden_windows"):
                hidden_hwnds = set(self.window_manager.get_software_hidden_windows())
            elif hasattr(self.window_manager, "_hidden_windows"):
                hidden_hwnds = set(self.window_manager._hidden_windows.keys())

            to_remove = []
            for hwnd in list(self._selected_windows):
                try:
                    if hwnd < 0:
                        window = self.window_manager.get_window(hwnd)
                        if window and window.process_name:
                            real_hwnds = self.window_manager.find_all_windows_by_process_name(window.process_name)
                            for real_hwnd in real_hwnds:
                                self.window_manager.show_and_minimize_window(real_hwnd)
                                count += 1
                            if hwnd in self._selected_windows:
                                self._selected_windows.remove(hwnd)
                        continue

                    window = self.window_manager.get_window(hwnd)
                    if window:
                        if window.is_taskbar is not None and not window.is_taskbar:
                            logger.info(f"窗口 {hwnd} (title={window.title}) is_taskbar=False，从隐藏列表移除")
                            to_remove.append(hwnd)
                            removed_count += 1
                            continue
                        self.window_manager.show_and_minimize_window(hwnd)
                        count += 1
                except Exception as e:
                    logger.error("显示并最小化窗口 %s 失败: %s", hwnd, str(e))

            for hwnd in to_remove:
                if hwnd in self._selected_windows:
                    self._selected_windows.remove(hwnd)
            if to_remove:
                self._save_hidden_windows()

            if self.config and getattr(self.config, "enable_window_operation_log", True):
                logger.info("已显示并最小化 %d 个隐藏窗口，移除 %d 个 is_taskbar=False 的窗口",
                           count, removed_count)
            self.request_save_hidden_windows.emit()
            self.request_refresh.emit()

        threading.Thread(target=show_windows_in_background, daemon=True).start()

    def _restore_hidden_window(self, hwnd: int) -> None:
        """恢复被隐藏的窗口（右键菜单触发）"""
        if not self.window_manager:
            return

        def do_restore():
            window = self.window_manager.get_window(hwnd)
            if window and window.is_taskbar is not None and not window.is_taskbar:
                logger.info(f"窗口 {hwnd} (title={window.title}) is_taskbar=False，从隐藏列表移除")
                if hwnd in self._selected_windows:
                    self._selected_windows.remove(hwnd)
                self._save_hidden_windows()
                self.request_refresh.emit()
                return
            success = self.window_manager.restore_hidden_window(hwnd)
            if success:
                self.request_save_hidden_windows.emit()
                self.request_refresh.emit()

        threading.Thread(target=do_restore, daemon=True).start()

    def _restore_process_windows(self, process_name: str) -> None:
        """恢复指定进程的所有窗口"""
        if not self.window_manager:
            return
        restored_hwnds = self.window_manager.restore_windows_by_process(process_name)
        if restored_hwnds:
            logger.info("恢复了进程 %s 的 %d 个窗口", process_name, len(restored_hwnds))
            self._save_hidden_windows()
            self.refresh_windows()
            self._show_temp_message(f"已恢复 {len(restored_hwnds)} 个 {process_name} 窗口")
        else:
            self._show_temp_message(f"未找到进程 {process_name} 的隐藏窗口")

    def _select_window(self, hwnd: int) -> None:
        """选中窗口并添加到选中窗口列表"""
        with self._lock:
            self._selected_windows.add(hwnd)
        if self.config:
            self._save_selected_windows_to_config()
        self.refresh_windows()

    def _remove_window(self, hwnd: int) -> None:
        """移除窗口（从当前表格中移除，点击刷新可以再次显示）"""
        self._ignored_windows.add(hwnd)
        self.refresh_windows()
        self.foreground_window_table.clearSelection()
        self.switch_window_table.clearSelection()

    def _remove_window_from_selected(self, hwnd: int) -> None:
        """从选中窗口列表中移除窗口"""
        with self._lock:
            if hwnd in self._selected_windows:
                self._selected_windows.remove(hwnd)
        self._ignored_windows.add(hwnd)
        if self.config and self.window_manager:
            target_windows = getattr(self.config, "target_windows", [])
            window = self.window_manager.get_window(hwnd)
            if window:
                self.config.target_windows = [
                    entry for entry in target_windows
                    if not (
                        entry.get("process_name") == window.process_name
                        and entry.get("title") == window.title
                    )
                ]
                if self.config_manager:
                    self.config_manager.save(self.config)
        self.refresh_windows()

    def _remove_windows_from_selected_batch(self, hwnds: list) -> None:
        """批量从选中窗口列表中移除窗口"""
        if not hwnds:
            return
        with self._lock:
            for hwnd in hwnds:
                if hwnd in self._selected_windows:
                    self._selected_windows.remove(hwnd)
                self._ignored_windows.add(hwnd)
        if self.config and self.window_manager:
            target_windows = getattr(self.config, "target_windows", [])
            windows_to_remove = set()
            for hwnd in hwnds:
                window = self.window_manager.get_window(hwnd)
                if window:
                    windows_to_remove.add((window.process_name, window.title))
            self.config.target_windows = [
                entry for entry in target_windows
                if (entry.get("process_name"), entry.get("title")) not in windows_to_remove
            ]
            if self.config_manager:
                self.config_manager.save(self.config)
        self.refresh_windows()

    def _show_temp_message(self, message: str, duration: int = 2000) -> None:
        """显示临时消息，自动关闭"""
        from theme import theme
        msg_label = QLabel(message)
        msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg_label.setStyleSheet(theme.get_temp_message_stylesheet())
        msg_label.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        msg_label.setAttribute(Qt.WA_TranslucentBackground)
        msg_label.show()

        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.availableGeometry()
            msg_label.move(
                (screen_geometry.width() - msg_label.width()) // 2,
                (screen_geometry.height() - msg_label.height()) // 2,
            )
        QTimer.singleShot(duration, msg_label.deleteLater)

    def _on_reset_clicked(self) -> None:
        """处理全部重置按钮点击"""
        reply = QMessageBox.question(
            self, "确认",
            "确定要全部重置吗？这将清除所有关键字和选中状态。",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.clear_all_keywords()
            self.clear_selected_windows()
            self.refresh_windows()

    def clear_selected_windows(self) -> None:
        """清除所有选中的窗口"""
        with self._lock:
            self._selected_windows.clear()
        if self.config:
            self.config.target_windows = []
            if self.config_manager:
                self.config_manager.save(self.config)
        self.refresh_windows()
