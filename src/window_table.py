# windowmanager/window_table.py
"""
窗口表格组件 - 独立的窗口表格 UI 组件
包含 WindowTableWidget 类，提供表格展示、列隐藏、右键菜单等功能
"""

from PySide6.QtWidgets import (
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QMenu,
    QWidget,
    QHBoxLayout,
    QCheckBox,
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt, Signal

from theme import theme
from constants import UIMainConstants


class WindowTableWidget(QTableWidget):
    """自定义窗口表格组件，支持信号"""

    # 定义信号
    window_double_clicked = Signal(int)  # 窗口句柄
    status_header_clicked = Signal()  # 状态列头点击
    column_visibility_changed = Signal()  # 列可见性发生变化

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(5)
        self.setHorizontalHeaderLabels(["选择", "类型", "标题", "进程", "显示器"])

        # 设置列宽调整模式
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Interactive)  # 选择列
        header.setSectionResizeMode(1, QHeaderView.Interactive)  # 类型列
        header.setSectionResizeMode(2, QHeaderView.Stretch)  # 标题列（自适应）
        header.setSectionResizeMode(3, QHeaderView.Interactive)  # 进程列
        header.setSectionResizeMode(4, QHeaderView.Interactive)  # 显示器列

        # 设置初始列宽
        self.setColumnWidth(0, UIMainConstants.COLUMN_WIDTH_SELECT)  # 选择列
        self.setColumnWidth(1, UIMainConstants.COLUMN_WIDTH_TYPE)  # 类型列
        self.setColumnWidth(3, UIMainConstants.COLUMN_WIDTH_PROCESS)  # 进程列
        self.setColumnWidth(4, UIMainConstants.COLUMN_WIDTH_DISPLAY)  # 显示器列

        # 设置标题行样式 - 现代化配色
        header.setStyleSheet(
            f"""
            QHeaderView::section {{
                background-color: {theme.TABLE_HEADER};
                color: {theme.TABLE_HEADER_TEXT};
                font-weight: bold;
                padding: 8px;
                border: none;
                border-right: 1px solid {theme.BORDER};
            }}
            QHeaderView::section:hover {{
                background-color: {theme.TABLE_ROW_HOVER};
            }}
        """
        )

        self.verticalHeader().setVisible(False)  # 隐藏行号
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setAlternatingRowColors(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)

        # 为表头添加右键菜单，用于显示/隐藏列
        header = self.horizontalHeader()
        header.setContextMenuPolicy(Qt.CustomContextMenu)
        header.customContextMenuRequested.connect(self._on_header_context_menu)

        # 设置表格整体样式
        self.setStyleSheet(
            f"""
            QTableWidget {{
                background-color: {theme.BACKGROUND};
                alternate-background-color: {theme.TABLE_ROW_EVEN};
                gridline-color: {theme.BORDER};
                border: 1px solid {theme.BORDER};
                border-radius: 4px;
            }}
            QTableWidget::item {{
                padding: 6px;
                color: {theme.TEXT_PRIMARY};
            }}
            QTableWidget::item:hover {{
                background-color: {theme.TABLE_ROW_HOVER};
            }}
            QTableWidget::item:selected {{
                background-color: {theme.TABLE_ROW_SELECTED};
                color: {theme.TABLE_ROW_SELECTED_TEXT};
            }}
            QTableWidget::item:selected:hover {{
                background-color: {theme.PRIMARY_LIGHT};
            }}
        """
        )

        # 连接双击信号
        self.cellDoubleClicked.connect(self._on_cell_double_clicked)

    def _on_cell_double_clicked(self, row: int, column: int):
        """处理单元格双击"""
        # 获取窗口句柄（存储在标题列的 UserRole data 中）
        title_item = self.item(row, 2)
        if title_item:
            hwnd = title_item.data(Qt.ItemDataRole.UserRole)
            if hwnd is not None:
                self.window_double_clicked.emit(hwnd)

    def mousePressEvent(self, event):
        """处理鼠标点击事件，检测是否点击了状态列头"""
        if event.button() == Qt.LeftButton:
            # 获取点击位置对应的列索引
            pos = event.pos()
            header = self.horizontalHeader()
            column = header.logicalIndexAt(pos.x())

            # 检查是否点击了列头区域
            if pos.y() < header.height():
                # 检查是否点击了"类型"列（第1列）
                if column == 1:
                    self.status_header_clicked.emit()
                    return

        super().mousePressEvent(event)

    def _on_header_context_menu(self, pos):
        """处理表头右键菜单，用于显示/隐藏列"""
        menu = QMenu(self)

        # 获取表头
        header = self.horizontalHeader()

        # 为每一列添加显示/隐藏选项
        column_names = ["选择", "类型", "标题", "进程", "显示器"]
        for i in range(self.columnCount()):
            action = QAction(column_names[i], self)
            action.setCheckable(True)
            action.setChecked(not header.isSectionHidden(i))
            action.triggered.connect(
                lambda checked, col=i: self._toggle_column_visibility(col, checked)
            )
            menu.addAction(action)

        menu.exec(self.mapToGlobal(pos))

    def _toggle_column_visibility(self, column, visible):
        """切换列的可见性"""
        header = self.horizontalHeader()
        if visible:
            header.showSection(column)
        else:
            header.hideSection(column)
        self.column_visibility_changed.emit()
