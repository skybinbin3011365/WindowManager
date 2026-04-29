# windowmanager/ui_whitelist.py
"""
窗口管理器 - 黑白名单管理界面
"""

import logging
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QPushButton,
    QInputDialog,
    QMessageBox,
    QLabel,
    QGroupBox,
    QGridLayout,
)
from PySide6.QtCore import QTimer


from manager import WindowManager

logger = logging.getLogger(__name__)


class WhitelistTab(QWidget):
    """黑白名单管理选项卡"""

    def __init__(self, window_manager: WindowManager):
        """初始化黑白名单管理界面

        Args:
            window_manager: 窗口管理器实例
        """
        super().__init__()
        self.window_manager = window_manager
        self._setup_ui()

        # 添加自动刷新定时器，与窗口列表的刷新采用同一个定时器，默认 60 秒
        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._refresh_lists)
        self._refresh_timer.start(60000)  # 60 秒刷新一次

        # 启动后延迟 10 秒自动刷新一次
        QTimer.singleShot(10000, self._refresh_lists)

    def _refresh_lists(self):
        """刷新黑白名单列表"""
        # 清空现有列表
        self.blacklist_list.clear()
        self.whitelist_list.clear()

        # 重新填充列表
        blacklist = self.window_manager.get_blacklist()
        for process_name in blacklist:
            self.blacklist_list.addItem(process_name)

        whitelist = self.window_manager.get_whitelist()
        for process_name in whitelist:
            self.whitelist_list.addItem(process_name)

    def _setup_ui(self):
        """设置UI界面"""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # 使用网格布局创建布局
        grid_layout = QGridLayout()
        grid_layout.setSpacing(8)

        # 黑名单（左侧上方）
        blacklist_group = QGroupBox("黑名单（无窗口进程）")
        blacklist_layout = QVBoxLayout(blacklist_group)
        blacklist_layout.setContentsMargins(5, 5, 5, 5)
        blacklist_layout.setSpacing(5)

        self.blacklist_list = QListWidget()
        blacklist_layout.addWidget(self.blacklist_list)

        blacklist_buttons = QHBoxLayout()
        blacklist_buttons.setSpacing(5)
        self.add_blacklist_btn = QPushButton("添加")
        self.add_blacklist_btn.setFixedWidth(60)
        self.remove_blacklist_btn = QPushButton("删除")
        self.remove_blacklist_btn.setFixedWidth(60)
        blacklist_buttons.addWidget(self.add_blacklist_btn)
        blacklist_buttons.addWidget(self.remove_blacklist_btn)
        blacklist_buttons.addStretch()
        blacklist_layout.addLayout(blacklist_buttons)

        grid_layout.addWidget(blacklist_group, 0, 0)

        # 白名单（左侧下方）
        whitelist_group = QGroupBox("白名单（前台进程）")
        whitelist_layout = QVBoxLayout(whitelist_group)
        whitelist_layout.setContentsMargins(5, 5, 5, 5)
        whitelist_layout.setSpacing(5)

        self.whitelist_list = QListWidget()
        whitelist_layout.addWidget(self.whitelist_list)

        whitelist_buttons = QHBoxLayout()
        whitelist_buttons.setSpacing(5)
        self.add_whitelist_btn = QPushButton("添加")
        self.add_whitelist_btn.setFixedWidth(60)
        self.remove_whitelist_btn = QPushButton("删除")
        self.remove_whitelist_btn.setFixedWidth(60)
        whitelist_buttons.addWidget(self.add_whitelist_btn)
        whitelist_buttons.addWidget(self.remove_whitelist_btn)
        whitelist_buttons.addStretch()
        whitelist_layout.addLayout(whitelist_buttons)

        grid_layout.addWidget(whitelist_group, 1, 0)

        # 右侧留空（可以用于其他功能，如进程信息等）
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.addStretch()

        # 添加提示标签
        info_label = QLabel(
            "提示：\n\n1. 黑名单中的进程会被自动跳过\n2. 白名单中的进程会被视为前台应用\n3. 点击'添加'按钮手动添加进程\n4. 选择进程后点击'删除'按钮移除"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; font-size: 12px;")
        right_layout.addWidget(info_label)
        right_layout.addStretch()

        grid_layout.addWidget(right_widget, 0, 1, 2, 1)  # 占据右侧两个格子

        main_layout.addLayout(grid_layout)

        # 底部按钮
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        refresh_btn = QPushButton("刷新列表")
        refresh_btn.setFixedWidth(100)
        bottom_layout.addWidget(refresh_btn)
        main_layout.addLayout(bottom_layout)

        # 连接信号
        self.add_blacklist_btn.clicked.connect(self._add_blacklist)
        self.remove_blacklist_btn.clicked.connect(self._remove_blacklist)
        self.add_whitelist_btn.clicked.connect(self._add_whitelist)
        self.remove_whitelist_btn.clicked.connect(self._remove_whitelist)
        refresh_btn.clicked.connect(self._refresh_lists)

        self.setLayout(main_layout)

        # 初始加载列表
        self._refresh_lists()

        logger.info("已刷新黑白名单列表")

    def _add_blacklist(self):
        """添加进程到黑名单"""
        process_name, ok = QInputDialog.getText(
            self, "添加到黑名单", "请输入进程名（例如：chrome.exe）:"
        )
        if ok and process_name:
            if self.window_manager.add_to_blacklist(process_name):
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
            if self.window_manager.remove_from_blacklist(process_name):
                logger.info("已从黑名单移除进程: %s", process_name)

        self._refresh_lists()
        QMessageBox.information(self, "成功", "已删除选中的进程")

    def _add_whitelist(self):
        """添加进程到白名单"""
        process_name, ok = QInputDialog.getText(
            self, "添加到白名单", "请输入进程名（例如：notepad.exe）:"
        )
        if ok and process_name:
            if self.window_manager.add_to_whitelist(process_name):
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
            if self.window_manager.remove_from_whitelist(process_name):
                logger.info("已从白名单移除进程: %s", process_name)

        self._refresh_lists()
        QMessageBox.information(self, "成功", "已删除选中的进程")
