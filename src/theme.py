# windowmanager/theme.py
"""
窗口管理器 - 现代化配色方案
提供统一的现代化深色主题配色
"""

from PySide6.QtGui import QColor


class ModernTheme:
    """现代化配色方案 - 深色主题"""

    # 主色调 - 现代蓝紫色
    PRIMARY = "#6366F1"
    PRIMARY_LIGHT = "#818CF8"
    PRIMARY_DARK = "#4F46E5"

    # 强调色 - 紫色
    ACCENT = "#8B5CF6"
    ACCENT_LIGHT = "#A78BFA"
    ACCENT_DARK = "#7C3AED"

    # 功能色
    SUCCESS = "#10B981"
    SUCCESS_LIGHT = "#34D399"
    SUCCESS_DARK = "#059669"

    WARNING = "#F59E0B"
    WARNING_LIGHT = "#FBBF24"
    WARNING_DARK = "#D97706"

    DANGER = "#EF4444"
    DANGER_LIGHT = "#F87171"
    DANGER_DARK = "#DC2626"

    # 背景色 - 深色主题
    BACKGROUND = "#0F172A"
    SURFACE = "#1E293B"
    SURFACE_LIGHT = "#334155"
    SURFACE_LIGHTER = "#475569"

    # 文字色
    TEXT_PRIMARY = "#F8FAFC"
    TEXT_SECONDARY = "#94A3B8"
    TEXT_MUTE = "#64748B"

    # 边框色
    BORDER = "#334155"
    BORDER_LIGHT = "#475569"

    # 表格配色
    TABLE_HEADER = "#1E293B"
    TABLE_HEADER_TEXT = "#F8FAFC"
    TABLE_ROW_EVEN = "#0F172A"
    TABLE_ROW_ODD = "#1E293B"
    TABLE_ROW_HOVER = "#334155"
    TABLE_ROW_SELECTED = "#6366F1"
    TABLE_ROW_SELECTED_TEXT = "#FFFFFF"
    TABLE_GRID = "#334155"

    # 按钮配色
    BUTTON_PRIMARY = "#6366F1"
    BUTTON_PRIMARY_HOVER = "#4F46E5"
    BUTTON_PRIMARY_ACTIVE = "#4338CA"

    BUTTON_SECONDARY = "#334155"
    BUTTON_SECONDARY_HOVER = "#475569"
    BUTTON_SECONDARY_ACTIVE = "#64748B"

    BUTTON_SUCCESS = "#10B981"
    BUTTON_SUCCESS_HOVER = "#059669"
    BUTTON_SUCCESS_ACTIVE = "#047857"

    BUTTON_DANGER = "#EF4444"
    BUTTON_DANGER_HOVER = "#DC2626"
    BUTTON_DANGER_ACTIVE = "#B91C1C"

    # 标题栏配色
    TITLE_BAR = "#1E293B"
    TITLE_BAR_TEXT = "#F8FAFC"

    # 分组框配色
    GROUP_BOX = "#1E293B"
    GROUP_BOX_TITLE = "#6366F1"

    # 状态栏配色
    STATUS_BAR = "#0F172A"
    STATUS_BAR_TEXT = "#94A3B8"

    # 输入框配色
    INPUT_BACKGROUND = "#0F172A"
    INPUT_BORDER = "#334155"
    INPUT_BORDER_FOCUS = "#6366F1"
    INPUT_TEXT = "#F8FAFC"
    INPUT_PLACEHOLDER = "#64748B"

    # 滚动条配色
    SCROLLBAR_BACKGROUND = "#0F172A"
    SCROLLBAR_THUMB = "#334155"
    SCROLLBAR_THUMB_HOVER = "#475569"

    # 选中框配色
    CHECKBOX_CHECKED = "#6366F1"
    CHECKBOX_BORDER = "#334155"

    # 进度条配色
    PROGRESS_BAR_BACKGROUND = "#334155"
    PROGRESS_BAR_FILL = "#6366F1"

    # 下拉框配色
    COMBOBOX_BACKGROUND = "#0F172A"
    COMBOBOX_BORDER = "#334155"
    COMBOBOX_ARROW = "#F8FAFC"

    # 菜单配色
    MENU_BACKGROUND = "#1E293B"
    MENU_BORDER = "#334155"
    MENU_HOVER = "#334155"

    # 工具提示配色
    TOOLTIP_BACKGROUND = "#1E293B"
    TOOLTIP_BORDER = "#334155"
    TOOLTIP_TEXT = "#F8FAFC"

    # 阴影
    SHADOW = "rgba(0, 0, 0, 0.3)"

    # 字体
    FONT_FAMILY = '"Segoe UI", "Microsoft YaHei", sans-serif'
    FONT_SIZE_SMALL = "12px"
    FONT_SIZE_NORMAL = "13px"
    FONT_SIZE_MEDIUM = "14px"
    FONT_SIZE_LARGE = "16px"

    # 阴影效果
    SHADOW_SMALL = "0 1px 2px rgba(0, 0, 0, 0.3)"
    SHADOW_MEDIUM = "0 2px 4px rgba(0, 0, 0, 0.3)"
    SHADOW_LARGE = "0 4px 8px rgba(0, 0, 0, 0.4)"
    SHADOW_GLOW = "0 0 10px rgba(99, 102, 241, 0.3)"

    # 渐变效果
    GRADIENT_PRIMARY = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #6366F1, stop:1 #8B5CF6)"
    GRADIENT_SURFACE = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1E293B, stop:1 #0F172A)"
    GRADIENT_BUTTON_PRIMARY = (
        "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #6366F1, stop:1 #4F46E5)"
    )
    GRADIENT_BUTTON_SUCCESS = (
        "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #10B981, stop:1 #059669)"
    )
    GRADIENT_BUTTON_DANGER = (
        "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #EF4444, stop:1 #DC2626)"
    )

    @classmethod
    def get_primary(cls) -> str:
        """获取主色调"""
        return cls.PRIMARY

    @classmethod
    def get_accent(cls) -> str:
        """获取强调色"""
        return cls.ACCENT

    @classmethod
    def get_success(cls) -> str:
        """获取成功色"""
        return cls.SUCCESS

    @classmethod
    def get_warning(cls) -> str:
        """获取警告色"""
        return cls.WARNING

    @classmethod
    def get_danger(cls) -> str:
        """获取危险色"""
        return cls.DANGER

    @classmethod
    def get_background(cls) -> str:
        """获取背景色"""
        return cls.BACKGROUND

    @classmethod
    def get_surface(cls) -> str:
        """获取表面色"""
        return cls.SURFACE

    @classmethod
    def get_text_primary(cls) -> str:
        """获取主要文字色"""
        return cls.TEXT_PRIMARY

    @classmethod
    def get_text_secondary(cls) -> str:
        """获取次要文字色"""
        return cls.TEXT_SECONDARY

    @classmethod
    def get_border(cls) -> str:
        """获取边框色"""
        return cls.BORDER

    @classmethod
    def to_qcolor(cls, hex_color: str) -> QColor:
        """将十六进制颜色转换为 QColor"""
        return QColor(hex_color)

    @classmethod
    def get_temp_message_stylesheet(cls) -> str:
        """获取临时消息的样式表"""
        return """
            background-color: rgba(0, 0, 0, 200);
            color: white;
            padding: 10px 20px;
            border-radius: 5px;
            font-size: 14px;
        """

    @classmethod
    def get_global_stylesheet(cls) -> str:
        """获取全局样式表 - 完整的现代化主题"""
        return f"""
/* 全局样式 */
QWidget {{
    background-color: {cls.BACKGROUND};
    color: {cls.TEXT_PRIMARY};
    font-family: {cls.FONT_FAMILY};
    font-size: {cls.FONT_SIZE_NORMAL};
}}

/* 主窗口 */
QMainWindow {{
    background-color: {cls.BACKGROUND};
    color: {cls.TEXT_PRIMARY};
}}

/* 状态栏 */
QStatusBar {{
    background-color: {cls.STATUS_BAR};
    color: {cls.STATUS_BAR_TEXT};
    border-top: 1px solid {cls.BORDER};
    font-size: {cls.FONT_SIZE_SMALL};
}}

/* 菜单栏 */
QMenuBar {{
    background-color: {cls.SURFACE};
    color: {cls.TEXT_PRIMARY};
    border-bottom: 1px solid {cls.BORDER};
    padding: 2px 0px;
}}

QMenuBar::item {{
    background-color: transparent;
    padding: 4px 8px;
    border-radius: 2px;
    margin: 2px 4px;
}}

QMenuBar::item:selected {{
    background-color: {cls.TABLE_ROW_HOVER};
}}

QMenuBar::item:pressed {{
    background-color: {cls.SURFACE_LIGHT};
}}

/* 菜单 */
QMenu {{
    background-color: {cls.MENU_BACKGROUND};
    color: {cls.TEXT_PRIMARY};
    border: 1px solid {cls.MENU_BORDER};
    border-radius: 4px;
    padding: 4px 0px;
}}

QMenu::item {{
    padding: 6px 16px;
    border-radius: 2px;
    margin: 2px 4px;
}}

QMenu::item:selected {{
    background-color: {cls.MENU_HOVER};
}}

QMenu::item:pressed {{
    background-color: {cls.SURFACE_LIGHT};
}}

QMenu::separator {{
    height: 1px;
    background: {cls.BORDER};
    margin: 4px 0px;
}}

/* 选项卡 */
QTabWidget::pane {{
    border: 1px solid {cls.BORDER};
    background-color: {cls.BACKGROUND};
    border-radius: 4px;
    padding: 0px;
}}

QTabWidget::tab-bar {{
    alignment: left;
}}

QTabBar::tab {{
    background-color: {cls.SURFACE};
    color: {cls.TEXT_SECONDARY};
    border: 1px solid {cls.BORDER};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 8px 16px;
    margin-right: 2px;
    min-width: 80px;
    font-weight: 500;
}}

QTabBar::tab:selected {{
    background-color: {cls.PRIMARY};
    color: {cls.TABLE_ROW_SELECTED_TEXT};
    border-color: {cls.PRIMARY};
}}

QTabBar::tab:hover:!selected {{
    background-color: {cls.SURFACE_LIGHT};
    color: {cls.TEXT_PRIMARY};
}}

/* 分组框 */
QGroupBox {{
    background-color: {cls.GROUP_BOX};
    border: 1px solid {cls.BORDER};
    border-radius: 6px;
    margin-top: 1ex;
    padding-top: 1ex;
    font-weight: bold;
    color: {cls.GROUP_BOX_TITLE};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top center;
    padding: 0 8px;
    background-color: {cls.GROUP_BOX};
    color: {cls.GROUP_BOX_TITLE};
}}

/* 按钮 - 统一样式，带阴影效果 */
QPushButton {{
    background-color: {cls.BUTTON_SECONDARY};
    color: {cls.TEXT_PRIMARY};
    border: 1px solid {cls.BORDER};
    border-radius: 4px;
    padding: 6px 16px;
    font-weight: 500;
    min-height: 28px;
}}

QPushButton:hover {{
    background-color: {cls.BUTTON_SECONDARY_HOVER};
    border-color: {cls.BORDER_LIGHT};
}}

QPushButton:pressed {{
    background-color: {cls.BUTTON_SECONDARY_ACTIVE};
}}

QPushButton:focus {{
    outline: none;
    border-color: {cls.PRIMARY};
}}

QPushButton:disabled {{
    background-color: {cls.SURFACE_LIGHT};
    color: {cls.TEXT_MUTE};
    border-color: {cls.BORDER};
}}

/* 主按钮样式 - 带渐变效果 */
QPushButton#primaryButton {{
    background: {cls.GRADIENT_BUTTON_PRIMARY};
    border: 1px solid {cls.BUTTON_PRIMARY};
    border-radius: 4px;
}}

QPushButton#primaryButton:hover {{
    background: {cls.GRADIENT_BUTTON_PRIMARY};
    border-color: {cls.BUTTON_PRIMARY_HOVER};
}}

QPushButton#primaryButton:pressed {{
    background-color: {cls.BUTTON_PRIMARY_ACTIVE};
}}

/* 成功按钮样式 - 带渐变效果 */
QPushButton#successButton {{
    background: {cls.GRADIENT_BUTTON_SUCCESS};
    border: 1px solid {cls.BUTTON_SUCCESS};
    border-radius: 4px;
}}

QPushButton#successButton:hover {{
    background: {cls.GRADIENT_BUTTON_SUCCESS};
    border-color: {cls.BUTTON_SUCCESS_HOVER};
}}

/* 危险按钮样式 - 带渐变效果 */
QPushButton#dangerButton {{
    background: {cls.GRADIENT_BUTTON_DANGER};
    border: 1px solid {cls.BUTTON_DANGER};
    border-radius: 4px;
}}

QPushButton#dangerButton:hover {{
    background: {cls.GRADIENT_BUTTON_DANGER};
    border-color: {cls.BUTTON_DANGER_HOVER};
}}

/* 输入框 */
QLineEdit {{
    background-color: {cls.INPUT_BACKGROUND};
    color: {cls.INPUT_TEXT};
    border: 1px solid {cls.INPUT_BORDER};
    border-radius: 4px;
    padding: 6px 10px;
    font-size: {cls.FONT_SIZE_NORMAL};
    selection-background-color: {cls.PRIMARY};
}}

QLineEdit:focus {{
    border-color: {cls.INPUT_BORDER_FOCUS};
    outline: none;
}}

QLineEdit:disabled {{
    background-color: {cls.SURFACE_LIGHT};
    color: {cls.TEXT_MUTE};
}}

QLineEdit::placeholder {{
    color: {cls.INPUT_PLACEHOLDER};
}}

/* 文本编辑框 */
QTextEdit {{
    background-color: {cls.INPUT_BACKGROUND};
    color: {cls.INPUT_TEXT};
    border: 1px solid {cls.INPUT_BORDER};
    border-radius: 4px;
    padding: 6px 10px;
    font-size: {cls.FONT_SIZE_NORMAL};
    selection-background-color: {cls.PRIMARY};
}}

QTextEdit:focus {{
    border-color: {cls.INPUT_BORDER_FOCUS};
    outline: none;
}}

QTextEdit:disabled {{
    background-color: {cls.SURFACE_LIGHT};
    color: {cls.TEXT_MUTE};
}}

/* 下拉框 */
QComboBox {{
    background-color: {cls.COMBOBOX_BACKGROUND};
    color: {cls.INPUT_TEXT};
    border: 1px solid {cls.COMBOBOX_BORDER};
    border-radius: 4px;
    padding: 6px 10px;
    min-width: 120px;
}}

QComboBox:hover {{
    border-color: {cls.BORDER_LIGHT};
}}

QComboBox:focus {{
    border-color: {cls.INPUT_BORDER_FOCUS};
    outline: none;
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

QComboBox::down-arrow {{
    width: 12px;
    height: 12px;
    border-image: url(
        image: arrow-down.svg
    );
}}

QComboBox QAbstractItemView {{
    background-color: {cls.MENU_BACKGROUND};
    color: {cls.TEXT_PRIMARY};
    border: 1px solid {cls.MENU_BORDER};
    border-radius: 4px;
    selection-background-color: {cls.PRIMARY};
    outline: none;
    padding: 4px 0px;
}}

QComboBox QAbstractItemView::item {{
    min-height: 30px;
    padding: 4px 10px;
}}

QComboBox QAbstractItemView::item:hover {{
    background-color: {cls.MENU_HOVER};
}}

QComboBox QAbstractItemView::item:selected {{
    background-color: {cls.PRIMARY};
    color: {cls.TABLE_ROW_SELECTED_TEXT};
}}

/* 搜索框样式 */
QFrame#windowSearchFrame {{
    background-color: {cls.SURFACE};
    border: 1px solid {cls.BORDER};
    border-radius: 6px;
    padding: 2px;
}}

QLineEdit#windowSearchInput {{
    background-color: {cls.INPUT_BACKGROUND};
    border: 1px solid {cls.INPUT_BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    font-size: {cls.FONT_SIZE_NORMAL};
}}

QLineEdit#windowSearchInput:focus {{
    border-color: {cls.PRIMARY};
}}

QLineEdit#windowSearchInput::placeholder {{
    color: {cls.TEXT_MUTE};
}}

QPushButton#clearSearchBtn {{
    background-color: transparent;
    border: none;
    color: {cls.TEXT_MUTE};
    font-size: 14px;
    border-radius: 4px;
    padding: 2px 6px;
}}

QPushButton#clearSearchBtn:hover {{
    background-color: {cls.SURFACE_LIGHT};
    color: {cls.TEXT_PRIMARY};
}}

QPushButton#clearSearchBtn:pressed {{
    background-color: {cls.SURFACE_LIGHTER};
}}

/* 复选框 */
QCheckBox {{
    color: {cls.TEXT_PRIMARY};
    spacing: 6px;
    font-size: {cls.FONT_SIZE_NORMAL};
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid {cls.CHECKBOX_BORDER};
    border-radius: 4px;
    background-color: {cls.BACKGROUND};
}}

QCheckBox::indicator:hover {{
    border-color: {cls.PRIMARY};
}}

QCheckBox::indicator:checked {{
    background-color: {cls.CHECKBOX_CHECKED};
    border-color: {cls.CHECKBOX_CHECKED};
    image: url(
        image: check.svg
    );
}}

QCheckBox::indicator:checked:hover {{
    background-color: {cls.PRIMARY_LIGHT};
    border-color: {cls.PRIMARY_LIGHT};
}}

QCheckBox::indicator:disabled {{
    background-color: {cls.SURFACE_LIGHT};
    border-color: {cls.BORDER};
}}

/* 单选框 */
QRadioButton {{
    color: {cls.TEXT_PRIMARY};
    spacing: 6px;
}}

QRadioButton::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid {cls.CHECKBOX_BORDER};
    border-radius: 9px;
    background-color: {cls.BACKGROUND};
}}

QRadioButton::indicator:hover {{
    border-color: {cls.PRIMARY};
}}

QRadioButton::indicator:checked {{
    background-color: {cls.CHECKBOX_CHECKED};
    border-color: {cls.CHECKBOX_CHECKED};
}}

/* 表格 - 带阴影效果 */
QTableWidget {{
    background-color: {cls.BACKGROUND};
    alternate-background-color: {cls.TABLE_ROW_EVEN};
    gridline-color: {cls.TABLE_GRID};
    border: 1px solid {cls.BORDER};
    border-radius: 6px;
    selection-background-color: {cls.PRIMARY};
    outline: none;
}}

QTableWidget::item {{
    padding: 6px;
    color: {cls.TEXT_PRIMARY};
    border: none;
}}

QTableWidget::item:hover {{
    background-color: {cls.TABLE_ROW_HOVER};
}}

QTableWidget::item:selected {{
    background-color: {cls.TABLE_ROW_SELECTED};
    color: {cls.TABLE_ROW_SELECTED_TEXT};
}}

QTableWidget::item:selected:hover {{
    background-color: {cls.PRIMARY_LIGHT};
}}

/* 表格左上角的corner button */
QTableWidget QTableCornerButton::section {{
    background-color: {cls.TABLE_HEADER};
    border: 1px solid {cls.BORDER};
    border-right: 1px solid {cls.BORDER};
    border-bottom: 1px solid {cls.BORDER};
}}

QHeaderView::section {{
    background-color: {cls.TABLE_HEADER};
    color: {cls.TABLE_HEADER_TEXT};
    font-weight: bold;
    padding: 8px;
    border: none;
    border-right: 1px solid {cls.BORDER};
    border-bottom: 1px solid {cls.BORDER};
    border-left: 1px solid {cls.BORDER};
}}

QHeaderView::section:first {{
    border-left: 1px solid {cls.BORDER};
}}

QHeaderView::section:hover {{
    background-color: {cls.TABLE_ROW_HOVER};
}}

QHeaderView::section:pressed {{
    background-color: {cls.SURFACE_LIGHT};
}}

/* 滚动条 */
QScrollBar:vertical {{
    background-color: {cls.SCROLLBAR_BACKGROUND};
    width: 12px;
    margin: 0px;
    border-radius: 6px;
}}

QScrollBar::handle:vertical {{
    background-color: {cls.SCROLLBAR_THUMB};
    min-height: 30px;
    border-radius: 6px;
    margin: 2px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {cls.SCROLLBAR_THUMB_HOVER};
}}

QScrollBar::add-line:vertical {{
    height: 0px;
}}

QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}

QScrollBar:horizontal {{
    background-color: {cls.SCROLLBAR_BACKGROUND};
    height: 12px;
    margin: 0px;
    border-radius: 6px;
}}

QScrollBar::handle:horizontal {{
    background-color: {cls.SCROLLBAR_THUMB};
    min-width: 30px;
    border-radius: 6px;
    margin: 2px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {cls.SCROLLBAR_THUMB_HOVER};
}}

QScrollBar::add-line:horizontal {{
    width: 0px;
}}

QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: none;
}}

/* 分割器 */
QSplitter::handle {{
    background-color: {cls.BORDER};
}}

QSplitter::handle:hover {{
    background-color: {cls.BORDER_LIGHT};
}}

QSplitter::handle:horizontal {{
    width: 2px;
}}

QSplitter::handle:vertical {{
    height: 2px;
}}

/* 进度条 */
QProgressBar {{
    background-color: {cls.PROGRESS_BAR_BACKGROUND};
    border: 1px solid {cls.BORDER};
    border-radius: 4px;
    text-align: center;
    color: {cls.TEXT_PRIMARY};
    height: 20px;
}}

QProgressBar::chunk {{
    background-color: {cls.PROGRESS_BAR_FILL};
    border-radius: 3px;
}}

/* 工具提示 */
QToolTip {{
    background-color: {cls.TOOLTIP_BACKGROUND};
    color: {cls.TOOLTIP_TEXT};
    border: 1px solid {cls.TOOLTIP_BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    font-size: {cls.FONT_SIZE_SMALL};
}}

/* 列表视图 */
QListView {{
    background-color: {cls.BACKGROUND};
    color: {cls.TEXT_PRIMARY};
    border: 1px solid {cls.BORDER};
    border-radius: 4px;
    outline: none;
    padding: 4px;
}}

QListView::item {{
    padding: 6px;
    border-radius: 4px;
    margin: 2px;
}}

QListView::item:hover {{
    background-color: {cls.TABLE_ROW_HOVER};
}}

QListView::item:selected {{
    background-color: {cls.PRIMARY};
    color: {cls.TABLE_ROW_SELECTED_TEXT};
}}

/* 列表部件 */
QListWidget {{
    background-color: {cls.BACKGROUND};
    color: {cls.TEXT_PRIMARY};
    border: 1px solid {cls.BORDER};
    border-radius: 4px;
    outline: none;
    padding: 4px;
}}

QListWidget::item {{
    padding: 6px;
    border-radius: 4px;
    margin: 2px;
}}

QListWidget::item:hover {{
    background-color: {cls.TABLE_ROW_HOVER};
}}

QListWidget::item:selected {{
    background-color: {cls.PRIMARY};
    color: {cls.TABLE_ROW_SELECTED_TEXT};
}}

/* 树形视图 */
QTreeView {{
    background-color: {cls.BACKGROUND};
    color: {cls.TEXT_PRIMARY};
    border: 1px solid {cls.BORDER};
    border-radius: 4px;
    outline: none;
    padding: 4px;
}}

QTreeView::item {{
    padding: 6px;
    border-radius: 4px;
    margin: 2px 0px;
}}

QTreeView::item:hover {{
    background-color: {cls.TABLE_ROW_HOVER};
}}

QTreeView::item:selected {{
    background-color: {cls.PRIMARY};
    color: {cls.TABLE_ROW_SELECTED_TEXT};
}}

QTreeView::branch {{
    background-color: transparent;
}}

QTreeView::branch:has-siblings:!adjoins-item {{
    border: none;
}}

/* 标签 */
QLabel {{
    color: {cls.TEXT_PRIMARY};
    font-size: {cls.FONT_SIZE_NORMAL};
}}

/* 微调框 */
QSpinBox {{
    background-color: {cls.INPUT_BACKGROUND};
    color: {cls.INPUT_TEXT};
    border: 1px solid {cls.INPUT_BORDER};
    border-radius: 4px;
    padding: 4px 8px;
}}

QSpinBox:focus {{
    border-color: {cls.INPUT_BORDER_FOCUS};
    outline: none;
}}

QSpinBox::up-button {{
    border: none;
    width: 16px;
}}

QSpinBox::down-button {{
    border: none;
    width: 16px;
}}

/* 工具按钮 */
QToolButton {{
    background-color: {cls.BUTTON_SECONDARY};
    color: {cls.TEXT_PRIMARY};
    border: 1px solid {cls.BORDER};
    border-radius: 4px;
    padding: 4px 10px;
    font-weight: 500;
}}

QToolButton:hover {{
    background-color: {cls.BUTTON_SECONDARY_HOVER};
    border-color: {cls.BORDER_LIGHT};
}}

QToolButton:pressed {{
    background-color: {cls.BUTTON_SECONDARY_ACTIVE};
}}

QToolButton::menu-indicator {{
    image: none;
}}

/* 系统托盘 */
QSystemTrayIcon {{
}}
"""


# 全局配色方案实例
theme = ModernTheme()
