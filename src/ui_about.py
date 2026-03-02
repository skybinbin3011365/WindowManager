# windowmanager/ui_about.py
"""
窗口管理器 - 关于界面模块
包含关于界面
"""
try:
    import tkinter as tk
    from tkinter import ttk
    TK_AVAILABLE = True
except ImportError:
    TK_AVAILABLE = False
    tk = ttk = None

from .constants import __version__, APP_TITLE


class AboutTab:
    """关于选项卡类"""

    def __init__(self, root):
        """初始化关于选项卡

        Args:
            root: Tkinter根窗口
        """
        if not TK_AVAILABLE:
            raise RuntimeError("Tkinter is required")

        self.root = root

    def build_about_tab(self, parent):
        """构建关于选项卡

        Args:
            parent: 父容器
        """
        about_frame = ttk.Frame(parent, padding=20)
        about_frame.pack(fill=tk.BOTH, expand=True)

        # 标题
        title_label = ttk.Label(about_frame, text=APP_TITLE, font=("Arial", 16, "bold"))
        title_label.pack(pady=10)

        # 版本信息
        version_label = ttk.Label(about_frame, text=f"版本: {__version__}")
        version_label.pack(pady=5)

        # 作者信息
        author_label = ttk.Label(about_frame, text="作者: Stephen Zhao")
        author_label.pack(pady=5)

        # 版本日期
        date_label = ttk.Label(about_frame, text="日期: 2026-02-09")
        date_label.pack(pady=5)

        # 分割线
        separator = ttk.Separator(about_frame, orient="horizontal")
        separator.pack(fill=tk.X, pady=10)

        # 操作说明
        instruction_label = ttk.Label(about_frame, text="操作说明", font=("Arial", 12, "bold"))
        instruction_label.pack(pady=10)

        instructions = [
            "1. 窗口管理: 选择窗口后点击'隐藏选中窗口'按钮",
            "2. 热键操作: 中键+右键隐藏窗口，Shift+右键显示窗口",
            "3. 关键字管理: 添加关键字后，含关键字的窗口会自动选中",
            "4. 进程白名单: 添加进程名到白名单，可过滤不需要的窗口",
            "5. 隐藏到任务栏: 点击按钮可将软件隐藏到系统托盘",
            "6. 全部重置: 清空关键字和选中状态",
            "7. 时间校准: 自动或手动校准系统时间与NTP服务器同步"
        ]

        for instr in instructions:
            instr_label = ttk.Label(about_frame, text=instr, justify=tk.LEFT)
            instr_label.pack(anchor=tk.W, pady=2, padx=20)

        # 版权信息
        copyright_label = ttk.Label(about_frame, text="© 2026 Window Manager. All rights reserved.")
        copyright_label.pack(pady=20)

        # 状态信息
        status_label = ttk.Label(about_frame, text="软件当前运行状态: 正常", foreground="green")
        status_label.pack(pady=5)
