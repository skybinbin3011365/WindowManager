"""
热键设置部件
PySide6版本
"""

import logging
from typing import Optional, TYPE_CHECKING

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
)
from PySide6.QtCore import Signal

if TYPE_CHECKING:
    from config import ConfigManager, Config

import hotkey_manager

from utils import HotkeyFormatter

logger = logging.getLogger(__name__)


class HotkeySettingsWidget(QWidget):
    """热键设置部件"""

    # 定义信号 - 热键更改时通知
    hotkeys_changed = Signal()

    # 定义录制完成信号
    hide_recording_finished = Signal(str)
    show_recording_finished = Signal(str)

    def __init__(
        self,
        config_manager: Optional["ConfigManager"] = None,
        config: Optional["Config"] = None,
        hotkey_manager: Optional["hotkey_manager.HotkeyManager"] = None,
        parent_window: Optional[QWidget] = None,
    ) -> None:
        """初始化热键设置部件

        Args:
            config_manager: 配置管理器实例
            config: 配置对象
            hotkey_manager: 热键管理器实例
            parent_window: 父窗口
        """
        super().__init__()

        self.config_manager = config_manager
        self.config = config
        self.hotkey_manager = hotkey_manager
        self.parent_window = parent_window

        self._init_ui()
        self._load_hotkeys()

        # 连接录制完成信号
        self.hide_recording_finished.connect(self._on_hide_recording_finished)
        self.show_recording_finished.connect(self._on_show_recording_finished)

    def _init_ui(self) -> None:
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # 隐藏热键
        hide_hotkey_layout = QHBoxLayout()
        hide_hotkey_layout.addWidget(QLabel("隐藏窗口热键:"))
        self.hide_hotkey_edit = QLineEdit()
        self.hide_hotkey_edit.setReadOnly(True)
        hide_hotkey_layout.addWidget(self.hide_hotkey_edit)

        self.hide_record_btn = QPushButton("录制")
        self.hide_record_btn.clicked.connect(self._record_hide_hotkey)
        hide_hotkey_layout.addWidget(self.hide_record_btn)

        layout.addLayout(hide_hotkey_layout)

        # 显示热键
        show_hotkey_layout = QHBoxLayout()
        show_hotkey_layout.addWidget(QLabel("显示窗口热键:"))
        self.show_hotkey_edit = QLineEdit()
        self.show_hotkey_edit.setReadOnly(True)
        show_hotkey_layout.addWidget(self.show_hotkey_edit)

        self.show_record_btn = QPushButton("录制")
        self.show_record_btn.clicked.connect(self._record_show_hotkey)
        show_hotkey_layout.addWidget(self.show_record_btn)

        layout.addLayout(show_hotkey_layout)

    def _format_hotkey_for_display(self, hotkey: str) -> str:
        """格式化热键用于显示"""
        return HotkeyFormatter.format_hotkey(hotkey)

    def _load_hotkeys(self) -> None:
        """加载热键设置"""
        if self.config:
            self.hide_hotkey_edit.setText(
                self._format_hotkey_for_display(self.config.hide_hotkey))
            self.show_hotkey_edit.setText(
                self._format_hotkey_for_display(self.config.show_hotkey))

    def _record_hotkey(
        self, button: QPushButton, line_edit: QLineEdit, finish_signal: Signal
    ) -> None:
        """录制热键

        Args:
            button: 录制按钮
            line_edit: 热键显示编辑框
            finish_signal: 录制完成信号
        """
        if not self.hotkey_manager:
            logger.warning("热键管理器不可用，无法录制热键")
            return

        button.setEnabled(False)
        button.setText("录制中...")

        def recording_callback(hotkey_str: Optional[str]) -> None:
            if hotkey_str:
                finish_signal.emit(hotkey_str)
            # 无论是否录到按键，都恢复按钮状态
            button.setEnabled(True)
            button.setText("录制")

        def realtime_callback(hotkey_str: str) -> None:
            line_edit.setText(hotkey_str)

        # 只有当成功开始录制时，才设置回调
        if not self.hotkey_manager.start_recording(recording_callback, realtime_callback):
            # 如果已经在录制中，立即恢复按钮状态
            button.setEnabled(True)
            button.setText("录制")

    def _record_hide_hotkey(self) -> None:
        """录制隐藏热键"""
        self._record_hotkey(
            self.hide_record_btn, self.hide_hotkey_edit, self.hide_recording_finished
        )

    def _on_hide_recording_finished(self, hotkey_str: str) -> None:
        """隐藏热键录制完成"""
        if not self.config:
            return

        self.hide_hotkey_edit.setText(
            self._format_hotkey_for_display(hotkey_str))
        self.config.hide_hotkey = hotkey_str

        if self.hotkey_manager:
            try:
                self.hotkey_manager.unregister_hide_hotkey()
                # 发出热键更改信号，让主窗口更新热键回调
                self.hotkeys_changed.emit()
            except Exception as e:
                logger.error("更新隐藏热键失败: %s", str(e))

        self.hotkeys_changed.emit()

    def _record_show_hotkey(self) -> None:
        """录制显示热键"""
        self._record_hotkey(
            self.show_record_btn, self.show_hotkey_edit, self.show_recording_finished
        )

    def _on_show_recording_finished(self, hotkey_str: str) -> None:
        """显示热键录制完成"""
        if not self.config:
            return

        self.show_hotkey_edit.setText(
            self._format_hotkey_for_display(hotkey_str))
        self.config.show_hotkey = hotkey_str

        if self.hotkey_manager:
            try:
                self.hotkey_manager.unregister_show_hotkey()
                # 发出热键更改信号，让主窗口更新热键回调
                self.hotkeys_changed.emit()
            except Exception as e:
                logger.error("更新显示热键失败: %s", str(e))

        self.hotkeys_changed.emit()

    def save_settings(self) -> None:
        """保存热键设置"""
        pass  # 热键设置在录制时已保存
