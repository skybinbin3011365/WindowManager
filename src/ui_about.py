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
        # 设置现代化样式
        self.setStyleSheet(theme.get_global_stylesheet())

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # 创建水平分隔器
        splitter = QSplitter(Qt.Horizontal)

        # ========== 左栏：关于内容 ==========
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        # 程序信息
        info_group = QGroupBox("程序信息")
        info_layout = QVBoxLayout(info_group)

        # 图标和标题
        header_layout = QHBoxLayout()

        # 尝试加载图标 - 优先使用PNG格式
        icon_label = QLabel()
        icon_candidates = [get_resource_path(
            icon) for icon in PathConstants.ICON_CANDIDATES]

        icon_loaded = False
        for icon_path in icon_candidates:
            if icon_path and os.path.exists(icon_path):
                pixmap = QPixmap(icon_path)
                if pixmap.isNull():  # 修复逻辑：图片为空时跳过
                    continue
                # 使用更高质量的缩放方法
                scaled_pixmap = pixmap.scaled(
                    128,
                    128,  # 使用更大的尺寸以提高清晰度
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
                # 设置固定大小以确保显示清晰
                icon_label.setFixedSize(128, 128)
                icon_label.setPixmap(scaled_pixmap)
                icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                icon_loaded = True
                break

        if not icon_loaded:
            # 如果没有图标，显示占位符
            icon_label.setText("🖥️")
            icon_label.setStyleSheet(
                "font-size: 64px; color: %s;" % theme.PRIMARY)
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_label.setFixedSize(128, 128)

        header_layout.addWidget(icon_label)

        title_layout = QVBoxLayout()
        title_label = QLabel(AppConstants.APP_TITLE)
        title_layout.addWidget(title_label)

        version_label = QLabel(f"版本: {AppConstants.APP_VERSION}")
        title_layout.addWidget(version_label)

        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        info_layout.addLayout(header_layout)

        # 描述
        desc_label = QLabel(
            "一个轻量级的 Windows 窗口管理工具，\n"
            "支持快速隐藏/显示窗口、全局热键操作、\n"
            "关键字自动选择等功能。"
        )
        desc_label.setWordWrap(True)
        info_layout.addWidget(desc_label)

        left_layout.addWidget(info_group)

        # 功能特性
        features_group = QGroupBox("功能特性")
        features_layout = QVBoxLayout(features_group)

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
        features_layout.addWidget(features_text)

        left_layout.addWidget(features_group)

        # 版权信息
        copyright_group = QGroupBox("版权信息")
        copyright_layout = QVBoxLayout(copyright_group)

        copyright_label = QLabel(
            "© 2024 WinHide 开发团队\n\n"
            "本软件为开源软件，遵循 MIT 许可证。\n"
            "如有问题或建议，欢迎反馈。"
        )
        copyright_label.setWordWrap(True)
        copyright_layout.addWidget(copyright_label)

        left_layout.addWidget(copyright_group)

        left_layout.addStretch()

        # 添加左栏到分隔器
        splitter.addWidget(left_widget)

        # ========== 右栏：日志窗口 ==========
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(5)

        log_group = QGroupBox("日志窗口")
        log_layout = QVBoxLayout(log_group)

        # 日志文本框
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)

        # 日志选项
        log_options_layout = QHBoxLayout()

        # 窗口刷新日志选项
        self.window_refresh_log_check = QCheckBox("窗口刷新日志")
        self.window_refresh_log_check.setChecked(
            True)  # 默认值，将被 _load_log_options 覆盖
        log_options_layout.addWidget(self.window_refresh_log_check)

        # 窗口操作日志选项
        self.window_operation_log_check = QCheckBox("记录窗口操作日志")
        self.window_operation_log_check.setChecked(
            True)  # 默认值，将被 _load_log_options 覆盖
        log_options_layout.addWidget(self.window_operation_log_check)

        # 校时日志选项
        self.ntp_log_check = QCheckBox("校时日志")
        self.ntp_log_check.setChecked(True)  # 默认值，将被 _load_log_options 覆盖
        log_options_layout.addWidget(self.ntp_log_check)

        # DEBUG 日志选项
        self.debug_log_check = QCheckBox("显示 DEBUG 日志")
        self.debug_log_check.setChecked(False)  # 默认关闭，将被 _load_log_options 覆盖
        self.debug_log_check.setToolTip("勾选后日志面板将显示 DEBUG 级别的详细调试信息")
        log_options_layout.addWidget(self.debug_log_check)

        log_options_layout.addStretch()
        log_layout.addLayout(log_options_layout)

        # 日志操作按钮
        log_btn_layout = QHBoxLayout()
        clear_log_btn = QPushButton("清空日志")
        clear_log_btn.clicked.connect(self._clear_log)
        log_btn_layout.addWidget(clear_log_btn)

        refresh_log_btn = QPushButton("刷新日志")
        refresh_log_btn.clicked.connect(self._refresh_log)
        log_btn_layout.addWidget(refresh_log_btn)

        log_layout.addLayout(log_btn_layout)

        right_layout.addWidget(log_group)

        # 添加右栏到分隔器
        splitter.addWidget(right_widget)

        # 设置分隔器初始比例
        splitter.setSizes([500, 500])

        # 添加分隔器到主布局
        main_layout.addWidget(splitter)

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
            getattr(config, "enable_window_refresh_log", True))
        self.window_operation_log_check.setChecked(
            getattr(config, "enable_window_operation_log", True)
        )
        self.ntp_log_check.setChecked(getattr(config, "enable_ntp_log", True))
        self.debug_log_check.setChecked(
            getattr(config, "enable_debug_log", False))

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
        config.enable_window_refresh_log = self.window_refresh_log_check.isChecked()
        config.enable_window_operation_log = self.window_operation_log_check.isChecked()
        config.enable_ntp_log = self.ntp_log_check.isChecked()
        config.enable_debug_log = self.debug_log_check.isChecked()
