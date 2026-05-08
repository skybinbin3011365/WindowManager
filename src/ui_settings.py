# windowmanager/ui_settings.py
"""
窗口管理器 - 设置模块 (PySide6 版本)
包含热键设置、进程白名单、时间校准等配置功能
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
    QInputDialog,
    QCheckBox,
    QComboBox,
    QSpinBox,
    QSplitter,
)
from PySide6.QtCore import Signal, QTimer, QThread, Qt
from PySide6.QtGui import QFont

from constants import NTPConstants
from utils import HotkeyFormatter, create_list_group_widget


from time_sync import SyncResult
from theme import theme

if TYPE_CHECKING:
    from .config import ConfigManager, Config
    from . import hotkey_manager

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

        # 初始化自动刷新黑白名单的定时器
        self._init_auto_refresh()

    def _init_auto_refresh(self) -> None:
        """初始化自动刷新黑白名单的定时器"""
        # 创建定时器，每60秒刷新一次黑白名单
        self._auto_refresh_timer = QTimer(self)
        self._auto_refresh_timer.timeout.connect(self._refresh_lists)
        # 启动定时器，60秒间隔
        self._auto_refresh_timer.start(60000)
        logger.info("已启动黑白名单自动刷新，间隔60秒")

    def _init_ui(self) -> None:
        """初始化 UI 组件 - 使用两栏垂直布局，可拖动调整宽度"""
        # 设置现代化样式
        self.setStyleSheet(theme.get_global_stylesheet())

        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(8)

        # 使用 QSplitter 实现可拖动的两栏布局
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setStretchFactor(0, 1)  # 左侧占二分之一
        self.main_splitter.setStretchFactor(1, 1)  # 右侧占二分之一

        # 左栏：热键设置和黑白名单
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(5, 5, 5, 5)
        left_layout.setSpacing(8)

        # 热键设置
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
        left_layout.addWidget(hotkey_group)

        # 黑名单（使用公共函数创建）
        blacklist_group, self.blacklist_list, self.add_blacklist_btn, self.remove_blacklist_btn = (
            create_list_group_widget("黑名单（无窗口进程）")
        )
        left_layout.addWidget(blacklist_group)

        # 白名单（使用公共函数创建）
        whitelist_group, self.whitelist_list, self.add_whitelist_btn, self.remove_whitelist_btn = (
            create_list_group_widget("白名单（前台进程）")
        )
        left_layout.addWidget(whitelist_group)

        # 刷新按钮
        refresh_layout = QHBoxLayout()
        refresh_layout.addStretch()
        self.refresh_list_btn = QPushButton("刷新列表")
        self.refresh_list_btn.setFixedWidth(100)
        refresh_layout.addWidget(self.refresh_list_btn)
        left_layout.addLayout(refresh_layout)

        left_layout.addStretch()
        self.main_splitter.addWidget(left_widget)

        # 右栏：时间设置和相关配置
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 5, 5, 5)
        right_layout.setSpacing(8)

        # 时间设置
        from widgets.time_settings import TimeSettingsWidget

        self.time_settings_widget = TimeSettingsWidget(parent_window=self)
        # 从配置文件加载 NTP 服务器列表
        ntp_servers = getattr(self.config, "ntp_servers", NTPConstants.DEFAULT_NTP_SERVERS)
        self.time_settings_widget.set_ntp_servers(ntp_servers)
        self.time_settings_widget.ntp_response_times_ready.connect(self._update_ntp_servers_table)
        right_layout.addWidget(self.time_settings_widget)

        # NTP服务器响应时间
        ntp_servers_label = QLabel("NTP 服务器响应时间")
        ntp_servers_label.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        right_layout.addWidget(ntp_servers_label)

        self.ntp_servers_table = QTableWidget()
        self.ntp_servers_table.setColumnCount(2)
        self.ntp_servers_table.setHorizontalHeaderLabels(["服务器", "响应时间"])
        self.ntp_servers_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.ntp_servers_table.setColumnWidth(1, 100)
        self.ntp_servers_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.ntp_servers_table.setEditTriggers(QTableWidget.AllEditTriggers)
        # 调整表格高度以显示所有NTP服务器（默认4个服务器，每个行高约30，加上表头40）
        self.ntp_servers_table.setMinimumHeight(160)
        self.ntp_servers_table.setMaximumHeight(200)
        self.ntp_servers_table.horizontalHeader().setStyleSheet(
            "QHeaderView::section { background-color: #1E88E5; color: white; font-weight: bold; }"
        )
        right_layout.addWidget(self.ntp_servers_table)

        # 自动校准配置
        config_group = QGroupBox("自动校准配置")
        config_group_layout = QVBoxLayout(config_group)
        config_group_layout.setContentsMargins(10, 8, 10, 8)
        config_group_layout.setSpacing(6)

        # 检查间隔
        interval_layout = QHBoxLayout()
        interval_layout.setSpacing(5)
        interval_layout.addWidget(QLabel("检查间隔:"))
        self.interval_combo = QComboBox()
        self.interval_combo.addItems(["30", "60", "120", "300"])
        self.interval_combo.setCurrentIndex(1)
        self.interval_combo.setFixedWidth(80)
        interval_layout.addWidget(self.interval_combo)
        interval_layout.addWidget(QLabel("秒"))
        interval_layout.addStretch()
        config_group_layout.addLayout(interval_layout)

        # 误差阈值
        threshold_layout = QHBoxLayout()
        threshold_layout.setSpacing(5)
        threshold_layout.addWidget(QLabel("误差阈值:"))
        self.threshold_spin = QSpinBox()
        self.threshold_spin.setRange(1, 60)
        self.threshold_spin.setValue(5)
        self.threshold_spin.setFixedWidth(80)
        threshold_layout.addWidget(self.threshold_spin)
        threshold_layout.addWidget(QLabel("秒"))
        threshold_layout.addStretch()
        config_group_layout.addLayout(threshold_layout)

        # 校准周期
        calibration_layout = QHBoxLayout()
        calibration_layout.setSpacing(5)
        calibration_layout.addWidget(QLabel("校准周期:"))
        self.calibration_interval_spin = QSpinBox()
        self.calibration_interval_spin.setRange(60, 86400)
        self.calibration_interval_spin.setValue(3600)
        self.calibration_interval_spin.setFixedWidth(80)
        calibration_layout.addWidget(self.calibration_interval_spin)
        calibration_layout.addWidget(QLabel("秒"))
        calibration_layout.addStretch()
        config_group_layout.addLayout(calibration_layout)
        right_layout.addWidget(config_group)

        # 开机自启动
        auto_start_layout = QHBoxLayout()
        self.auto_start_check = QCheckBox("开机自启动")
        auto_start_layout.addWidget(self.auto_start_check)
        auto_start_layout.addStretch()
        right_layout.addLayout(auto_start_layout)

        # 保存和恢复默认按钮
        save_reset_layout = QHBoxLayout()
        save_reset_layout.setSpacing(10)

        save_btn = QPushButton("保存设置")
        save_btn.setObjectName("successButton")
        save_btn.clicked.connect(self._save_settings)
        save_reset_layout.addWidget(save_btn)

        reset_btn = QPushButton("恢复默认")
        reset_btn.setObjectName("dangerButton")
        reset_btn.clicked.connect(self._reset_settings)
        save_reset_layout.addWidget(reset_btn)

        save_reset_layout.addStretch()
        right_layout.addLayout(save_reset_layout)

        right_layout.addStretch()
        self.main_splitter.addWidget(right_widget)

        main_layout.addWidget(self.main_splitter)

        # 从配置恢复列宽比例
        self._restore_splitter_sizes()

        # 连接信号
        self.add_blacklist_btn.clicked.connect(self._add_blacklist)
        self.remove_blacklist_btn.clicked.connect(self._remove_blacklist)
        self.add_whitelist_btn.clicked.connect(self._add_whitelist)
        self.remove_whitelist_btn.clicked.connect(self._remove_whitelist)
        self.refresh_list_btn.clicked.connect(self._refresh_lists)

    def _restore_splitter_sizes(self) -> None:
        """从配置恢复分栏宽度"""
        if self.config and hasattr(self.config, "settings_splitter_sizes"):
            try:
                sizes = self.config.settings_splitter_sizes
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
                self.config.settings_splitter_sizes = sizes
                logger.info("已保存分栏宽度: %s", sizes)
            except Exception as e:
                logger.warning("保存分栏宽度失败: %s", str(e))

    def _add_blacklist(self):
        """添加进程到黑名单"""
        process_name, ok = QInputDialog.getText(
            self, "添加到黑名单", "请输入进程名（例如：chrome.exe）:"
        )
        if ok and process_name:
            if hasattr(self, "window_manager") and self.window_manager.add_to_blacklist(
                process_name
            ):
                QMessageBox.information(self, "成功", f"已添加 {process_name} 到黑名单")
                self._refresh_lists()
            else:
                QMessageBox.warning(self, "失败", f"添加 {process_name} 到黑名单失败")

    def _remove_blacklist(self):
        """从黑名单中删除进程"""
        selected_items = self.blacklist_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "提示", "请选择要删除的进程")
            return

        for item in selected_items:
            process_name = item.text()
            if hasattr(self, "window_manager"):
                self.window_manager.remove_from_blacklist(process_name)

        self._refresh_lists()
        QMessageBox.information(self, "成功", "已删除选中的进程")

    def _add_whitelist(self):
        """添加进程到白名单"""
        process_name, ok = QInputDialog.getText(
            self, "添加到白名单", "请输入进程名（例如：notepad.exe）:"
        )
        if ok and process_name:
            if hasattr(self, "window_manager") and self.window_manager.add_to_whitelist(
                process_name
            ):
                QMessageBox.information(self, "成功", f"已添加 {process_name} 到白名单")
                self._refresh_lists()
            else:
                QMessageBox.warning(self, "失败", f"添加 {process_name} 到白名单失败")

    def _remove_whitelist(self):
        """从白名单中删除进程"""
        selected_items = self.whitelist_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "提示", "请选择要删除的进程")
            return

        for item in selected_items:
            process_name = item.text()
            if hasattr(self, "window_manager"):
                self.window_manager.remove_from_whitelist(process_name)

        self._refresh_lists()
        QMessageBox.information(self, "成功", "已删除选中的进程")

    def _refresh_lists(self):
        """刷新黑白名单列表"""
        if (
            hasattr(self, "blacklist_list")
            and hasattr(self, "whitelist_list")
            and hasattr(self, "window_manager")
        ):
            # 清空列表
            self.blacklist_list.clear()
            self.whitelist_list.clear()

            # 加载黑名单
            blacklist = self.window_manager.get_blacklist()
            for process in sorted(blacklist):
                self.blacklist_list.addItem(process)

            # 加载白名单
            whitelist = self.window_manager.get_whitelist()
            for process in sorted(whitelist):
                self.whitelist_list.addItem(process)

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
        calibration_interval = getattr(self.config, "calibration_interval", 30)
        self.calibration_interval_spin.setValue(calibration_interval)

    def _preview_hotkey(self, hotkey_type: str) -> None:
        """热键预览功能"""
        # 由于使用了HotkeySettingsWidget，此方法暂时保留但不使用
        pass

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
            self.config.ntp_servers = ntp_servers

        self.config.ntp_check_interval = int(self.interval_combo.currentText())
        self.config.ntp_error_threshold = self.threshold_spin.value()
        self.config.calibration_interval = self.calibration_interval_spin.value()

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
            self.time_sync_tool.enable_log = self.config.enable_ntp_log

        QMessageBox.information(self, "成功", "设置已保存")

    def _reset_settings(self) -> None:
        """恢复默认设置"""
        if self.config and self.config_manager:
            # 直接创建全新的默认配置对象（避免缓存导致恢复无效）
            from config import Config

            default_config = Config()

            # 热键设置由HotkeySettingsWidget处理，更新config即可
            self.config.hide_hotkey = default_config.hide_hotkey
            self.config.show_hotkey = default_config.show_hotkey

            # 恢复其他设置
            self.auto_start_check.setChecked(default_config.auto_start)

            # 恢复检查间隔和误差阈值
            interval_index = self.interval_combo.findText(str(default_config.ntp_check_interval))
            if interval_index >= 0:
                self.interval_combo.setCurrentIndex(interval_index)
            else:
                self.interval_combo.setCurrentIndex(1)  # 默认 60 秒

            self.threshold_spin.setValue(default_config.ntp_error_threshold)

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
                    if getattr(sys, "frozen", False):
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
            # 停止自动刷新定时器
            if hasattr(self, "_auto_refresh_timer") and self._auto_refresh_timer:
                self._auto_refresh_timer.stop()
                logger.info("已停止黑白名单自动刷新")

            # 停止 NTP 同步线程
            if hasattr(self, "ntp_sync_thread") and self.ntp_sync_thread:
                try:
                    if self.ntp_sync_thread.isRunning():
                        self.ntp_sync_thread.wait(1000)  # 等待最多1秒
                except RuntimeError:
                    # 忽略对象已删除的错误
                    pass

            # 停止校准线程
            if hasattr(self, "calibration_thread") and self.calibration_thread:
                try:
                    if self.calibration_thread.isRunning():
                        self.calibration_thread.wait(1000)  # 等待最多1秒
                except RuntimeError:
                    # 忽略对象已删除的错误
                    pass
        except Exception:
            # 忽略所有清理错误
            pass

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
