# -*- coding: utf-8 -*-
# windowmanager/window_manager_ui.py
"""
UI 布局与更新 Mixin - 包含 MainWindowTab 的 UI 初始化和表格更新方法
"""

import logging
from typing import List, Set, TYPE_CHECKING

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidgetItem, QHeaderView, QGroupBox, QLineEdit,
    QSplitter, QCheckBox, QAbstractItemView, QMenu,
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt, QDateTime

from window_base import WindowInfo
from core import SafeWindowsAPI
from deps import psutil

logger = logging.getLogger(__name__)


class WindowManagerUIMixin:  # pylint: disable=no-member
    """UI 布局与更新 Mixin - 提供 UI 初始化和表格更新能力

    注意：_selected_windows, window_manager 等属性由宿主类 MainWindowTab 提供
    """

    if TYPE_CHECKING:
        from manager import WindowManager
        _selected_windows: Set[int]
        window_manager: WindowManager

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
        clear_keywords_btn.clicked.connect(self.clear_all_keywords)
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

        # 恢复主窗口垂直分栏宽度（隐藏/可见/切换窗口表格的高度比例）
        saved_sizes = getattr(self.config.layout, "main_vertical_splitter_sizes", []) if self.config else []
        if not saved_sizes:
            saved_sizes = getattr(self.config.layout, "main_splitter_sizes", [])
        if saved_sizes and len(saved_sizes) == 3:
            self.window_splitter.setSizes(saved_sizes)
        else:
            self.window_splitter.setSizes([120, 250, 120])

        # 监听分栏宽度变化，实时保存
        self.window_splitter.splitterMoved.connect(self._save_main_vertical_splitter_sizes)

        self.right_layout.addWidget(self.window_splitter)

    def _save_main_horizontal_splitter_sizes(self) -> None:
        """保存主窗口水平分栏宽度（关键字列表 ↔ 窗口表格）"""
        if not self.config or not self.config_manager:
            return
        sizes = self.main_splitter.sizes()
        if len(sizes) == 2:
            self.config.layout.main_horizontal_splitter_sizes = list(sizes)
            try:
                self.config_manager.save(self.config)
                logger.debug("已保存主窗口水平分栏宽度: %s", sizes)
            except Exception as e:
                logger.error("保存主窗口水平分栏宽度失败: %s", str(e))

    def _save_main_vertical_splitter_sizes(self) -> None:
        """保存主窗口垂直分栏宽度（隐藏/可见/切换窗口表格）"""
        if not self.config or not self.config_manager:
            return
        sizes = self.window_splitter.sizes()
        if len(sizes) == 3:
            self.config.layout.main_vertical_splitter_sizes = list(sizes)
            self.config.layout.main_splitter_sizes = list(sizes)
            try:
                self.config_manager.save(self.config)
                logger.debug("已保存主窗口垂直分栏宽度: %s", sizes)
            except Exception as e:
                logger.error("保存主窗口垂直分栏宽度失败: %s", str(e))

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
        show_btn.clicked.connect(self.show_selected_hidden_windows)  # ✅ 修复：只显示不最小化
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

        # 恢复主窗口水平分栏宽度（关键字列表 ↔ 窗口表格）
        saved_sizes = getattr(self.config.layout, "main_horizontal_splitter_sizes", []) if self.config else []
        if saved_sizes and len(saved_sizes) == 2:
            self.main_splitter.setSizes(saved_sizes)
        else:
            self.main_splitter.setSizes([200, 600])

        # 监听水平分栏宽度变化，实时保存
        self.main_splitter.splitterMoved.connect(self._save_main_horizontal_splitter_sizes)

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

    def _on_auto_refresh_changed(self, state) -> None:
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

    def _on_refresh_interval_changed(self) -> None:
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

    def _get_selected_status_text(self, hwnd: int) -> str:
        """获取窗口选中状态文本"""
        return "✓" if hwnd in self._selected_windows else ""

    def _get_window_status_text(self, window: WindowInfo) -> str:
        """获取窗口状态文本

        注意：已退出的窗口应在渲染前由 _cleanup_exited_windows 过滤，
        不应到达此函数。此处保留 hwnd 无效 + 进程存活的 "后台" 判断作为防御。

        Args:
            window: 窗口信息

        Returns:
            str: 状态文本（"可见" 或 "后台"）
        """
        if not SafeWindowsAPI.is_window(window.hwnd):
            # 窗口句柄无效，检查进程是否仍在运行
            if window.pid:
                try:
                    if psutil and psutil.pid_exists(window.pid):
                        return "后台"
                except Exception:
                    pass
            # hwnd 无效且进程不存在 — 理论上不应到达此处（已由 _cleanup_exited_windows 过滤）
            logger.warning(
                "未过滤的退出窗口到达 _get_window_status_text: hwnd=%d, title=%s, pid=%s",
                window.hwnd, window.title, window.pid,
            )
            return "后台"
        if window.is_taskbar is True:
            return "可见"
        if window.is_taskbar is False:
            return "后台"
        if SafeWindowsAPI.is_taskbar_window(window.hwnd):
            return "可见"
        return "后台"

    def _on_window_check_changed(self, hwnd: int, state: int) -> None:
        """处理窗口选择状态变化（带 PID 去重）"""
        if state == Qt.CheckState.Checked:
            # one-VW-per-PID: 添加前移除同 PID 的旧 hwnd
            self._remove_same_pid_from_selected(hwnd)
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
        table.setRowCount(0)
        for window in windows:
            row = table.rowCount()
            table.insertRow(row)
            self._update_table_row(table, row, window, allow_check)

    def _update_table_row(
        self, table, row: int, window: WindowInfo, allow_check: bool = True,
    ) -> None:
        """更新表格中的一行"""
        self._update_check_column(table, row, window, allow_check)
        self._update_status_column(table, row, window)

        self._update_text_column(table, row, 2, window.title, window.hwnd, window.process_name)
        self._update_text_column(table, row, 3, window.process_name)

        # 第4列显示 HWND（数字窗口句柄）
        hwnd_text = str(window.hwnd) if window.hwnd else ""
        self._update_text_column(table, row, 4, hwnd_text)

    def _update_check_column(self, table, row: int, window: WindowInfo, allow_check: bool) -> None:
        """更新选择列（复选框或文本）"""
        from PySide6.QtWidgets import QCheckBox, QWidget, QHBoxLayout

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
            selected_text = self._get_selected_status_text(window.hwnd)
            self._update_text_column(table, row, 0, selected_text, align_center=True)

    def _update_status_column(self, table, row: int, window: WindowInfo) -> str:
        """更新类型/状态列，返回状态文本"""
        status_text = self._get_window_status_text(window)
        self._update_text_column(table, row, 1, status_text)
        return status_text

    def _update_text_column(
        self, table, row: int, col: int, text: str,
        user_data=None, extra_data=None, align_center: bool = False,
    ) -> None:
        """更新表格中的文本列"""
        item = table.item(row, col)
        if item:
            item.setText(text)
        else:
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if align_center:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, col, item)

        if user_data is not None:
            item.setData(Qt.ItemDataRole.UserRole, user_data)
        if extra_data is not None:
            item.setData(Qt.ItemDataRole.UserRole + 1, extra_data)

    def _on_refresh_finished(self, classified) -> None:
        """处理窗口刷新完成的回调 - 增强错误处理"""
        logger.debug("_on_refresh_finished: 开始处理刷新结果")
        try:
            # 保存超级窗口字典供后续使用（恢复/保存/关键字匹配等）
            if hasattr(classified, "super_windows_by_process"):
                self._super_windows_by_process = classified.super_windows_by_process

            # 先清理已退出进程的窗口（从所有数据结构和配置中移除）
            logger.debug("_on_refresh_finished: 调用 _cleanup_exited_windows...")
            exited_hwnds = self._cleanup_exited_windows(classified.selected)
            logger.debug("_on_refresh_finished: _cleanup_exited_windows 完成, 退出窗口数=%d", len(exited_hwnds))

            # 过滤掉已退出的窗口，确保不在表格中显示"已退出"状态
            if exited_hwnds:
                classified.selected = [
                    w for w in classified.selected if w.hwnd not in exited_hwnds
                ]

            # 更新三个表格（选中、可见、切换）
            logger.debug("_on_refresh_finished: 更新选中窗口表格...")
            self._update_window_table_incremental(
                self.selected_window_table, classified.selected, allow_check=True
            )
            logger.debug("_on_refresh_finished: selected_window_table 更新完成")

            logger.debug("_on_refresh_finished: 更新可见窗口表格...")
            self._update_window_table_incremental(
                self.foreground_window_table, classified.foreground, allow_check=False
            )
            logger.debug("_on_refresh_finished: foreground_window_table 更新完成")

            logger.debug("_on_refresh_finished: 更新切换窗口表格...")
            self._update_switch_window_table(classified.foreground)
            logger.debug("_on_refresh_finished: switch_window_table 更新完成")

            timestamp = QDateTime.currentDateTime().toString("HH:mm:ss")
            total = len(classified.selected) + len(classified.foreground)
            status_msg = f"已刷新 {total} 个窗口 {timestamp}"
            logger.debug("_on_refresh_finished: %s", status_msg)
            self.status_updated.emit(status_msg)

            # 刷新后重新检查关键字匹配（跳过递归刷新）
            self._auto_select_keyword_windows(skip_refresh=True)
            logger.debug("_on_refresh_finished: 处理完成")
        except Exception as e:
            logger.error(
                "_on_refresh_finished: 处理刷新结果失败 [严重] - %s",
                str(e), exc_info=True
            )
            # 尝试发送错误状态到状态栏，让用户知道出了问题
            try:
                self.status_updated.emit(f"刷新失败: {str(e)}")
            except Exception:
                pass

    def _cleanup_exited_windows(self, windows: List) -> set:
        """清理已退出进程的窗口

        遍历窗口列表，如果窗口/进程已退出，
        从 selected_windows、_hidden_windows、_software_hidden_windows 和 config.target_windows 中彻底移除。

        Returns:
            set: 已退出的窗口句柄集合，调用方据此过滤渲染列表
        """
        if not self.config:
            return set()

        exited_hwnds = set()
        for window in windows:
            # 检查窗口是否已退出（句柄无效且进程不存在）
            if not SafeWindowsAPI.is_window(window.hwnd):
                if window.pid:
                    try:
                        if psutil and psutil.pid_exists(window.pid):
                            # 进程仍在运行，只是窗口句柄失效（可能被销毁重建），跳过
                            continue
                    except Exception:
                        pass
                # 确认进程已退出，标记为待清理
                exited_hwnds.add(window.hwnd)

        if not exited_hwnds:
            return set()

        logger.info("清理 %d 个已退出进程的隐藏窗口: %s", len(exited_hwnds), exited_hwnds)

        # 1. 从 selected_windows 中移除
        with self._lock:
            self._selected_windows -= exited_hwnds

        # 2. 从 WindowManager 内部数据结构中彻底移除
        if self.window_manager:
            self.window_manager.remove_hidden_windows(exited_hwnds)
            logger.info("已从 WindowManager 内部数据中移除 %d 个退出窗口", len(exited_hwnds))

        # 3. 从 config.target_windows 中移除并持久化
        if hasattr(self.config, "target_windows"):
            self.config.target_windows = [
                w for w in self.config.target_windows
                if isinstance(w, dict) and w.get("hwnd") not in exited_hwnds
            ]
            if self.config_manager:
                self.config_manager.save(self.config)

        self.status_updated.emit(f"已清理 {len(exited_hwnds)} 个已退出的窗口")
        return exited_hwnds

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
        """处理自动选中的窗口（从后台线程通过信号传来，带 PID 去重）"""
        self._remove_same_pid_from_selected(hwnd)
        with self._lock:
            self._selected_windows.add(hwnd)

    def _on_hwnd_updated(self, old_hwnd: int, new_hwnd: int) -> None:
        """处理窗口句柄更新（从后台线程通过信号传来）"""
        with self._lock:
            if old_hwnd in self._selected_windows:
                self._selected_windows.discard(old_hwnd)
                self._selected_windows.add(new_hwnd)
