# -*- coding: utf-8 -*-
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

from core import SafeWindowsAPI
from window_models import WindowEntry
from deps import psutil, WIN32GUI_AVAILABLE, win32gui

logger = logging.getLogger(__name__)


class SwitchMixin:
    """切换窗口 Mixin - 提供切换窗口管理能力"""

    def _update_switch_window_table(self, visible_windows: list) -> None:
        """更新切换窗口表格，基于可见窗口列表进行匹配

        核心逻辑：
        1. 在 visible_windows（分类后的 VW 窗口）中按 hwnd 查找匹配窗口
        2. hwnd 匹配成功且 is_taskbar=True → 显示窗口
        3. hwnd 不匹配或 is_taskbar=False → 按进程名在 visible_windows 中查找
        4. 找到新 VW 窗口 → 更新配置并显示
        5. 进程名也找不到 → 从配置中移除该条目

        Args:
            visible_windows: 可见窗口列表（classified.foreground），只包含 is_taskbar=True 的 VW 窗口
        """
        if not self.config:
            return

        switch_windows_config = getattr(self.config, "switch_windows", [])
        config_changed = False

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
                config_changed = True

        if not switch_windows_config:
            self.switch_window_table.setRowCount(0)
            return

        # 构建 visible_windows 的快速查找索引
        hwnd_index = {win.hwnd: win for win in visible_windows}
        # 进程名 → 第一个匹配的 VW 窗口（one-VW-per-PID）
        process_index = {}
        for win in visible_windows:
            pname_lower = win.process_name.lower()
            if pname_lower not in process_index:
                process_index[pname_lower] = win

        new_switch_config = []
        switch_windows = []

        for entry in switch_windows_config:
            hwnd = entry.get("hwnd", 0)
            process_name = entry.get("process_name", "")
            process_name_lower = process_name.lower() if process_name else ""

            matched_win = None

            # 路径1：按 hwnd 精确匹配
            if hwnd > 0 and hwnd in hwnd_index:
                win = hwnd_index[hwnd]
                if win.is_taskbar:
                    matched_win = win
                    logger.debug(
                        "_update_switch_window_table: hwnd=%d 精确匹配成功 (title='%s')",
                        hwnd, win.title,
                    )
                else:
                    logger.warning(
                        "_update_switch_window_table: hwnd=%d 对应非 VW 窗口，按进程名重新匹配",
                        hwnd,
                    )

            # 路径2：hwnd 匹配失败，按进程名匹配
            if matched_win is None and process_name_lower:
                if process_name_lower in process_index:
                    matched_win = process_index[process_name_lower]
                    logger.info(
                        "_update_switch_window_table: 进程 '%s' 匹配到 VW 窗口 hwnd=%d (title='%s')",
                        process_name, matched_win.hwnd, matched_win.title,
                    )
                    # 更新配置中的 hwnd
                    entry["hwnd"] = matched_win.hwnd
                    entry["title"] = matched_win.title
                    config_changed = True

            if matched_win is not None:
                # 成功匹配到 VW 窗口
                switch_windows.append(matched_win)
                new_switch_config.append(entry)
            else:
                # 匹配失败：窗口不存在或没有 VW 窗口
                if process_name_lower:
                    logger.info(
                        "_update_switch_window_table: 进程 '%s' (hwnd=%d) 没有匹配的 VW 窗口，从配置中移除",
                        process_name, hwnd,
                    )
                else:
                    logger.warning(
                        "_update_switch_window_table: 无效条目 (hwnd=%d, 无进程名)，从配置中移除",
                        hwnd,
                    )
                # 不加入 new_switch_config，即从配置中移除
                config_changed = True

        # 如果配置有变化（hwnd 更新或条目移除），自动保存
        if config_changed and self.config_manager:
            self.config.switch_windows = new_switch_config
            try:
                self.config_manager.save(self.config)
                logger.info("_update_switch_window_table: 已自动保存更新的切换窗口配置")
            except Exception as e:
                logger.error("_update_switch_window_table: 保存配置失败: %s", str(e))

        self._update_window_table_incremental(
            self.switch_window_table, switch_windows, allow_check=False
        )

    def _on_switch_window_double_clicked(self, row: int, _col: int) -> None:
        """切换窗口表格双击事件"""
        title_item = self.switch_window_table.item(row, 2)
        if not title_item:
            return
        raw_hwnd = title_item.data(Qt.ItemDataRole.UserRole)
        hwnd = int(raw_hwnd) if raw_hwnd is not None else 0
        process_name = title_item.data(Qt.ItemDataRole.UserRole + 1) or ""
        if hwnd > 0:
            self._switch_window_to_foreground(hwnd)
        elif process_name:
            self._switch_process_to_foreground(process_name)

    def _on_switch_window_context_menu(self, position) -> None:
        """切换窗口表格右键菜单"""
        table = self.switch_window_table
        selected_row = table.currentRow()

        menu = QMenu()

        if selected_row >= 0:
            title_item = table.item(selected_row, 2)
            if title_item:
                # 获取hwnd（Qt的data()对0可能返回None或0，需要统一处理）
                raw_hwnd = title_item.data(Qt.ItemDataRole.UserRole)
                hwnd = int(raw_hwnd) if raw_hwnd is not None else 0
                process_name = title_item.data(Qt.ItemDataRole.UserRole + 1) or ""

                if hwnd > 0 or process_name:
                    activate_action = QAction("激活窗口", self)
                    if hwnd > 0:
                        activate_action.triggered.connect(lambda checked=False, h=hwnd: self._switch_window_to_foreground(h))
                    else:
                        activate_action.triggered.connect(lambda checked=False, p=process_name: self._switch_process_to_foreground(p))
                    menu.addAction(activate_action)

                    remove_action = QAction("移除", self)
                    if hwnd > 0:
                        remove_action.triggered.connect(lambda checked=False, h=hwnd: self._remove_switch_window(h))
                    else:
                        remove_action.triggered.connect(lambda checked=False, p=process_name: self._remove_switch_process(p))
                    menu.addAction(remove_action)

                    menu.addSeparator()

        activate_all_action = QAction("激活全部窗口", self)
        activate_all_action.triggered.connect(self.switch_all_processes_to_foreground)
        menu.addAction(activate_all_action)

        menu.exec(table.mapToGlobal(position))

    def _switch_window_to_foreground(self, hwnd: int) -> bool:
        """将指定句柄的窗口切换到前台并最大化

        Returns:
            bool: 成功返回True，失败返回False
        """
        if not self.window_manager:
            return False
        if self.window_manager.switch_to_foreground(hwnd):
            logger.info(f"已将窗口切换到前台并最大化: hwnd={hwnd}")
            return True
        logger.warning(f"切换窗口到前台失败: hwnd={hwnd}")
        return False

    def _switch_process_to_foreground(self, process_name: str) -> int:
        """将指定进程的窗口切换到前台并最大化

        Returns:
            int: 成功激活的窗口数量
        """
        if not self.window_manager:
            return 0
        count = self.window_manager.switch_windows_by_process_name(process_name)
        if count > 0:
            logger.info("切换窗口：激活 %s 的 %d 个窗口到前台", process_name, count)
        return count

    def switch_all_processes_to_foreground(self) -> None:
        """热键触发：将所有切换窗口列表中的窗口按顺序激活到前台并最大化

        用于应对假死(hung)窗口的激活需求。
        """
        if not self.config:
            return
        switch_windows = getattr(self.config, "switch_windows", [])

        # 兼容旧的 switch_processes 配置
        switch_processes = getattr(self.config, "switch_processes", [])

        if not switch_windows and not switch_processes:
            self.status_updated.emit("切换窗口列表为空，请先添加窗口")
            return

        activated_count = 0

        # 优先处理 HWND 条目（按添加顺序）
        for entry in switch_windows:
            hwnd = entry.get("hwnd", 0)
            process_name = entry.get("process_name", "")

            if hwnd > 0:
                # 按 HWND 激活单个窗口
                if self._switch_window_to_foreground(hwnd):
                    activated_count += 1
            elif process_name:
                # 按进程名激活（兼容旧配置）
                activated_count += self._switch_process_to_foreground(process_name)

        # 处理旧的 switch_processes 配置
        for process_name in switch_processes:
            activated_count += self._switch_process_to_foreground(process_name)

        if activated_count > 0:
            self.status_updated.emit(f"已激活 {activated_count} 个切换窗口到前台")
        else:
            self.status_updated.emit("没有找到可激活的切换窗口")

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
                # 触发完整刷新，让 _update_switch_window_table 使用最新的 visible_windows
                self.refresh_windows()
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
                # 触发完整刷新，让 _update_switch_window_table 使用最新的 visible_windows
                self.refresh_windows()
                logger.info(f"已从切换窗口列表移除: {process_name}")
                return

        old_processes = getattr(self.config, "switch_processes", [])
        if process_name in old_processes:
            old_processes.remove(process_name)
            self.config.switch_processes = old_processes
            if self.config_manager:
                self.config_manager.save(self.config)
            # 触发完整刷新，让 _update_switch_window_table 使用最新的 visible_windows
            self.refresh_windows()

    def _show_add_process_dialog(self) -> None:
        """显示添加进程对话框"""
        try:
            processes = {}
            if psutil:
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
            # 查找该进程的所有窗口（使用进程名作为辅助辨识参数）
            # 注意：这里按进程名查找是合理的，因为用户是通过进程名发起的自动选择请求
            process_windows = [
                w for w in all_windows if w.process_name.lower() == process_name_lower
            ]
            # 只选最后一个窗口（one-VW-per-PID），避免 N 次 refresh_windows
            last_window = None
            for window in process_windows:
                if window.hwnd not in self._selected_windows:
                    last_window = window
            if last_window:
                logger.info(
                    "_auto_select_process: 通过进程名 '%s' 自动选中窗口 hwnd=%d - %s",
                    process_name, last_window.hwnd, last_window.title,
                )
                self._select_window(last_window.hwnd)
            else:
                logger.debug(
                    "_auto_select_process: 进程 '%s' 无可选窗口 (已选中或无窗口)",
                    process_name,
                )
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
            "title": title, "source": WindowEntry.SOURCE_MANUAL
        }
        switch_windows.append(new_entry)
        self.config.switch_windows = switch_windows
        if self.config_manager:
            self.config_manager.save(self.config)
        # 触发完整刷新，让 _update_switch_window_table 使用最新的 visible_windows
        self.refresh_windows()
        logger.info(f"已添加到切换窗口列表: hwnd={hwnd}, title={title}")

    def _load_switch_processes_from_config(self) -> None:
        """从配置中加载切换窗口进程列表（实际显示由首次 refresh 驱动）"""
        pass
