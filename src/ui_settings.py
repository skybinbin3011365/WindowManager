# -*- coding: utf-8 -*-
# windowmanager/ui_settings.py
"""
窗口管理器 - 设置模块 (PySide6 版本)
包含热键设置、时间校准等配置功能
"""

import sys
import os
import logging

# 延迟导入 asyncio，避免打包时的问题
from typing import Optional, TYPE_CHECKING

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QGroupBox,
    QMessageBox,
    QCheckBox,
    QComboBox,
    QSpinBox,
    QSplitter,
)
from PySide6.QtCore import Signal, QThread, Qt
from PySide6.QtGui import QFont

from constants import NTPConstants, UIMainConstants
from utils import HotkeyFormatter


from time_sync import SyncResult
from theme import theme

if TYPE_CHECKING:
    from config import ConfigManager, Config
    import hotkey_manager

logger = logging.getLogger(__name__)


class NtpSyncThread(QThread):
    """NTP同步线程"""

    finished = Signal(object, object)  # (SyncResult, Dict[str, float])

    def __init__(self, time_sync_tool):
        super().__init__()
        self.time_sync_tool = time_sync_tool

    def run(self):
        """在后台线程中执行NTP同步"""
        try:
            result, response_times = self.time_sync_tool.sync_time_blocking()
            self.finished.emit(result, response_times)
        except Exception as e:
            logger.error("NTP同步异常: %s", str(e))
            self.finished.emit(SyncResult(success=False, message=str(e)), {})


