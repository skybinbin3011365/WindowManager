# -*- coding: utf-8 -*-
# windowmanager/main_window_ops.py
"""
窗口操作 Mixin - 包含 MainWindowTab 的隐藏/显示/恢复等操作方法
"""

import logging
import threading
from typing import Set, TYPE_CHECKING
from PySide6.QtWidgets import QLabel, QApplication, QMessageBox
from PySide6.QtCore import Qt, QTimer

from core import SafeWindowsAPI
from deps import win32process

logger = logging.getLogger(__name__)


class WindowOperationsMixin:  # pylint: disable=no-member
    """窗口操作 Mixin - 提供窗口隐藏/显示能力

    注意：_selected_windows, window_manager 等属性由宿主类 MainWindowTab 提供
    """

    if TYPE_CHECKING:
        from manager import WindowManager
        _selected_windows: Set[int]
        window_manager: WindowManager

    def hide_selected_windows(self) -> None:
        """隐藏选中的窗口（强制操作，用户主动选择的窗口应该能被隐藏）"""
        if not self.window_manager:
            return
        if not self._selected_windows:
            self._show_temp_message("没有选中的窗口")
            return

        def hide_windows_in_background():
            with self._lock:
                hwnds = list(self._selected_windows)
            count = 0
            for hwnd in hwnds:
                if hwnd < 0:
                    continue
                try:
                    # 基本验证：窗口句柄是否有效
                    if not SafeWindowsAPI.is_window(hwnd):
                        logger.debug("隐藏: 窗口 %d 已不存在，跳过", hwnd)
                        continue

                    # 强制隐藏用户选中的窗口（不检查is_taskbar）
                    # 因为用户已经明确选择了要隐藏的窗口
                    self.window_manager.hide_window(hwnd)
                    count += 1
                    logger.debug("已隐藏窗口 %d", hwnd)
                except Exception as e:
                    logger.error("隐藏窗口 %s 失败: %s", hwnd, str(e))

            if self.config and getattr(self.config.log, "enable_window_operation_log", True):
                logger.info("已隐藏 %d 个窗口", count)

            # 隐藏完成后刷新UI和保存配置
            self.request_save_hidden_windows.emit()
            self.request_refresh.emit()

        threading.Thread(target=hide_windows_in_background, daemon=True).start()

    def show_and_minimize_selected_hidden_windows(self) -> None:
        """显示选中的隐藏窗口并最小化到任务栏"""
        if not self.window_manager:
            return
        if not self._selected_windows:
            self._show_temp_message("没有选中的窗口")
            return

        def show_windows_in_background():
            with self._lock:
                hwnds = list(self._selected_windows)
            count = 0
            for hwnd in hwnds:
                try:
                    if hwnd < 0:
                        window = self.window_manager.get_window(hwnd)
                        if window and window.process_name:
                            real_hwnds = self.window_manager.find_all_hwnds_by_process_name(window.process_name)
                            for real_hwnd in real_hwnds:
                                self.window_manager.show_and_minimize_window(real_hwnd)
                                count += 1
                            with self._lock:
                                self._selected_windows.discard(hwnd)
                        continue

                    # 显示所有隐藏的窗口并最小化到任务栏
                    self.window_manager.show_and_minimize_window(hwnd)
                    count += 1
                except Exception as e:
                    logger.error("显示并最小化窗口 %s 失败: %s", hwnd, str(e))

            if self.config and getattr(self.config.log, "enable_window_operation_log", True):
                logger.info("已显示并最小化 %d 个隐藏窗口", count)
            self.request_save_hidden_windows.emit()
            self.request_refresh.emit()

        threading.Thread(target=show_windows_in_background, daemon=True).start()

    def show_selected_hidden_windows(self) -> None:
        """显示选中的隐藏窗口（正常显示，不最小化）"""
        if not self.window_manager:
            return
        if not self._selected_windows:
            self._show_temp_message("没有选中的窗口")
            return

        def show_windows_in_background():
            with self._lock:
                hwnds = list(self._selected_windows)
            count = 0
            for hwnd in hwnds:
                try:
                    if hwnd < 0:
                        window = self.window_manager.get_window(hwnd)
                        if window and window.process_name:
                            real_hwnds = self.window_manager.find_all_hwnds_by_process_name(window.process_name)
                            for real_hwnd in real_hwnds:
                                self.window_manager.show_window(real_hwnd)
                                count += 1
                            with self._lock:
                                self._selected_windows.discard(hwnd)
                        continue

                    # 显示所有隐藏的窗口（使用SW_SHOW恢复可见性，不最小化）
                    self.window_manager.show_window(hwnd)
                    count += 1
                except Exception as e:
                    logger.error("显示窗口 %s 失败: %s", hwnd, str(e))

            if self.config and getattr(self.config.log, "enable_window_operation_log", True):
                logger.info("已显示 %d 个隐藏窗口", count)
            self.request_save_hidden_windows.emit()
            self.request_refresh.emit()

        threading.Thread(target=show_windows_in_background, daemon=True).start()

    def _restore_hidden_window(self, hwnd: int) -> None:
        """恢复被隐藏的窗口（右键菜单触发）

        恢复后从 _selected_windows 和 _software_hidden_windows 中移除，
        窗口不再出现在隐藏列表中。
        """
        if not self.window_manager:
            return

        def do_restore():
            success = self.window_manager.restore_hidden_window(hwnd)
            if success:
                # P1-8 修复: 恢复成功后从选中列表移除，避免仍显示在隐藏列表
                with self._lock:
                    self._selected_windows.discard(hwnd)
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
        """选中窗口并添加到选中窗口列表（带 PID 去重，原子操作）"""
        self._remove_same_pid_from_selected(hwnd)
        with self._lock:
            self._selected_windows.add(hwnd)
        if self.config:
            self._save_selected_windows_to_config()
        self.refresh_windows()

    def _remove_same_pid_from_selected(self, new_hwnd: int) -> None:
        """从 _selected_windows 中移除与 new_hwnd 同 PID 的旧 hwnd（one-VW-per-PID）

        先在锁外收集 PID 信息（避免在锁内调用 Win32 API 导致 UI 卡死），
        然后在锁内执行删除操作。

        特殊处理：如果已有窗口是隐藏窗口，且新窗口是可见窗口，则保留隐藏窗口（不移除）。
        这是为了支持读书巴士这类多窗口应用，用户可能需要操作隐藏的主窗口。
        """
        if not self.window_manager:
            return

        new_pid = self._get_pid_for_hwnd(new_hwnd)
        if not new_pid:
            return

        # 获取新窗口的可见性
        from core import SafeWindowsAPI
        new_is_visible = SafeWindowsAPI.is_window_visible(new_hwnd)

        # 在锁外收集所有已有窗口的 PID（Win32 API 调用可能在某些情况下阻塞）
        with self._lock:
            existing_hwnds = list(self._selected_windows)

        to_remove = set()
        for existing_hwnd in existing_hwnds:
            if existing_hwnd == new_hwnd:
                continue
            existing_pid = self._get_pid_for_hwnd(existing_hwnd)
            if existing_pid and existing_pid == new_pid:
                # 检查旧窗口是否是隐藏窗口
                existing_is_visible = SafeWindowsAPI.is_window_visible(existing_hwnd)
                # 如果旧窗口是隐藏的，新窗口是可见的，则保留隐藏窗口（不移除）
                if not existing_is_visible and new_is_visible:
                    logger.info(
                        "PID 去重: 保留隐藏窗口 %d，跳过可见窗口 %d",
                        existing_hwnd, new_hwnd,
                    )
                    # 移除新窗口（因为我们要保留隐藏窗口）
                    with self._lock:
                        self._selected_windows.discard(new_hwnd)
                    return
                to_remove.add(existing_hwnd)

        if to_remove:
            with self._lock:
                self._selected_windows -= to_remove
            logger.info(
                "PID 去重: 新 hwnd=%d (PID=%d) 替换旧 hwnd=%s",
                new_hwnd, new_pid, to_remove,
            )

    def _get_pid_for_hwnd(self, hwnd: int) -> int:
        """获取 hwnd 对应的 PID，优先从缓存读取，回退到 Win32 API"""
        # 优先从 window_manager 缓存获取
        if self.window_manager:
            window = self.window_manager.get_window(hwnd)
            if window and window.pid:
                return window.pid
        # 回退到 Win32 API
        try:
            if win32process is not None:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                return pid
        except Exception:
            pass
        return 0

    def _remove_window(self, hwnd: int) -> None:
        """移除窗口（从当前表格中移除，点击刷新可以再次显示）"""
        with self._lock:
            self._ignored_windows.add(hwnd)
        self.refresh_windows()
        self.foreground_window_table.clearSelection()
        self.switch_window_table.clearSelection()

    def _remove_window_from_selected(self, hwnd: int) -> None:
        """从选中窗口列表中移除窗口"""
        # 获取窗口信息用于后续处理
        process_name = ""
        is_hidden = False
        if self.window_manager:
            window_info = self.window_manager.get_window(hwnd)
            if window_info:
                process_name = window_info.process_name
                is_hidden = not window_info.is_visible

        # 如果窗口当前是隐藏状态，先恢复其可见性，避免移除后窗口永远不可见
        if is_hidden and hwnd > 0:
            try:
                self.window_manager.show_window(hwnd)
                logger.info("移除前恢复隐藏窗口可见性: hwnd=%d", hwnd)
            except Exception as e:
                logger.warning("移除前恢复窗口可见性失败: hwnd=%d, %s", hwnd, str(e))

        with self._lock:
            if hwnd in self._selected_windows:
                self._selected_windows.remove(hwnd)
            self._ignored_windows.add(hwnd)

        # 同时从窗口管理器的隐藏窗口集合中移除
        if self.window_manager:
            self.window_manager.remove_hidden_window(hwnd)
            logger.info("从窗口管理器移除窗口: %d", hwnd)

        # 更新配置
        if self.config:
            target_windows = getattr(self.config, "target_windows", [])
            self.config.target_windows = [
                entry for entry in target_windows
                if not (isinstance(entry, dict) and entry.get("hwnd") == hwnd)
            ]

            # 从 auto_select_processes 中移除对应的进程名
            if process_name and hasattr(self.config, "filter") and hasattr(self.config.filter, "auto_select_processes"):
                if process_name in self.config.filter.auto_select_processes:
                    self.config.filter.auto_select_processes.remove(process_name)
                    logger.info("从 auto_select_processes 移除进程: %s", process_name)

            if self.config_manager:
                self.config_manager.save(self.config)

        logger.info("移除窗口成功: hwnd=%d, process_name=%s", hwnd, process_name)
        self.refresh_windows()

    def _remove_windows_from_selected_batch(self, hwnds: list) -> None:
        """批量从选中窗口列表中移除窗口"""
        if not hwnds:
            return
        remove_set = set(hwnds)

        # 获取要移除的进程名集合，并恢复隐藏窗口的可见性
        process_names_to_remove = set()
        if self.window_manager:
            for hwnd in hwnds:
                window_info = self.window_manager.get_window(hwnd)
                if window_info and window_info.process_name:
                    process_names_to_remove.add(window_info.process_name)
                    # 恢复隐藏窗口的可见性，避免移除后窗口永远不可见
                    if not window_info.is_visible and hwnd > 0:
                        try:
                            self.window_manager.show_window(hwnd)
                            logger.info("批量移除前恢复隐藏窗口可见性: hwnd=%d", hwnd)
                        except Exception as e:
                            logger.warning("批量移除前恢复窗口可见性失败: hwnd=%d, %s", hwnd, str(e))

        with self._lock:
            for hwnd in hwnds:
                if hwnd in self._selected_windows:
                    self._selected_windows.remove(hwnd)
                self._ignored_windows.add(hwnd)

        # 同时从窗口管理器的隐藏窗口集合中移除
        if self.window_manager:
            self.window_manager.remove_hidden_windows(remove_set)

        # 更新配置
        if self.config:
            target_windows = getattr(self.config, "target_windows", [])
            self.config.target_windows = [
                entry for entry in target_windows
                if not (isinstance(entry, dict) and entry.get("hwnd") in remove_set)
            ]

            # 从 auto_select_processes 中移除对应的进程名
            if hasattr(self.config, "filter") and hasattr(self.config.filter, "auto_select_processes"):
                for process_name in process_names_to_remove:
                    if process_name in self.config.filter.auto_select_processes:
                        self.config.filter.auto_select_processes.remove(process_name)
                        logger.info("从 auto_select_processes 移除进程: %s", process_name)

            if self.config_manager:
                self.config_manager.save(self.config)

        logger.info("批量移除 %d 个窗口，关联进程: %s", len(hwnds), ", ".join(process_names_to_remove))
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
