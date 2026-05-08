# windowmanager/window_switch.py
"""
切换窗口 Mixin - 包含 MainWindowTab 的切换窗口功能
"""

import logging
from PySide6.QtWidgets import (
    QMenu, QDialog, QVBoxLayout, QLabel, QLineEdit,
    QFrame, QListWidget, QDialogButtonBox
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt

from window_base import WindowInfo, WindowState
from core import SafeWindowsAPI

logger = logging.getLogger(__name__)

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False

try:
    import win32gui
    WIN32GUI_AVAILABLE = True
except ImportError:
    win32gui = None
    WIN32GUI_AVAILABLE = False


class SwitchMixin:
    """切换窗口 Mixin - 提供切换窗口管理能力"""

    def _update_switch_window_table(self) -> None:
        """更新切换窗口表格，从配置中加载窗口列表并显示其状态"""
        if not self.config:
            return

        switch_windows_config = getattr(self.config, "switch_windows", [])

        # 兼容旧的 switch_processes 配置
        if not switch_windows_config:
            old_processes = getattr(self.config, "switch_processes", [])
            if old_processes:
                for process_name in old_processes:
                    switch_windows_config.append({
                        "hwnd": 0,
                        "process_name": process_name,
                        "title": process_name,
                        "source": "process"
                    })
                self.config.switch_windows = switch_windows_config
                self.config.switch_processes = []
                if self.config_manager:
                    self.config_manager.save(self.config)

        if not switch_windows_config:
            self.switch_window_table.setRowCount(0)
            return

        switch_windows = []
        all_windows = self.window_manager.get_all_windows() if self.window_manager else []

        try:
            import psutil
            running_processes = set()
            for proc in psutil.process_iter(["name"]):
                try:
                    running_processes.add(proc.info["name"].lower())
                except Exception:
                    continue
        except Exception:
            running_processes = set()

        for entry in switch_windows_config:
            hwnd = entry.get("hwnd", 0)
            process_name = entry.get("process_name", "")

            if hwnd > 0:
                matched = [win for win in all_windows if win.hwnd == hwnd]
                if matched:
                    switch_windows.extend(matched)
                else:
                    process_name_lower = process_name.lower() if process_name else ""
                    if process_name_lower and process_name_lower in running_processes:
                        switch_windows.append(WindowInfo(
                            hwnd=hwnd,
                            title=f"[运行中] {entry.get('title', process_name)}",
                            process_name=process_name,
                            is_visible=False, is_taskbar=False,
                            state=WindowState.HIDDEN,
                        ))
                    else:
                        switch_windows.append(WindowInfo(
                            hwnd=hwnd,
                            title=f"[未找到] {entry.get('title', 'Unknown')}",
                            process_name=process_name,
                            is_visible=False, is_taskbar=False,
                            state=WindowState.HIDDEN,
                        ))
            else:
                if not process_name:
                    continue
                process_name_lower = process_name.lower()
                taskbar_windows = [
                    win for win in all_windows
                    if win.process_name.lower() == process_name_lower
                    and win.is_taskbar and win.title.strip()
                ]
                if taskbar_windows:
                    switch_windows.extend(taskbar_windows)
                else:
                    visible_windows = [
                        win for win in all_windows
                        if win.process_name.lower() == process_name_lower
                        and win.is_visible and win.title.strip()
                    ]
                    if visible_windows:
                        switch_windows.extend(visible_windows)
                    elif process_name_lower in running_processes:
                        switch_windows.append(WindowInfo(
                            hwnd=0,
                            title=f"[运行中] {process_name}",
                            process_name=process_name,
                            is_visible=False, is_taskbar=False,
                            state=WindowState.HIDDEN,
                        ))
                    else:
                        switch_windows.append(WindowInfo(
                            hwnd=0,
                            title=f"[未运行] {process_name}",
                            process_name=process_name,
                            is_visible=False, is_taskbar=False,
                            state=WindowState.HIDDEN,
                        ))

        self._update_window_table_incremental(
            self.switch_window_table, switch_windows, allow_check=False
        )

    def _on_switch_window_double_clicked(self, row: int, col: int) -> None:
        """切换窗口表格双击事件"""
        title_item = self.switch_window_table.item(row, 2)
        if not title_item:
            return
        hwnd = title_item.data(Qt.ItemDataRole.UserRole)  # noqa: F821
        process_name = title_item.data(Qt.ItemDataRole.UserRole + 1)  # noqa: F821
        if hwnd and hwnd > 0:
            self._switch_window_to_foreground(hwnd)
        elif process_name:
            self._switch_process_to_foreground(process_name)

    def _on_switch_window_context_menu(self, position) -> None:
        """切换窗口表格右键菜单"""
        table = self.switch_window_table
        selected_row = table.currentRow()
        if selected_row < 0:
            return

        title_item = table.item(selected_row, 2)
        if not title_item:
            return

        hwnd = title_item.data(Qt.ItemDataRole.UserRole)  # noqa: F821
        process_name = title_item.data(Qt.ItemDataRole.UserRole + 1)  # noqa: F821
        if not hwnd and not process_name:
            return

        menu = QMenu()
        restore_action = QAction("恢复窗口", self)
        if hwnd and hwnd > 0:
            restore_action.triggered.connect(lambda: self._switch_window_to_foreground(hwnd))
        else:
            restore_action.triggered.connect(lambda: self._switch_process_to_foreground(process_name))
        menu.addAction(restore_action)

        remove_action = QAction("移除", self)
        if hwnd and hwnd > 0:
            remove_action.triggered.connect(lambda: self._remove_switch_window(hwnd))
        else:
            remove_action.triggered.connect(lambda: self._remove_switch_process(process_name))
        menu.addAction(remove_action)

        menu.exec(table.mapToGlobal(position))

    def _switch_window_to_foreground(self, hwnd: int) -> None:
        """将指定句柄的窗口恢复到前台"""
        if not self.window_manager:
            return
        if self.window_manager.show_and_minimize_window(hwnd):
            logger.info(f"已将窗口显示到前台: hwnd={hwnd}")
        else:
            logger.warning(f"显示窗口失败: hwnd={hwnd}")

    def _switch_process_to_foreground(self, process_name: str) -> None:
        """将指定进程的窗口恢复到前台"""
        if not self.window_manager:
            return
        count = self.window_manager.show_windows_by_process_name(process_name)
        if count > 0:
            self.status_updated.emit(f"已恢复 {process_name} 的 {count} 个窗口")
            logger.info("切换窗口：恢复 %s 的 %d 个窗口到前台", process_name, count)
        else:
            self.status_updated.emit(f"{process_name} 没有可恢复的窗口")

    def switch_all_processes_to_foreground(self) -> None:
        """热键触发：将所有切换窗口列表中的进程窗口恢复到前台"""
        if not self.config:
            return
        switch_processes = getattr(self.config, "switch_processes", [])
        if not switch_processes:
            self.status_updated.emit("切换窗口列表为空，请先添加进程")
            return
        for process_name in switch_processes:
            self._switch_process_to_foreground(process_name)

    def _remove_switch_window(self, hwnd: int) -> None:
        """从切换窗口列表中移除指定句柄的窗口"""
        if not self.config:
            return
        switch_windows = getattr(self.config, "switch_windows", [])
        for i, entry in enumerate(switch_windows):
            if entry.get("hwnd") == hwnd:
                del switch_windows[i]
                self.config.switch_windows = switch_windows
                if self.config_manager:
                    self.config_manager.save(self.config)
                self._update_switch_window_table()
                logger.info(f"已从切换窗口列表移除: hwnd={hwnd}")
                return

    def _remove_switch_process(self, process_name: str) -> None:
        """从切换窗口列表中移除进程"""
        if not self.config:
            return
        switch_windows = getattr(self.config, "switch_windows", [])
        for i, entry in enumerate(switch_windows):
            if entry.get("process_name", "").lower() == process_name.lower():
                del switch_windows[i]
                self.config.switch_windows = switch_windows
                if self.config_manager:
                    self.config_manager.save(self.config)
                self._update_switch_window_table()
                logger.info(f"已从切换窗口列表移除: {process_name}")
                return

        old_processes = getattr(self.config, "switch_processes", [])
        if process_name in old_processes:
            old_processes.remove(process_name)
            self.config.switch_processes = old_processes
            if self.config_manager:
                self.config_manager.save(self.config)
            self._update_switch_window_table()

    def _show_add_process_dialog(self) -> None:
        """显示添加进程对话框"""
        try:
            import psutil
            processes = {}
            for proc in psutil.process_iter(["name", "pid"]):
                try:
                    name = proc.info["name"].lower()
                    if name not in processes:
                        processes[name] = proc.info["name"]
                except Exception:
                    continue
            process_list = sorted(processes.values())
        except Exception:
            process_list = []

        dialog = QDialog(self)
        dialog.setWindowTitle("添加进程到隐藏窗口")
        dialog.setMinimumWidth(450)
        dialog.setMinimumHeight(350)
        layout = QVBoxLayout(dialog)

        label = QLabel("选择要添加的进程（或手动输入进程名）：")
        layout.addWidget(label)

        input_edit = QLineEdit()
        input_edit.setPlaceholderText("手动输入进程名（如：myapp.exe）")
        layout.addWidget(input_edit)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)

        list_widget = QListWidget()
        list_widget.addItems(process_list)
        list_widget.setSelectionMode(QListWidget.SingleSelection)  # noqa: F821
        layout.addWidget(list_widget)

        search_edit = QLineEdit()
        search_edit.setPlaceholderText("搜索进程...")
        layout.addWidget(search_edit)

        def filter_processes():
            search_text = search_edit.text().lower()
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                item.setHidden(search_text and search_text not in item.text().lower())

        search_edit.textChanged.connect(filter_processes)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)  # noqa: F821
        layout.addWidget(button_box)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)

        if dialog.exec() == QDialog.Accepted:  # noqa: F821
            manual_input = input_edit.text().strip()
            if manual_input:
                process_name = manual_input
            else:
                selected_items = list_widget.selectedItems()
                if not selected_items:
                    return
                process_name = selected_items[0].text()
            self._add_process_to_hidden_windows(process_name)

    def _add_process_to_hidden_windows(self, process_name: str) -> None:
        """添加进程到隐藏窗口列表"""
        if not self.config:
            return
        blacklist = getattr(self.config, "blacklist", [])
        process_name_lower = process_name.lower()
        to_remove = [p for p in blacklist if p.lower() == process_name_lower]
        for p in to_remove:
            blacklist.remove(p)
        if to_remove:
            self.config.blacklist = blacklist
            if self.config_manager:
                self.config_manager.save(self.config)

        if self.window_manager:
            all_windows = self.window_manager.get_all_windows()
            process_windows = [
                w for w in all_windows if w.process_name.lower() == process_name_lower
            ]
            for window in process_windows:
                if window.hwnd not in self._selected_windows:
                    self._select_window(window.hwnd)
        self.refresh_windows()

    def _add_switch_window_by_hwnd(self, hwnd: int, process_name: str = "") -> None:
        """添加单个窗口句柄到切换窗口列表"""
        if not self.config:
            return
        switch_windows = getattr(self.config, "switch_windows", [])
        for entry in switch_windows:
            if entry.get("hwnd") == hwnd:
                logger.debug(f"窗口已在切换列表中: hwnd={hwnd}")
                return

        title = ""
        window_process_name = process_name
        if self.window_manager:
            window = self.window_manager.get_window(hwnd)
            if window:
                title = window.title
                window_process_name = window.process_name
        if not title and WIN32GUI_AVAILABLE and win32gui is not None:
            try:
                title = SafeWindowsAPI.get_window_text(hwnd)
            except Exception:
                pass
        if not title:
            title = window_process_name or f"窗口_{hwnd}"

        new_entry = {
            "hwnd": hwnd, "process_name": window_process_name,
            "title": title, "source": "manual"
        }
        switch_windows.append(new_entry)
        self.config.switch_windows = switch_windows
        if self.config_manager:
            self.config_manager.save(self.config)
        self._update_switch_window_table()
        logger.info(f"已添加到切换窗口列表: hwnd={hwnd}, title={title}")

    def _add_switch_process(self, process_name: str) -> None:
        """添加进程到切换窗口列表"""
        if not self.config:
            return
        switch_windows = getattr(self.config, "switch_windows", [])
        for entry in switch_windows:
            if entry.get("process_name", "").lower() == process_name.lower():
                logger.debug(f"进程已在切换列表中: {process_name}")
                return
        new_entry = {
            "hwnd": 0, "process_name": process_name,
            "title": process_name, "source": "process"
        }
        switch_windows.append(new_entry)
        self.config.switch_windows = switch_windows
        if self.config_manager:
            self.config_manager.save(self.config)
        self._update_switch_window_table()

    def _add_switch_process_by_name(self, process_name: str) -> None:
        """通过进程名添加到切换窗口列表"""
        self._add_switch_process(process_name)

    def _load_switch_processes_from_config(self) -> None:
        """从配置中加载切换窗口进程列表"""
        if not self.config:
            return
        self._update_switch_window_table()