class SettingsTab(QWidget):
    """设置选项卡 - PySide6版本"""

    # 定义信号 - 热键更改时通知主窗口
    hotkeys_changed = Signal()

    # 定义状态更新信号 - 用于通知主窗口更新状态栏
    status_update = Signal(str)  # 状态消息

    def __init__(
        self,
        config_manager: Optional["ConfigManager"] = None,
        config: Optional["Config"] = None,
        hotkey_manager: Optional["hotkey_manager.HotkeyManager"] = None,
        parent_window: Optional[QWidget] = None,
        window_manager: Optional[object] = None,
    ) -> None:
        """初始化设置选项卡

        Args:
            config_manager: 配置管理器实例
            config: 配置对象
            hotkey_manager: 热键管理器实例
            parent_window: 父窗口（主窗口实例）
            window_manager: 窗口管理器实例
        """
        super().__init__()

        self.config_manager = config_manager
        self.config = config
        self.hotkey_manager = hotkey_manager
        self.parent_window = parent_window
        self.window_manager = window_manager

        # 初始化 UI
        self._init_ui()
        self._load_settings()

        # 时间同步工具（由TimeSettingsWidget管理）
        self.time_sync_tool = None

    def _init_ui(self) -> None:
        """初始化 UI 组件 - 使用两栏垂直布局，可拖动调整宽度"""
        self.setStyleSheet(theme.get_global_stylesheet())

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(8)

        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 1)

        self.main_splitter.addWidget(self._create_left_panel())
        self.main_splitter.addWidget(self._create_right_panel())

        main_layout.addWidget(self.main_splitter)
        self._restore_splitter_sizes()

    def _create_left_panel(self) -> QWidget:
        """创建左栏面板（热键设置）"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        hotkey_group = QGroupBox("热键设置")
        hotkey_group_layout = QVBoxLayout(hotkey_group)
        hotkey_group_layout.setContentsMargins(10, 8, 10, 8)
        hotkey_group_layout.setSpacing(6)

        from widgets.hotkey_settings import HotkeySettingsWidget

        self.hotkey_settings_widget = HotkeySettingsWidget(
            config_manager=self.config_manager,
            config=self.config,
            hotkey_manager=self.hotkey_manager,
            parent_window=self,
        )
        self.hotkey_settings_widget.hotkeys_changed.connect(self.hotkeys_changed.emit)
        hotkey_group_layout.addWidget(self.hotkey_settings_widget)

        layout.addWidget(hotkey_group)
        layout.addStretch()
        return widget

    def _create_right_panel(self) -> QWidget:
        """创建右栏面板（时间设置、NTP表格、自动校准、开机自启动、保存按钮）"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        layout.addWidget(self._create_time_settings_widget())
        layout.addWidget(self._create_ntp_servers_section())
        layout.addWidget(self._create_calibration_config_group())
        layout.addLayout(self._create_auto_start_layout())
        layout.addLayout(self._create_save_reset_layout())
        layout.addStretch()

        return widget

    def _create_time_settings_widget(self) -> QWidget:
        """创建时间设置组件"""
        from widgets.time_settings import TimeSettingsWidget

        self.time_settings_widget = TimeSettingsWidget(parent_window=self)
        ntp_servers = getattr(self.config.ntp, "ntp_servers", NTPConstants.DEFAULT_NTP_SERVERS)
        self.time_settings_widget.set_ntp_servers(ntp_servers)
        self.time_settings_widget.ntp_response_times_ready.connect(self._update_ntp_servers_table)
        return self.time_settings_widget

    def _create_ntp_servers_section(self) -> QWidget:
        """创建NTP服务器响应时间标签和表格"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        ntp_servers_label = QLabel("NTP 服务器响应时间")
        ntp_servers_label.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        layout.addWidget(ntp_servers_label)

        self.ntp_servers_table = QTableWidget()
        self.ntp_servers_table.setColumnCount(2)
        self.ntp_servers_table.setHorizontalHeaderLabels(["服务器", "响应时间"])
        self.ntp_servers_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.ntp_servers_table.setColumnWidth(1, 100)
        self.ntp_servers_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.ntp_servers_table.setEditTriggers(QTableWidget.AllEditTriggers)
        self.ntp_servers_table.setMinimumHeight(160)
        self.ntp_servers_table.setMaximumHeight(200)
        self.ntp_servers_table.horizontalHeader().setStyleSheet(
            "QHeaderView::section { background-color: #1E88E5; color: white; font-weight: bold; }"
        )
        layout.addWidget(self.ntp_servers_table)

        return container

    def _create_calibration_config_group(self) -> QGroupBox:
        """创建自动校准配置分组（检查间隔、误差阈值、校准周期）"""
        group = QGroupBox("自动校准配置")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        layout.addLayout(self._create_interval_layout())
        layout.addLayout(self._create_threshold_layout())
        layout.addLayout(self._create_calibration_layout())

        return group

    def _create_interval_layout(self) -> QHBoxLayout:
        """创建检查间隔布局"""
        layout = QHBoxLayout()
        layout.setSpacing(5)
        layout.addWidget(QLabel("检查间隔:"))
        self.interval_combo = QComboBox()
        self.interval_combo.addItems(["30", "60", "120", "300"])
        self.interval_combo.setCurrentIndex(1)
        self.interval_combo.setFixedWidth(80)
        layout.addWidget(self.interval_combo)
        layout.addWidget(QLabel("秒"))
        layout.addStretch()
        return layout

    def _create_threshold_layout(self) -> QHBoxLayout:
        """创建误差阈值布局"""
        layout = QHBoxLayout()
        layout.setSpacing(5)
        layout.addWidget(QLabel("误差阈值:"))
        self.threshold_spin = QSpinBox()
        self.threshold_spin.setRange(1, 60)
        self.threshold_spin.setValue(5)
        self.threshold_spin.setFixedWidth(80)
        layout.addWidget(self.threshold_spin)
        layout.addWidget(QLabel("秒"))
        layout.addStretch()
        return layout

    def _create_calibration_layout(self) -> QHBoxLayout:
        """创建校准周期布局"""
        layout = QHBoxLayout()
        layout.setSpacing(5)
        layout.addWidget(QLabel("校准周期:"))
        self.calibration_interval_spin = QSpinBox()
        self.calibration_interval_spin.setRange(60, 86400)
        self.calibration_interval_spin.setValue(3600)
        self.calibration_interval_spin.setFixedWidth(80)
        layout.addWidget(self.calibration_interval_spin)
        layout.addWidget(QLabel("秒"))
        layout.addStretch()
        return layout

    def _create_auto_start_layout(self) -> QHBoxLayout:
        """创建开机自启动布局"""
        layout = QHBoxLayout()
        self.auto_start_check = QCheckBox("开机自启动")
        layout.addWidget(self.auto_start_check)
        layout.addStretch()
        return layout

    def _create_save_reset_layout(self) -> QHBoxLayout:
        """创建保存和恢复默认按钮布局"""
        layout = QHBoxLayout()
        layout.setSpacing(10)

        save_btn = QPushButton("保存设置")
        save_btn.setObjectName("successButton")
        save_btn.clicked.connect(self._save_settings)
        layout.addWidget(save_btn)

        reset_btn = QPushButton("恢复默认")
        reset_btn.setObjectName("dangerButton")
        reset_btn.clicked.connect(self._reset_settings)
        layout.addWidget(reset_btn)

        layout.addStretch()
        return layout

    def _restore_splitter_sizes(self) -> None:
        """从配置恢复分栏宽度"""
        if self.config and hasattr(self.config, "layout") and hasattr(self.config.layout, "settings_splitter_sizes"):
            try:
                sizes = self.config.layout.settings_splitter_sizes
                if isinstance(sizes, list) and len(sizes) == 3:
                    self.main_splitter.setSizes(sizes)
                    logger.info("已恢复分栏宽度: %s", sizes)
            except Exception as e:
                logger.warning("恢复分栏宽度失败: %s", str(e))

    def _save_splitter_sizes(self) -> None:
        """保存分栏宽度到配置"""
        if self.config:
            try:
                sizes = self.main_splitter.sizes()
                self.config.layout.settings_splitter_sizes = sizes
                logger.info("已保存分栏宽度: %s", sizes)
            except Exception as e:
                logger.warning("保存分栏宽度失败: %s", str(e))

    def _format_hotkey_for_display(self, hotkey: str) -> str:
        """将热键格式转换为用户友好的显示格式

        Args:
            hotkey: 原始热键字符串

        Returns:
            格式化后的热键字符串
        """
        return HotkeyFormatter.format_hotkey(hotkey)

    def _load_settings(self) -> None:
        """加载设置"""
        # 热键设置由HotkeySettingsWidget自动加载

        # 加载其他设置
        self.auto_start_check.setChecked(getattr(self.config, "auto_start", False))

        # 加载校准间隔
        calibration_interval = getattr(self.config.ntp, "calibration_interval", 30)
        self.calibration_interval_spin.setValue(calibration_interval)

    def _save_hotkeys(self) -> None:
        """保存热键设置"""
        self._save_settings()

    def _save_settings(self) -> None:
        """保存所有设置（包括热键和NTP配置）"""
        # 热键设置由HotkeySettingsWidget自动保存

        # 保存其他设置
        self.config.auto_start = self.auto_start_check.isChecked()

        # 保存NTP配置
        # 从表格中读取服务器列表
        ntp_servers = []
        for row in range(self.ntp_servers_table.rowCount()):
            server_item = self.ntp_servers_table.item(row, 0)
            if server_item:
                server = server_item.text().strip()
                if server:
                    ntp_servers.append(server)

        # 如果表格中有服务器，则保存，否则使用默认服务器
        if ntp_servers:
            self.config.ntp.ntp_servers = ntp_servers

        self.config.ntp.ntp_check_interval = int(self.interval_combo.currentText())
        self.config.ntp.ntp_error_threshold = self.threshold_spin.value()
        self.config.ntp.calibration_interval = self.calibration_interval_spin.value()

        # 保存日志开关状态（通过 AboutTab 的 API 接口，解耦跨选项卡依赖）
        if self.parent_window and hasattr(self.parent_window, "about_tab"):
            self.parent_window.about_tab.apply_log_options_to_config(self.config)

        self._save_config()

        # 保存分栏宽度
        self._save_splitter_sizes()

        # 发送信号通知主窗口刷新热键
        self.hotkeys_changed.emit()

        # 如果有父窗口引用，直接调用刷新方法
        if self.parent_window and hasattr(self.parent_window, "refresh_hotkeys"):
            self.parent_window.refresh_hotkeys()

        # 设置开机自启动
        self._set_auto_start(self.auto_start_check.isChecked())

        # 同步更新 TimeSyncTool 的 enable_log（无需重启立即生效）
        if self.time_sync_tool and hasattr(self.time_sync_tool, "enable_log"):
            self.time_sync_tool.enable_log = self.config.ntp.enable_ntp_log

        QMessageBox.information(self, "成功", "设置已保存")

    def _reset_settings(self) -> None:
        """恢复默认设置"""
        if self.config and self.config_manager:
            # 直接创建全新的默认配置对象（避免缓存导致恢复无效）
            from config import Config

            default_config = Config()

            # 热键设置由HotkeySettingsWidget处理，更新config即可
            self.config.hotkey.hide_hotkey = default_config.hotkey.hide_hotkey
            self.config.hotkey.show_hotkey = default_config.hotkey.show_hotkey

            # 恢复其他设置
            self.auto_start_check.setChecked(default_config.auto_start)

            # 恢复检查间隔和误差阈值
            interval_index = self.interval_combo.findText(str(default_config.ntp.ntp_check_interval))
            if interval_index >= 0:
                self.interval_combo.setCurrentIndex(interval_index)
            else:
                self.interval_combo.setCurrentIndex(1)

            self.threshold_spin.setValue(default_config.ntp.ntp_error_threshold)

            # 将当前 config 对象恢复为默认值（保留对象引用不变）
            for f_name, f_val in vars(default_config).items():
                setattr(self.config, f_name, f_val)

            # 保存配置
            self.config_manager.save(self.config)

            # 重新加载热键设置显示
            if hasattr(self, "hotkey_settings_widget") and self.hotkey_settings_widget:
                self.hotkey_settings_widget._load_hotkeys()

            QMessageBox.information(self, "成功", "已恢复默认设置")

    def _set_auto_start(self, enabled: bool) -> None:
        """设置开机自启动

        Args:
            enabled: 是否启用
        """
        if sys.platform == "win32":
            import winreg

            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            app_name = "WinHide"

            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)

                if enabled:
                    if getattr(sys, "frozen", False) or hasattr(sys, "__nuitka_binary__"):
                        exe_path = sys.executable
                    else:
                        exe_path = os.path.abspath(sys.argv[0])

                    winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, exe_path)
                    logger.info("已启用开机自启动：%s", exe_path)
                else:
                    try:
                        winreg.DeleteValue(key, app_name)
                        logger.info("已禁用开机自启动")
                    except FileNotFoundError:
                        pass

                winreg.CloseKey(key)

            except Exception as e:
                logger.error("设置开机自启动失败：%s", str(e))
                QMessageBox.warning(self, "警告", f"设置开机自启动失败: {str(e)}")

    def _save_config(self) -> None:
        """保存配置"""
        if self.config_manager:
            self.config_manager.save(self.config)

    def cleanup(self) -> None:
        """清理资源，停止运行中的线程"""
        try:
            # 停止 NTP 同步线程
            ntp_thread = getattr(self, "ntp_sync_thread", None)
            if ntp_thread:
                self._safe_stop_thread(ntp_thread, "NTP同步线程")
                self.ntp_sync_thread = None

            # 停止校准线程
            cal_thread = getattr(self, "calibration_thread", None)
            if cal_thread:
                self._safe_stop_thread(cal_thread, "校准线程")
                self.calibration_thread = None
        except Exception as e:
            logger.error("清理资源时发生错误: %s", str(e))

    def _safe_stop_thread(self, thread: QThread, thread_name: str) -> None:
        """安全停止线程

        Args:
            thread: 要停止的线程
            thread_name: 线程名称（用于日志）
        """
        if thread is None:
            return

        try:
            # 请求中断
            if hasattr(thread, "requestInterruption"):
                thread.requestInterruption()

            # 如果线程正在运行，等待它完全结束
            if thread.isRunning():
                # 尝试多次等待
                max_attempts = 3
                for attempt in range(max_attempts):
                    if not thread.isRunning():
                        break
                    # 等待线程结束（每次等1秒）
                    if thread.wait(UIMainConstants.THREAD_WAIT_TIMEOUT):
                        logger.info("%s已安全停止", thread_name)
                        break
                    logger.warning(
                            "%s等待退出超时 (尝试 %d/%d)",
                            thread_name,
                            attempt + 1,
                            max_attempts,
                        )
                else:
                    if thread.isRunning():
                        logger.warning("强制终止%s", thread_name)
                        thread.terminate()
                        thread.wait(UIMainConstants.THREAD_WAIT_TIMEOUT)
                        logger.info("%s已被强制终止", thread_name)

            # 标记为待删除
            thread.deleteLater()
        except RuntimeError as e:
            # 忽略对象已删除的错误
            logger.debug("%s对象可能已删除: %s", thread_name, str(e))
        except Exception as e:
            logger.error("停止%s时发生错误: %s", thread_name, str(e))

    def set_time_sync_tool(self, time_sync_tool) -> None:
        """设置时间同步工具

        Args:
            time_sync_tool: TimeSyncTool实例
        """
        self.time_sync_tool = time_sync_tool
        # 时间同步工具已在TimeSettingsWidget中使用

    def _update_ntp_servers_table(self, response_times: dict) -> None:
        """更新 NTP 服务器响应时间表格

        Args:
            response_times: 服务器响应时间字典，格式为 {server: response_time}
        """
        # 清空表格
        self.ntp_servers_table.setRowCount(0)

        # 转换为列表并按响应时间排序
        sorted_servers = sorted(response_times.items(), key=lambda x: x[1])

        # 重建表格
        self.ntp_servers_table.setRowCount(len(sorted_servers))

        for row, (server, response_time) in enumerate(sorted_servers):
            # 服务器名称
            server_item = QTableWidgetItem(server)
            self.ntp_servers_table.setItem(row, 0, server_item)

            # 响应时间
            if response_time == float("inf"):
                time_text = "超时"
            else:
                time_text = f"{response_time:.0f}ms"
            time_item = QTableWidgetItem(time_text)
            time_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.ntp_servers_table.setItem(row, 1, time_item)
