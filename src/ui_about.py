# -*- coding: utf-8 -*-
# windowmanager/ui_about.py
"""
窗口管理器 - 关于模块 (PySide6版本)
显示程序信息和版权声明，以及日志窗口
"""

import os
import logging
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QTextEdit,
    QPushButton,
    QSplitter,
    QCheckBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap

from constants import AppConstants, PathConstants
from utils import get_resource_path
from theme import theme

if TYPE_CHECKING:
    from config import Config

logger = logging.getLogger(__name__)


class AboutTab(QWidget):
    """关于选项卡 - PySide6版本 - 左右两栏布局"""

    # 定义日志更新信号
    log_updated = Signal(str)

    def __init__(self, config: "Config" = None) -> None:
        """初始化关于选项卡

        Args:
            config: 配置对象，用于初始化日志开关状态
        """
        super().__init__()
        self._config = config
        self._init_ui()
        # 从配置加载日志开关初始状态
        if config is not None:
            self._load_log_options(config)
        # 连接日志更新信号
        self.log_updated.connect(self._append_log_safe)

    def _init_ui(self) -> None:
        """初始化UI组件 - 左右两栏布局，带可调整分隔器"""
        self.setStyleSheet(theme.get_global_stylesheet())

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._create_left_panel())
        splitter.addWidget(self._create_right_panel())
        splitter.setSizes([500, 500])

        main_layout.addWidget(splitter)

    def _create_left_panel(self) -> QWidget:
        """创建左栏面板（程序信息、功能特性、版权信息）"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        layout.addWidget(self._create_info_group())
        layout.addWidget(self._create_features_group())
        layout.addWidget(self._create_copyright_group())
        layout.addStretch()

        return widget

    def _create_info_group(self) -> QGroupBox:
        """创建程序信息分组（图标、标题、版本、描述）"""
        group = QGroupBox("程序信息")
        layout = QVBoxLayout(group)

        header_layout = QHBoxLayout()
        header_layout.addWidget(self._create_icon_label())

        title_layout = QVBoxLayout()
        title_layout.addWidget(QLabel(AppConstants.APP_TITLE))
        title_layout.addWidget(QLabel(f"版本: {AppConstants.APP_VERSION}"))
        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        desc_label = QLabel(
            "一个轻量级的 Windows 窗口管理工具，\n"
            "支持快速隐藏/显示窗口、全局热键操作、\n"
            "关键字自动选择等功能。"
        )
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        return group

    def _create_icon_label(self) -> QLabel:
        """创建图标标签，自动尝试加载候选图标"""
        icon_label = QLabel()
        icon_candidates = [get_resource_path(icon) for icon in PathConstants.ICON_CANDIDATES]

        for icon_path in icon_candidates:
            if icon_path and os.path.exists(icon_path):
                pixmap = QPixmap(icon_path)
                if pixmap.isNull():
                    continue
                scaled_pixmap = pixmap.scaled(
                    128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation,
                )
                icon_label.setFixedSize(128, 128)
                icon_label.setPixmap(scaled_pixmap)
                icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                return icon_label

        icon_label.setText("🖥️")
        icon_label.setStyleSheet(f"font-size: 64px; color: {theme.PRIMARY};")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setFixedSize(128, 128)
        return icon_label

    def _create_features_group(self) -> QGroupBox:
        """创建功能特性分组"""
        group = QGroupBox("功能特性")
        layout = QVBoxLayout(group)

        features_text = QTextEdit()
        features_text.setReadOnly(True)
        features_text.setMaximumHeight(150)
        features_text.setPlainText(
            "• 窗口列表管理 - 实时显示所有可见窗口\n"
            "• 快速隐藏/显示 - 一键隐藏或恢复窗口\n"
            "• 全局热键 - 自定义热键快速操作\n"
            "• 关键字自动选择 - 自动选中匹配窗口\n"
            "• 进程白名单 - 过滤不需要管理的窗口\n"
            "• 系统托盘 - 最小化到托盘，后台运行\n"
            "• 开机自启动 - 可选开机自动启动"
        )
        layout.addWidget(features_text)

        return group

    def _create_copyright_group(self) -> QGroupBox:
        """创建版权信息分组"""
        group = QGroupBox("版权信息")
        layout = QVBoxLayout(group)

        copyright_label = QLabel(
            "© 2024 WinHide 开发团队\n\n"
            "本软件为开源软件，遵循 MIT 许可证。\n"
            "如有问题或建议，欢迎反馈。"
        )
        copyright_label.setWordWrap(True)
        layout.addWidget(copyright_label)

        return group

    def _create_right_panel(self) -> QWidget:
        """创建右栏面板（日志窗口）"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        layout.addWidget(self._create_log_group())

        return widget

    def _create_log_group(self) -> QGroupBox:
        """创建日志窗口分组（日志文本框、选项复选框、操作按钮）"""
        group = QGroupBox("日志窗口")
        layout = QVBoxLayout(group)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

        layout.addLayout(self._create_log_options_layout())
        layout.addLayout(self._create_log_buttons_layout())

        return group

    def _create_log_options_layout(self) -> QHBoxLayout:
        """创建日志选项复选框布局"""
        layout = QHBoxLayout()

        self.window_refresh_log_check = QCheckBox("窗口刷新日志")
        self.window_refresh_log_check.setChecked(True)
        layout.addWidget(self.window_refresh_log_check)

        self.window_operation_log_check = QCheckBox("记录窗口操作日志")
        self.window_operation_log_check.setChecked(True)
        layout.addWidget(self.window_operation_log_check)

        self.ntp_log_check = QCheckBox("校时日志")
        self.ntp_log_check.setChecked(True)
        layout.addWidget(self.ntp_log_check)

        self.debug_log_check = QCheckBox("显示 DEBUG 日志")
        self.debug_log_check.setChecked(False)
        self.debug_log_check.setToolTip("勾选后日志面板将显示 DEBUG 级别的详细调试信息")
        layout.addWidget(self.debug_log_check)

        layout.addStretch()
        return layout

    def _create_log_buttons_layout(self) -> QHBoxLayout:
        """创建日志操作按钮布局"""
        layout = QHBoxLayout()

        clear_log_btn = QPushButton("清空日志")
        clear_log_btn.clicked.connect(self._clear_log)
        layout.addWidget(clear_log_btn)

        refresh_log_btn = QPushButton("刷新日志")
        refresh_log_btn.clicked.connect(self._refresh_log)
        layout.addWidget(refresh_log_btn)

        return layout

    def _clear_log(self) -> None:
        """清空日志"""
        self.log_text.clear()

    def _refresh_log(self) -> None:
        """刷新日志"""
        self.log_text.clear()
        self.log_text.append("日志已刷新")

    def _load_log_options(self, config: "Config") -> None:
        """从配置中加载日志开关状态

        Args:
            config: 配置对象
        """
        self.window_refresh_log_check.setChecked(
            getattr(config.log, "enable_window_refresh_log", True))
        self.window_operation_log_check.setChecked(
            getattr(config.log, "enable_window_operation_log", True)
        )
        self.ntp_log_check.setChecked(getattr(config.ntp, "enable_ntp_log", True))
        self.debug_log_check.setChecked(
            getattr(config.log, "enable_debug_log", False))

    def append_log(self, message: str) -> None:
        """添加日志消息（从日志处理器调用）

        Args:
            message: 要添加的日志消息
        """
        # 通过信号在主线程更新UI
        self.log_updated.emit(message)

    def _append_log_safe(self, message: str) -> None:
        """安全添加日志消息（在主线程中执行）

        Args:
            message: 要添加的日志消息
        """
        self.log_text.append(message)

    def get_window_refresh_log_enabled(self) -> bool:
        """获取窗口刷新日志是否启用

        Returns:
            bool: 窗口刷新日志是否启用
        """
        return self.window_refresh_log_check.isChecked()

    def get_ntp_log_enabled(self) -> bool:
        """获取NTP日志是否启用

        Returns:
            bool: NTP日志是否启用
        """
        return self.ntp_log_check.isChecked()

    def get_window_operation_log_enabled(self) -> bool:
        """获取窗口操作日志是否启用

        Returns:
            bool: 窗口操作日志是否启用
        """
        return self.window_operation_log_check.isChecked()

    def get_debug_log_enabled(self) -> bool:
        """获取 DEBUG 日志面板显示是否启用

        Returns:
            bool: DEBUG 日志是否在面板中显示
        """
        return self.debug_log_check.isChecked()

    def apply_log_options_to_config(self, config) -> None:
        """将日志开关状态写入配置对象（解耦接口）

        供 SettingsTab 保存配置时调用，避免跨选项卡直接访问 UI 控件。

        Args:
            config: Config 配置对象
        """
        config.log.enable_window_refresh_log = self.window_refresh_log_check.isChecked()
        config.log.enable_window_operation_log = self.window_operation_log_check.isChecked()
        config.ntp.enable_ntp_log = self.ntp_log_check.isChecked()
        config.log.enable_debug_log = self.debug_log_check.isChecked()
