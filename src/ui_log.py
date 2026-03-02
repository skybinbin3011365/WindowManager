# windowmanager/ui_log.py
"""
窗口管理器 - 日志界面模块
包含日志显示界面
"""
import logging

try:
    import tkinter as tk
    from tkinter import ttk, scrolledtext
    TK_AVAILABLE = True
except ImportError:
    TK_AVAILABLE = False
    tk = ttk = scrolledtext = None

logger = logging.getLogger(__name__)


class TextLogHandler(logging.Handler):
    """自定义日志处理器，将日志输出到Text控件"""

    def __init__(self, text_widget):
        """初始化日志处理器

        Args:
            text_widget: Tkinter Text控件
        """
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        """发送日志记录

        Args:
            record: 日志记录对象
        """
        try:
            msg = self.format(record)

            # 根据日志级别设置不同的颜色
            if record.levelno >= logging.ERROR:
                tag = "error"
            elif record.levelno >= logging.WARNING:
                tag = "warning"
            elif record.levelno >= logging.INFO:
                tag = "info"
            else:
                tag = "debug"

            # 在Text控件中插入日志
            def append():
                try:
                    if self.text_widget.winfo_exists():
                        self.text_widget.configure(state='normal')
                        self.text_widget.insert(tk.END, msg + '\n', tag)
                        self.text_widget.see(tk.END)
                        self.text_widget.configure(state='disabled')
                except Exception:
                    pass

            # 尝试在主线程中执行UI更新
            try:
                # 检查widget是否存在且在主线程
                if self.text_widget.winfo_exists():
                    try:
                        self.text_widget.after(0, append)
                    except RuntimeError:
                        # 不在主线程中，直接忽略（避免程序崩溃）
                        pass
            except Exception:
                pass
        except Exception:
            self.handleError(record)


class LogTab:
    """日志选项卡类"""

    def __init__(self, root):
        """初始化日志选项卡

        Args:
            root: Tkinter根窗口
        """
        if not TK_AVAILABLE:
            raise RuntimeError("Tkinter is required")

        self.root = root
        self.log_text = None
        self._log_handler = None

    def build_log_tab(self, parent):
        """构建日志选项卡

        Args:
            parent: 父容器
        """
        # 创建日志显示区域
        self.log_text = scrolledtext.ScrolledText(parent, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # 配置标签样式
        self.log_text.tag_config("error", foreground="red")
        self.log_text.tag_config("warning", foreground="orange")
        self.log_text.tag_config("info", foreground="black")
        self.log_text.tag_config("debug", foreground="gray")

        # 创建并添加日志处理器
        self._log_handler = TextLogHandler(self.log_text)
        self._log_handler.setFormatter(
            logging.Formatter('%(asctime)s [%(levelname).1s] %(name)s: %(message)s',
                           datefmt='%Y-%m-%d %H:%M:%S')
        )
        logging.getLogger().addHandler(self._log_handler)

    def clear_log(self):
        """清空日志显示"""
        if self.log_text:
            self.log_text.configure(state='normal')
            self.log_text.delete(1.0, tk.END)
            self.log_text.configure(state='disabled')

    def cleanup(self):
        """清理日志处理器"""
        if self._log_handler:
            logging.getLogger().removeHandler(self._log_handler)
            self._log_handler.close()
            self._log_handler = None
