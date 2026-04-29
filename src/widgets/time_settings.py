"""
时间设置部件
PySide6版本
"""

import logging
import threading
from datetime import datetime
from typing import Optional

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QCheckBox,
    QMessageBox,
)
from PySide6.QtCore import Signal, QTimer
from PySide6.QtGui import QFont


from time_sync import TimeSyncTool, SyncResult, SystemTimeSetter

logger = logging.getLogger(__name__)


class TimeSettingsWidget(QWidget):
    """时间设置部件"""

    # 定义 NTP 结果信号
    ntp_result_ready = Signal(object)  # SyncResult
    # NTP 所有服务器响应时间就绪（供父窗口 SettingsTab 更新其 ntp_servers_table）
    ntp_response_times_ready = Signal(dict)  # Dict[str, float]
    # 校准结果信号（用于跨线程安全更新UI）
    calibration_result_ready = Signal(bool)  # bool: success

    def __init__(self, parent_window: Optional[QWidget] = None) -> None:
        """初始化时间设置部件

        Args:
            parent_window: 父窗口
        """
        super().__init__()

        self.parent_window = parent_window

        # 初始化时间同步工具
        # 暂时使用默认服务器，稍后会从配置文件加载
        self.time_sync_tool = TimeSyncTool()

    def set_ntp_servers(self, ntp_servers):
        """设置NTP服务器列表

        Args:
            ntp_servers: NTP服务器列表
        """
        self.time_sync_tool.ntp_servers = ntp_servers
        self._ntp_time = None

        # 记录获取 NTP 时间时的本地时间偏移，用于模拟时间增长
        self._ntp_base_time = None  # 获取 NTP 时间时的本地时间
        self._ntp_synced_time = None  # 获取到的 NTP 时间

        # 自动校准相关
        self.auto_calibration_enabled = False
        self.auto_calibration_timer = QTimer()

        self._init_ui()

        # 更新时间显示
        self._update_current_time()
        self._time_timer = QTimer()
        self._time_timer.timeout.connect(self._update_current_time)
        self._time_timer.start(1000)  # 每秒更新一次

        # 连接 NTP 结果信号
        self.ntp_result_ready.connect(self._on_ntp_result)

        # 连接校准结果信号（用于跨线程安全更新UI）
        self.calibration_result_ready.connect(self._on_calibrate_result)

        # 延迟自动获取 NTP 时间（等待 UI 完全初始化）
        QTimer.singleShot(1500, self._on_get_ntp_clicked)

        # 初始化自动校准
        self._init_auto_calibration()

    def _init_auto_calibration(self) -> None:
        """初始化自动校准功能"""
        # 连接自动校准定时器
        self.auto_calibration_timer.timeout.connect(self._auto_calibrate)
        # 启动自动校准，60秒间隔
        self.auto_calibration_enabled = True
        self.auto_calibration_timer.start(60000)
        logger.info("已启动自动时间校准，间隔60秒")

    def _init_ui(self) -> None:
        """初始化 UI 组件"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # 时间校准
        time_group = QGroupBox("时间校准")
        time_layout = QVBoxLayout(time_group)

        # 初始化时间显示布局
        time_display_layout = self._init_time_display_layout()
        time_layout.addLayout(time_display_layout)

        # 初始化 NTP 操作按钮布局
        ntp_btn_layout = self._init_ntp_buttons_layout()
        time_layout.addLayout(ntp_btn_layout)

        # 初始化 NTP 选项
        self._init_ntp_options(time_layout)

        layout.addWidget(time_group)

    def _init_time_display_layout(self) -> QVBoxLayout:
        """初始化时间显示布局（上下排列）"""
        time_display_layout = QVBoxLayout()
        time_display_layout.setSpacing(8)

        # 本地时间
        local_time_row = QHBoxLayout()
        local_time_title = QLabel("本地时间:")
        local_time_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        local_time_title.setMinimumWidth(100)
        local_time_row.addWidget(local_time_title)

        self.local_time_label = QLabel()
        self.local_time_label.setFont(QFont("Consolas", 12))
        local_time_row.addWidget(self.local_time_label)
        local_time_row.addStretch()
        time_display_layout.addLayout(local_time_row)

        # NTP 时间
        ntp_time_row = QHBoxLayout()
        ntp_time_title = QLabel("NTP 时间:")
        ntp_time_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        ntp_time_title.setMinimumWidth(100)
        ntp_time_row.addWidget(ntp_time_title)

        self.ntp_time_label = QLabel("未获取")
        self.ntp_time_label.setFont(QFont("Consolas", 12))
        ntp_time_row.addWidget(self.ntp_time_label)
        ntp_time_row.addStretch()
        time_display_layout.addLayout(ntp_time_row)

        # 时间差
        time_diff_row = QHBoxLayout()
        time_diff_title = QLabel("时间差:")
        time_diff_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        time_diff_title.setMinimumWidth(100)
        time_diff_row.addWidget(time_diff_title)

        self.diff_label = QLabel("N/A")
        self.diff_label.setFont(QFont("Consolas", 10))
        time_diff_row.addWidget(self.diff_label)
        time_diff_row.addStretch()
        time_display_layout.addLayout(time_diff_row)

        return time_display_layout

    def _init_ntp_buttons_layout(self) -> QHBoxLayout:
        """初始化 NTP 操作按钮布局"""
        ntp_btn_layout = QHBoxLayout()

        self.get_ntp_btn = QPushButton("获取 NTP 时间")
        self.get_ntp_btn.clicked.connect(self._on_get_ntp_clicked)
        ntp_btn_layout.addWidget(self.get_ntp_btn)

        self.calibrate_btn = QPushButton("立即校准")
        self.calibrate_btn.clicked.connect(self._on_calibrate_clicked)
        ntp_btn_layout.addWidget(self.calibrate_btn)

        ntp_btn_layout.addStretch()

        return ntp_btn_layout

    def _init_ntp_options(self, layout: QVBoxLayout) -> None:
        """初始化 NTP 选项"""
        # NTP 日志选项
        self.enable_ntp_log_check = QCheckBox("记录 NTP 同步日志")
        self.enable_ntp_log_check.setChecked(True)
        layout.addWidget(self.enable_ntp_log_check)

    def _save_config(self) -> None:
        """保存配置（占位符）"""
        pass

    def _update_current_time(self) -> None:
        """更新当前时间显示"""
        now = datetime.now()
        time_str = now.strftime("%Y-%m-%d %H:%M:%S")
        self.local_time_label.setText(time_str)

        # 如果已经获取过 NTP 时间，模拟时间增长并更新显示
        if self._ntp_synced_time is not None and self._ntp_base_time is not None:
            # 计算从获取 NTP 时间到现在的经过时间
            elapsed = now - self._ntp_base_time
            # 模拟 NTP 时间增长
            simulated_ntp_time = self._ntp_synced_time + elapsed
            ntp_time_str = simulated_ntp_time.strftime("%Y-%m-%d %H:%M:%S")
            self.ntp_time_label.setText(ntp_time_str)

            # 计算当前时间差（毫秒）
            current_diff = (simulated_ntp_time - now).total_seconds() * 1000
            self.diff_label.setText(f"{current_diff:.0f} 毫秒")

            # 根据时间差绝对值设置颜色
            if abs(current_diff) > 5000:
                self.diff_label.setStyleSheet(
                    "color: #F44336; font-weight: bold;")
            else:
                self.diff_label.setStyleSheet(
                    "color: #4CAF50; font-weight: bold;")

    def _on_get_ntp_clicked(self) -> None:
        """获取 NTP 时间按钮点击"""
        self.get_ntp_btn.setEnabled(False)
        self._ntp_time = None

        # 更新界面状态，显示正在获取
        self.ntp_time_label.setText("正在获取...")
        self.ntp_time_label.setStyleSheet("color: #2196F3; font-weight: bold;")
        self.diff_label.setText("计算中...")
        self.diff_label.setStyleSheet("color: #2196F3; font-weight: bold;")

        # 在后台线程中执行 NTP 同步，添加超时处理
        def on_complete():
            try:
                # 使用超时机制，避免网络问题导致无限等待
                import socket

                socket.setdefaulttimeout(10)  # 10秒超时
                result, response_times = self.time_sync_tool.sync_time_blocking()
            except socket.timeout:
                logger.error("获取 NTP 时间超时")
                result = SyncResult(success=False, message="获取 NTP 时间超时（10秒）")
                response_times = {}
            except Exception as e:
                logger.error("获取 NTP 时间异常：%s", str(e))
                result = SyncResult(success=False, message=str(e))
                response_times = {}
            self.ntp_result_ready.emit(result)
            self.ntp_response_times_ready.emit(response_times)

        threading.Thread(target=on_complete, daemon=True).start()

    def _on_ntp_result(self, result: SyncResult) -> None:
        """NTP 获取结果处理"""
        self.get_ntp_btn.setEnabled(True)

        if result.success:
            ntp_time_str = result.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            self.ntp_time_label.setText(ntp_time_str)
            self._ntp_time = result.timestamp

            # 保存获取 NTP 时间时的基准信息，用于模拟时间增长
            self._ntp_base_time = datetime.now()
            self._ntp_synced_time = result.timestamp

            # 计算并显示时间差（毫秒）
            time_diff_ms = result.offset_ms
            self.diff_label.setText(f"{time_diff_ms:.0f} 毫秒")

            # 根据时间差绝对值设置颜色
            if abs(time_diff_ms) > 5000:
                self.diff_label.setStyleSheet(
                    "color: #F44336; font-weight: bold;")
            else:
                self.diff_label.setStyleSheet(
                    "color: #4CAF50; font-weight: bold;")

            # 恢复NTP时间标签的默认颜色
            self.ntp_time_label.setStyleSheet(
                "color: #4CAF50; font-weight: bold;")

            if self.enable_ntp_log_check.isChecked():
                logger.info(
                    "NTP 时间获取成功：%s，时间差：%.2f 毫秒",
                    ntp_time_str,
                    time_diff_ms,
                )
        else:
            self.ntp_time_label.setText(f"获取失败: {result.message}")
            self.ntp_time_label.setStyleSheet(
                "color: #F44336; font-weight: bold;")
            self.diff_label.setText("N/A")
            logger.warning("NTP 时间获取失败：%s", result.message)

    def _on_calibrate_clicked(self) -> None:
        """立即校准按钮点击"""
        if not self._ntp_time:
            QMessageBox.warning(self, "警告", "请先获取 NTP 时间")
            return

        logger.info("正在校准系统时间...")
        self.calibrate_btn.setEnabled(False)

        def do_calibrate():
            try:
                # 计算时间偏移量（毫秒）：(NTP时间 - 本地时间) * 1000
                local_time = datetime.now()
                time_diff = self._ntp_time - local_time
                offset_ms = time_diff.total_seconds() * 1000
                success = SystemTimeSetter.set_system_time(offset_ms)
                if success:
                    logger.info("系统时间校准成功")
                else:
                    logger.warning("系统时间校准失败")

                # 使用信号安全地更新UI（跨线程通信）
                self.calibration_result_ready.emit(success)
            except Exception as e:
                logger.error("校准时发生异常：%s", str(e))
                self.calibration_result_ready.emit(False)

        threading.Thread(target=do_calibrate, daemon=True).start()

    def _update_ntp_base_after_calibration(self) -> None:
        """校准成功后更新NTP时间基准"""
        if self._ntp_time:
            # 校准成功后，将当前系统时间作为新的基准时间
            # 这样模拟的NTP时间就会与系统时间同步
            self._ntp_base_time = datetime.now()
            self._ntp_synced_time = self._ntp_time
            logger.info("NTP时间基准已更新，模拟时间与系统时间同步")

    def _on_calibrate_result(self, success: bool) -> None:
        """校准结果处理"""
        self.calibrate_btn.setEnabled(True)

        if success:
            # 校准成功后，更新NTP时间基准，使模拟时间与系统时间同步
            self._update_ntp_base_after_calibration()
            QMessageBox.information(self, "成功", "系统时间校准成功！")
        else:
            QMessageBox.warning(self, "失败", "系统时间校准失败，请检查权限设置")

    def _auto_calibrate(self) -> None:
        """自动校准时间"""
        if not self.auto_calibration_enabled:
            return

        logger.info("执行自动时间校准...")

        # 先获取最新的 NTP 时间
        def on_auto_complete():
            try:
                # 使用超时机制，避免网络问题导致无限等待
                import socket

                socket.setdefaulttimeout(10)  # 10秒超时
                result, response_times = self.time_sync_tool.sync_time_blocking()
            except socket.timeout:
                logger.error("自动校准：获取 NTP 时间超时")
                return
            except Exception as e:
                logger.error("自动校准：获取 NTP 时间异常：%s", str(e))
                return

            if result.success:
                logger.info("自动校准：NTP 时间获取成功，准备校准系统时间")
                # 保存获取 NTP 时间时的基准信息，用于模拟时间增长
                self._ntp_base_time = datetime.now()
                self._ntp_synced_time = result.timestamp
                self._ntp_time = result.timestamp

                # 执行校准
                try:
                    # 计算时间偏移量（毫秒）：(NTP时间 - 本地时间) * 1000
                    local_time = datetime.now()
                    time_diff = result.timestamp - local_time
                    offset_ms = time_diff.total_seconds() * 1000
                    success = SystemTimeSetter.set_system_time(offset_ms)
                    if success:
                        logger.info("自动校准：系统时间校准成功")
                    else:
                        logger.warning("自动校准：系统时间校准失败")
                except Exception as e:
                    logger.error("自动校准：校准时发生异常：%s", str(e))
            else:
                logger.warning("自动校准：NTP 时间获取失败：%s", result.message)

        threading.Thread(target=on_auto_complete, daemon=True).start()

    def cleanup(self) -> None:
        """清理资源"""
        if hasattr(self, "_time_timer"):
            self._time_timer.stop()

        # 停止自动校准定时器
        if hasattr(self, "auto_calibration_timer"):
            self.auto_calibration_timer.stop()
            logger.info("已停止自动时间校准")
