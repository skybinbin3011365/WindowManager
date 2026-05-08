# windowmanager/window_manager_ui.py
"""
UI 布局与更新 Mixin - 包含 MainWindowTab 的 UI 初始化和表格更新方法
"""

import logging
from typing import List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidgetItem, QHeaderView, QGroupBox, QLineEdit,
    QSplitter, QCheckBox, QAbstractItemView, QFrame, QComboBox,
    QMenu,
)
from PySide6.QtGui import QAction, QColor
from PySide6.QtCore import Qt, QDateTime

from window_base import WindowInfo
from core import SafeWindowsAPI

logger = logging.getLogger(__name__)


class WindowManagerUIMixin:
    """UI 布局与更新 Mixin - 提供 UI 初始化和表格更新能力"""

    def _init_ui(self) -> None:
        """初始化UI组件"""
        from theme import theme
        self.setStyleSheet(theme.get_global_stylesheet())
        self._init_main_layout()
        self._init_keyword_section()
        self._init_window_tables()
        self._init_buttons()
        self._init_options()
        self._init_connections()
        self._load_keywords()
        self._apply_hidden_columns_from_config()

    def _init_main_layout(self) -> None:
        """初始化主布局"""
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(5, 5, 5, 5)
        self.layout().setSpacing(5)
        self.layout().addWidget(self.main_splitter)

    def _init_keyword_section(self) -> None:
        """初始化关键字部分"""
        left_frame = QGroupBox("关键字列表")
        left_layout = QVBoxLayout(left_frame)
        left_layout.setContentsMargins(5, 5, 5, 5)
        left_layout.setSpacing(3)

        keyword_input_layout = QHBoxLayout()
        keyword_input_layout.setSpacing(3)
        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("输入关键字")
        self.keyword_input.returnPressed.connect(self._add_keyword)
        keyword_input_layout.addWidget(self.keyword_input)

        add_keyword_btn = QPushButton("添加")
        add_keyword_btn.setFixedWidth(60)
        add_keyword_btn.clicked.connect(self._add_keyword)
        keyword_input_layout.addWidget(add_keyword_btn)
        left_layout.addLayout(keyword_input_layout)

        from PySide6.QtWidgets import QTableWidget
        self.keyword_table = QTableWidget()
        self.keyword_table.setColumnCount(1)
        self.keyword_table.setHorizontalHeaderLabels(["关键字"])
        self.keyword_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.keyword_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.keyword_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.keyword_table.customContextMenuRequested.connect(self._on_keyword_context_menu)
        left_layout.addWidget(self.keyword_table)

        keyword_btn_layout = QHBoxLayout()
        keyword_btn_layout.setSpacing(3)
        remove_keyword_btn = QPushButton("删除选中")
        remove_keyword_btn.setFixedWidth(100)
        remove_keyword_btn.clicked.connect(self._remove_selected_keyword)
        keyword_btn_layout.addWidget(remove_keyword_btn)
        clear_keywords_btn = QPushButton("全部清除")
        clear_keywords_btn.setFixedWidth(100)
        clear_keywords_btn.clicked.connect(self._clear_all_keywords)
        keyword_btn_layout.addWidget(clear_keywords_btn)
        left_layout.addLayout(keyword_btn_layout)

        left_frame.setMinimumWidth(130)
        self.main_splitter.addWidget(left_frame)

    def _init_window_tables(self) -> None:
        """初始化窗口表格"""
        from window_table import WindowTableWidget

        self.right_frame = QWidget()
        self.right_layout = QVBoxLayout(self.right_frame)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.setSpacing(3)

        self._init_window_search_box()
        self.right_layout.addWidget(self.window_search_frame)

        self.window_splitter = QSplitter(Qt.Vertical)

        # 1. 隐藏窗口表格
        selected_group = QGroupBox("隐藏窗口")
        selected_group_layout = QVBoxLayout(selected_group)
        selected_group_layout.setContentsMargins(3, 3, 3, 3)
        self.selected_window_table = WindowTableWidget()
        self.selected_window_table.setMinimumHeight(35)
        selected_group_layout.addWidget(self.selected_window_table)
        self.window_splitter.addWidget(selected_group)

        # 2. 可见窗口表格
        foreground_group = QGroupBox("可见窗口")
        foreground_group_layout = QVBoxLayout(foreground_group)
        foreground_group_layout.setContentsMargins(3, 3, 3, 3)
        self.foreground_window_table = WindowTableWidget()
        self.foreground_window_table.setSortingEnabled(True)
        self.foreground_window_table.horizontalHeader().setSortIndicatorShown(True)
        self.foreground_window_table.horizontalHeader().setSectionsClickable(True)
        self.foreground_window_table.setMinimumHeight(35)
        foreground_group_layout.addWidget(self.foreground_window_table)
        self.window_splitter.addWidget(foreground_group)

        # 3. 切换窗口表格
        switch_group = QGroupBox("切换窗口")
        switch_group_layout = QVBoxLayout(switch_group)
        switch_group_layout.setContentsMargins(3, 3, 3, 3)
        self.switch_window_table = WindowTableWidget()
        self.switch_window_table.setMinimumHeight(35)
        switch_group_layout.addWidget(self.switch_window_table)
        self.window_splitter.addWidget(switch_group)

        self.window_splitter.setSizes([120, 250, 120])
        self.right_layout.addWidget(self.window_splitter)

    def _init_buttons(self) -> None:
        """初始化操作按钮"""
        button_layout = QHBoxLayout()
        refresh_btn = QPushButton("刷新窗口")
        refresh_btn.clicked.connect(self.refresh_windows)
        button_layout.addWidget(refresh_btn)

        hide_btn = QPushButton("隐藏窗口")
        hide_btn.clicked.connect(self.hide_selected_windows)
        button_layout.addWidget(hide_btn)

        show_btn = QPushButton("显示窗口")
        show_btn.clicked.connect(self.show_and_minimize_selected_hidden_windows)
        button_layout.addWidget(show_btn)

        reset_btn = QPushButton("全部重置")
        reset_btn.clicked.connect(self._on_reset_clicked)
        button_layout.addWidget(reset_btn)

        button_layout.addStretch()
        self.right_layout.addLayout(button_layout)

    def _init_options(self) -> None:
        """初始化选项"""
        options_layout = QHBoxLayout()

        self.auto_refresh_checkbox = QCheckBox("自动刷新")
        self.auto_refresh_checkbox.setChecked(True)
        self.auto_refresh_checkbox.stateChanged.connect(self._on_auto_refresh_changed)
        options_layout.addWidget(self.auto_refresh_checkbox)

        options_layout.addWidget(QLabel("刷新间隔:"))
        self.refresh_interval_spinbox = QLineEdit()
        self.refresh_interval_spinbox.setFixedWidth(60)
        self.refresh_interval_spinbox.setText(
            str(getattr(self.config, "auto_refresh_interval", 5.0))
        )
        self.refresh_interval_spinbox.editingFinished.connect(self._on_refresh_interval_changed)
        options_layout.addWidget(self.refresh_interval_spinbox)
        options_layout.addWidget(QLabel("秒"))

        options_layout.addStretch()
        self.right_layout.addLayout(options_layout)
        self.main_splitter.addWidget(self.right_frame)
        self.main_splitter.setSizes([200, 600])

    def _init_window_search_box(self) -> None:
        """初始化窗口搜索框"""
        from theme import theme

        self.window_search_frame = QFrame()
        self.window_search_frame.setObjectName("windowSearchFrame")
        search_layout = QHBoxLayout(self.window_search_frame)
        search_layout.setContentsMargins(0, 3, 0, 3)
        search_layout.setSpacing(6)

        search_icon_label = QLabel("🔍")
        search_icon_label.setFixedWidth(25)
        search_layout.addWidget(search_icon_label)

        self.window_search_input = QLineEdit()
        self.window_search_input.setPlaceholderText("搜索窗口...")
        self.window_search_input.textChanged.connect(self._on_window_search_text_changed)
        self.window_search_input.setFixedHeight(28)
        search_layout.addWidget(self.window_search_input, 1)

        self.search_type_combo = QComboBox()
        self.search_type_combo.addItems(["全部", "标题", "进程名"])
        self.search_type_combo.setFixedWidth(80)
        self.search_type_combo.currentTextChanged.connect(self._on_window_search_text_changed)
        search_layout.addWidget(self.search_type_combo)

        clear_search_btn = QPushButton("✕")
        clear_search_btn.setFixedWidth(30)
        clear_search_btn.setObjectName("clearSearchBtn")
        clear_search_btn.clicked.connect(self._on_clear_window_search)
        clear_search_btn.setToolTip("清除搜索")
        search_layout.addWidget(clear_search_btn)

    def _on_window_search_text_changed(self, text: str) -> None:
        """处理窗口搜索文本变化"""
        search_type = self.search_type_combo.currentText()
        self._filter_window_tables(text, search_type)

    def _filter_window_tables(self, text: str, search_type: str) -> None:
        """根据搜索条件过滤窗口表格"""
        if not text:
            for table in [
                self.selected_window_table,
                self.foreground_window_table,
                self.switch_window_table,
            ]:
                for row in range(table.rowCount()):
                    table.setRowHidden(row, False)
            return

        text_lower = text.lower()
        tables = [
            (self.selected_window_table, 2, 3),
            (self.foreground_window_table, 2, 3),
            (self.switch_window_table, 2, 3),
        ]

        for table, title_col, process_col in tables:
            for row in range(table.rowCount()):
                title_item = table.item(row, title_col)
                process_item = table.item(row, process_col)
                title = title_item.text().lower() if title_item else ""
                process = process_item.text().lower() if process_item else ""

                if search_type == "全部":
                    match = text_lower in title or text_lower in process
                elif search_type == "标题":
                    match = text_lower in title
                else:
                    match = text_lower in process

                table.setRowHidden(row, not match)

    def _on_clear_window_search(self) -> None:
        """清除窗口搜索"""
        self.window_search_input.clear()

    def _init_connections(self) -> None:
        """连接信号"""
        self.selected_window_table.window_double_clicked.connect(
            self._on_window_double_clicked
        )
        self.foreground_window_table.window_double_clicked.connect(
            self._on_window_double_clicked
        )
        self.switch_window_table.window_double_clicked.connect(
            self._on_switch_window_double_clicked
        )

        self.selected_window_table.status_header_clicked.connect(
            self._on_type_header_clicked
        )
        self.foreground_window_table.status_header_clicked.connect(
            self._on_type_header_clicked
        )
        self.switch_window_table.status_header_clicked.connect(
            self._on_type_header_clicked
        )

        self.foreground_window_table.customContextMenuRequested.connect(
            self._on_window_context_menu
        )
        self.switch_window_table.customContextMenuRequested.connect(
            self._on_switch_window_context_menu
        )
        self.selected_window_table.customContextMenuRequested.connect(
            self._on_selected_window_context_menu
        )

        self.selected_window_table.column_visibility_changed.connect(
            self._save_hidden_columns_config
        )
        self.foreground_window_table.column_visibility_changed.connect(
            self._save_hidden_columns_config
        )
        self.switch_window_table.column_visibility_changed.connect(
            self._save_hidden_columns_config
        )

    def _on_type_header_clicked(self) -> None:
        """处理类型列头点击事件"""
        self.refresh_windows()

    def _on_auto_refresh_changed(self, state):
        """处理自动刷新开关状态变化"""
        if state == Qt.CheckState.Checked:
            from constants import UIMainConstants
            refresh_interval = (
                getattr(self.config, "auto_refresh_interval", UIMainConstants.DEFAULT_AUTO_REFRESH_INTERVAL)
                * 1000
            )
            self._refresh_timer.start(int(refresh_interval))
        else:
            self._refresh_timer.stop()

    def _on_refresh_interval_changed(self):
        """处理刷新间隔变化"""
        try:
            interval = float(self.refresh_interval_spinbox.text())
            if interval > 0:
                if self.config:
                    self.config.auto_refresh_interval = interval
                    if self.config_manager:
                        self.config_manager.save(self.config)
                if self.auto_refresh_checkbox.isChecked():
                    self._refresh_timer.stop()
                    self._refresh_timer.start(int(interval * 1000))
        except ValueError:
            default_interval = getattr(self.config, "auto_refresh_interval", 5.0)
            self.refresh_interval_spinbox.setText(str(default_interval))

    # ==================== 表格更新方法 ====================

    def _get_selected_status_text(self, hwnd: int) -> str:
        """获取窗口选中状态文本"""
        return "✓" if hwnd in self._selected_windows else ""

    def _get_window_status_text(self, window: WindowInfo) -> str:
        """获取窗口状态文本"""
        if not SafeWindowsAPI.is_window(window.hwnd):
            if window.is_taskbar is False:
                return "后台"
            if window.pid:
                try:
                    import psutil
                    if psutil.pid_exists(window.pid):
                        return "后台"
                except Exception:
                    pass
            return "退出"
        if window.is_taskbar is True:
            return "可见"
        if window.is_taskbar is False:
            return "后台"
        if SafeWindowsAPI.is_taskbar_window(window.hwnd):
            return "可见"
        return "后台"

    def _on_window_check_changed(self, hwnd: int, state: int) -> None:
        """处理窗口选择状态变化"""
        if state == Qt.CheckState.Checked:
            with self._lock:
                self._selected_windows.add(hwnd)
        else:
            with self._lock:
                self._selected_windows.discard(hwnd)
        if self.config:
            self._save_selected_windows_to_config()
        self.refresh_windows()

    def _update_window_table_incremental(
        self,
        table,
        windows: List[WindowInfo],
        allow_check: bool = True,
    ) -> None:
        """增量更新窗口表格"""
        from theme import theme

        table.setRowCount(0)
        for window in windows:
            row = table.rowCount()
            table.insertRow(row)
            self._update_table_row(table, row, window, allow_check)

    def _update_table_row(
        self, table, row: int, window: WindowInfo, allow_check: bool = True,
    ) -> None:
        """更新表格中的一行"""
        from PySide6.QtWidgets import QCheckBox, QWidget, QHBoxLayout
        from theme import theme

        # 选择列（复选框）
        if allow_check:
            check_widget = table.cellWidget(row, 0)
            if check_widget:
                check_box = check_widget.findChild(QCheckBox)
                if check_box:
                    check_box.setChecked(window.hwnd in self._selected_windows)
            else:
                check_box = QCheckBox()
                check_box.setChecked(window.hwnd in self._selected_windows)
                check_box.stateChanged.connect(
                    lambda state, hwnd=window.hwnd: self._on_window_check_changed(hwnd, state)
                )
                check_widget = QWidget()
                check_layout = QHBoxLayout(check_widget)
                check_layout.addWidget(check_box)
                check_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                check_layout.setContentsMargins(0, 0, 0, 0)
                table.setCellWidget(row, 0, check_widget)
        else:
            check_item = table.item(row, 0)
            selected_text = self._get_selected_status_text(window.hwnd)
            if check_item:
                check_item.setText(selected_text)
            else:
                check_item = QTableWidgetItem(selected_text)
                check_item.setFlags(check_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                check_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row, 0, check_item)

        # 类型列
        status_text = self._get_window_status_text(window)
        status_item = table.item(row, 1)
        if status_item:
            status_item.setText(status_text)
        else:
            status_item = QTableWidgetItem(status_text)
            status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(row, 1, status_item)

        if status_text == "退出":
            exit_color = (
                theme.COLOR_EXIT_STATUS if hasattr(theme, "COLOR_EXIT_STATUS") else "#808080"
            )
            for col in range(table.columnCount()):
                item = table.item(row, col)
                if item:
                    item.setBackground(QColor(exit_color))
                    item.setForeground(QColor("#FFFFFF"))
            if allow_check:
                check_widget = table.cellWidget(row, 0)
                if check_widget:
                    check_box = check_widget.findChild(QCheckBox)
                    if check_box:
                        check_box.setEnabled(False)

        # 标题列
        title_item = table.item(row, 2)
        if title_item:
            title_item.setText(window.title)
            title_item.setData(Qt.ItemDataRole.UserRole, window.hwnd)
            title_item.setData(Qt.ItemDataRole.UserRole + 1, window.process_name)
        else:
            title_item = QTableWidgetItem(window.title)
            title_item.setFlags(title_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            title_item.setData(Qt.ItemDataRole.UserRole, window.hwnd)
            title_item.setData(Qt.ItemDataRole.UserRole + 1, window.process_name)
            table.setItem(row, 2, title_item)

        # 进程名列
        proc_item = table.item(row, 3)
        if proc_item:
            proc_item.setText(window.process_name)
        else:
            proc_item = QTableWidgetItem(window.process_name)
            proc_item.setFlags(proc_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(row, 3, proc_item)

        # 显示器列
        monitor_name = getattr(window, "monitor_name", "")
        if not monitor_name:
            from core import SafeWindowsAPI
            monitor = SafeWindowsAPI.get_window_monitor(window.hwnd)
            if monitor:
                monitor_name = "主显" if monitor.is_primary else "副显"
            else:
                monitor_name = "未知显示器"
        monitor_item = table.item(row, 4)
        if monitor_item:
            monitor_item.setText(monitor_name)
        else:
            monitor_item = QTableWidgetItem(monitor_name)
            monitor_item.setFlags(monitor_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(row, 4, monitor_item)

    def _on_refresh_finished(self, classified) -> None:
        """处理窗口刷新完成的回调"""
        try:
            from constants import UIMainConstants

            self._update_window_table_incremental(
                self.selected_window_table, classified.selected, allow_check=True
            )
            self._update_window_table_incremental(
                self.foreground_window_table, classified.foreground, allow_check=False
            )
            self._update_switch_window_table()

            timestamp = QDateTime.currentDateTime().toString("HH:mm:ss")
            total = len(classified.selected) + len(classified.foreground)
            self.status_updated.emit(f"已刷新 {total} 个窗口 {timestamp}")

            self._auto_select_keyword_windows(skip_refresh=True)
        except Exception as e:
            logger.warning("处理刷新结果失败: %s", str(e))

    def _on_window_context_menu(self, position) -> None:
        """窗口列表右键菜单"""
        table = self.sender()
        selected_row = table.currentRow()
        if selected_row < 0:
            return

        title_item = table.item(selected_row, 2)
        if not title_item:
            return

        hwnd = title_item.data(Qt.ItemDataRole.UserRole)
        process_name = title_item.data(Qt.ItemDataRole.UserRole + 1)
        if hwnd is None:
            return

        menu = QMenu()
        add_to_menu = QMenu("添加到", self)

        add_to_hidden_action = QAction("隐藏窗口", self)
        add_to_hidden_action.triggered.connect(lambda: self._select_window(hwnd))
        add_to_menu.addAction(add_to_hidden_action)

        add_to_switch_action = QAction("切换窗口", self)
        add_to_switch_action.triggered.connect(
            lambda h=hwnd, p=process_name: self._add_switch_window_by_hwnd(h, p)
        )
        add_to_menu.addAction(add_to_switch_action)
        menu.addMenu(add_to_menu)

        restore_action = QAction("恢复窗口", self)
        restore_action.triggered.connect(lambda: self._restore_hidden_window(hwnd))
        menu.addAction(restore_action)

        remove_action = QAction("移除", self)
        remove_action.triggered.connect(lambda: self._remove_window(hwnd))
        menu.addAction(remove_action)

        menu.exec(table.mapToGlobal(position))

    def _on_selected_window_context_menu(self, position) -> None:
        """选中窗口列表右键菜单"""
        selected_rows = self.selected_window_table.selectionModel().selectedRows()
        menu = QMenu()

        if not selected_rows:
            add_action = QAction("添加进程", self)
            add_action.triggered.connect(self._show_add_process_dialog)
            menu.addAction(add_action)
            menu.exec(self.selected_window_table.mapToGlobal(position))
            return

        hwnds = []
        for idx in selected_rows:
            row = idx.row()
            title_item = self.selected_window_table.item(row, 2)
            if not title_item:
                continue
            hwnd = title_item.data(Qt.ItemDataRole.UserRole)
            if hwnd is not None:
                hwnds.append(hwnd)

        if not hwnds:
            return

        process_names = set()
        for row_idx in selected_rows:
            row = row_idx.row()
            process_item = self.selected_window_table.item(row, 3)
            if process_item:
                process_names.add(process_item.text())

        if len(hwnds) == 1:
            remove_action = QAction("移除", self)
            remove_action.triggered.connect(lambda: self._remove_window_from_selected(hwnds[0]))
            menu.addAction(remove_action)
        else:
            remove_action = QAction(f"移除选中项 ({len(hwnds)}项)", self)
            remove_action.triggered.connect(lambda: self._remove_windows_from_selected_batch(hwnds))
            menu.addAction(remove_action)

        menu.addSeparator()

        if process_names:
            process_name = next(iter(process_names))
            restore_action = QAction(f"恢复显示所有 {process_name} 窗口", self)
            restore_action.triggered.connect(lambda: self._restore_process_windows(process_name))
            menu.addAction(restore_action)

        menu.exec(self.selected_window_table.mapToGlobal(position))

    def _on_auto_selected(self, hwnd: int) -> None:
        """处理自动选中的窗口（从后台线程通过信号传来）"""
        self._selected_windows.add(hwnd)

    def _on_hwnd_updated(self, old_hwnd: int, new_hwnd: int) -> None:
        """处理窗口句柄更新（从后台线程通过信号传来）"""
        if old_hwnd in self._selected_windows:
            self._selected_windows.discard(old_hwnd)
            self._selected_windows.add(new_hwnd)
