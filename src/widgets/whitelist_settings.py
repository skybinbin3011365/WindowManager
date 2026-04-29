"""
白名单设置部件
PySide6版本
"""

import re
import logging
from typing import Optional, TYPE_CHECKING

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QGroupBox,
    QListWidget,
    QMessageBox,
)

if TYPE_CHECKING:
    from config import ConfigManager, Config

logger = logging.getLogger(__name__)


class WhitelistSettingsWidget(QWidget):
    """白名单设置部件"""

    def __init__(
        self,
        config_manager: Optional["ConfigManager"] = None,
        config: Optional["Config"] = None,
    ) -> None:
        """初始化白名单设置部件

        Args:
            config_manager: 配置管理器实例
            config: 配置对象
        """
        super().__init__()

        self.config_manager = config_manager
        self.config = config

        self._init_ui()
        self._load_whitelist()

    def _init_ui(self) -> None:
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # 进程白名单
        whitelist_group = QGroupBox("隐藏白名单进程")
        whitelist_layout = QVBoxLayout(whitelist_group)

        whitelist_info = QLabel("以下进程不会被隐藏（支持正则表达式）：")
        whitelist_info.setWordWrap(True)
        whitelist_layout.addWidget(whitelist_info)

        # 白名单输入
        whitelist_input_layout = QHBoxLayout()
        self.whitelist_edit = QLineEdit()
        self.whitelist_edit.setPlaceholderText("输入进程名或正则表达式，例如：notepad")
        whitelist_input_layout.addWidget(self.whitelist_edit)

        self.add_whitelist_btn = QPushButton("添加")
        self.add_whitelist_btn.clicked.connect(self._add_whitelist)
        whitelist_input_layout.addWidget(self.add_whitelist_btn)

        whitelist_layout.addLayout(whitelist_input_layout)

        # 白名单列表
        self.whitelist_list = QListWidget()
        self.whitelist_list.setSelectionMode(
            QListWidget.SelectionMode.MultiSelection)
        whitelist_layout.addWidget(self.whitelist_list)

        # 白名单操作按钮
        whitelist_btn_layout = QHBoxLayout()

        self.remove_whitelist_btn = QPushButton("删除选中")
        self.remove_whitelist_btn.clicked.connect(
            self._remove_selected_whitelist)
        whitelist_btn_layout.addWidget(self.remove_whitelist_btn)

        self.remove_all_whitelist_btn = QPushButton("清空")
        self.remove_all_whitelist_btn.clicked.connect(
            self._remove_all_whitelist)
        whitelist_btn_layout.addWidget(self.remove_all_whitelist_btn)

        whitelist_btn_layout.addStretch()
        whitelist_layout.addLayout(whitelist_btn_layout)

        layout.addWidget(whitelist_group)

    def _validate_process_name(self, process: str) -> bool:
        """验证进程名或正则表达式

        Args:
            process: 进程名或正则表达式

        Returns:
            bool: 是否有效
        """
        if not process or not process.strip():
            return False

        try:
            re.compile(process)
            return True
        except re.error:
            return False

    def _add_whitelist(self) -> None:
        """添加白名单"""
        if not self.config:
            return

        process = self.whitelist_edit.text().strip()
        if not process:
            QMessageBox.warning(self, "警告", "请输入进程名")
            return

        if not self._validate_process_name(process):
            QMessageBox.warning(self, "警告", "无效的正则表达式")
            return

        if process in self.config.process_whitelist:
            QMessageBox.warning(self, "警告", "该进程已在白名单中")
            return

        self.config.process_whitelist.append(process)
        self.whitelist_list.addItem(process)
        self.whitelist_edit.clear()
        logger.info("已添加到白名单: %s", process)

    def _remove_selected_whitelist(self) -> None:
        """删除选中的白名单项"""
        if not self.config:
            return

        for item in self.whitelist_list.selectedItems():
            process = item.text()
            if process in self.config.process_whitelist:
                self.config.process_whitelist.remove(process)
            row = self.whitelist_list.row(item)
            self.whitelist_list.takeItem(row)
            logger.info("已从白名单移除: %s", process)

    def _remove_all_whitelist(self) -> None:
        """删除所有白名单项"""
        if not self.config:
            return

        self.config.process_whitelist = []
        self.whitelist_list.clear()
        logger.info("已清空所有白名单")

    def _load_whitelist(self) -> None:
        """加载白名单"""
        if self.config:
            if hasattr(self, "whitelist_list"):
                self.whitelist_list.clear()
                for process in self.config.process_whitelist:
                    self.whitelist_list.addItem(process)

    def save_settings(self) -> None:
        """保存白名单设置"""
        if self.config_manager and self.config:
            self.config_manager.save(self.config)

    def get_whitelist(self) -> list:
        """获取白名单列表

        Returns:
            list: 白名单进程列表
        """
        if self.config:
            return self.config.process_whitelist
        return []
