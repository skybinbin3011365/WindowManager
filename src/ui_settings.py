# windowmanager/ui_settings.py
"""
窗口管理器 - 设置界面模块
包含热键设置和其他设置界面
"""
import logging
import threading
import re
from typing import Optional

try:
    import tkinter as tk
    from tkinter import ttk, scrolledtext
    TK_AVAILABLE = True
except ImportError:
    TK_AVAILABLE = False
    tk = ttk = scrolledtext = None

from . import hotkey_manager
from .config import Config
HotkeyManager = hotkey_manager.HotkeyManager

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


class SettingsTab:
    """设置选项卡类"""

    def __init__(self, root, config_manager=None, config=None, hotkey_manager=None):
        """初始化设置选项卡

        Args:
            root: Tkinter根窗口
            config_manager: 配置管理器实例
            config: 配置对象
            hotkey_manager: 热键管理器实例
        """
        if not TK_AVAILABLE:
            raise RuntimeError("Tkinter is required")

        self.root = root
        self.config_manager = config_manager
        self.config = config
        self.hotkey_manager = hotkey_manager

        # UI变量
        self.hide_hotkey_var = None
        self.show_hotkey_var = None
        self.auto_start_var = None
        self.log_window_var = None
        self.log_time_var = None
        self.whitelist_var = None
        self.whitelist_listbox = None
        self.hide_record_btn = None
        self.show_record_btn = None
        self.log_text = None
        self._log_handler = None

        # 当前正在录制的热键类型：'hide' 或 'show'
        self._recording_target = None

        # 自动停止录制的定时器ID
        self._auto_stop_timer = None

        # 状态管理线程锁
        self._state_lock = threading.Lock()

    def build_settings_tab(self, parent):
        """构建设置选项卡

        Args:
            parent: 父容器
        """
        # 创建左中右三栏布局
        left_frame = ttk.Frame(parent, width=350)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=5, pady=5)

        middle_frame = ttk.Frame(parent, width=300)
        middle_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=5, pady=5)

        right_frame = ttk.Frame(parent)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # ============= 左栏：热键设置和日志选项 =============
        # 上部分：热键设置
        hotkey_frame = ttk.LabelFrame(left_frame, text="热键设置")
        hotkey_frame.pack(fill=tk.X, padx=5, pady=5)

        # 隐藏窗口热键
        hide_frame = ttk.Frame(hotkey_frame)
        hide_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(hide_frame, text="隐藏窗口热键:").pack(side=tk.LEFT, padx=5)
        self.hide_hotkey_var = tk.StringVar(value=self.config.hide_hotkey)
        hide_entry = ttk.Entry(hide_frame, textvariable=self.hide_hotkey_var, width=20)
        hide_entry.pack(side=tk.LEFT, padx=5)
        # 绑定鼠标进入和点击事件
        hide_entry.bind("<FocusIn>", lambda e: self._set_recording_target('hide'))
        hide_entry.bind("<Enter>", lambda e: self._set_recording_target('hide'))
        hide_entry.bind("<Button-1>", lambda e: self._set_recording_target('hide'))

        # 显示窗口热键
        show_frame = ttk.Frame(hotkey_frame)
        show_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(show_frame, text="显示窗口热键:").pack(side=tk.LEFT, padx=5)
        self.show_hotkey_var = tk.StringVar(value=self.config.show_hotkey)
        show_entry = ttk.Entry(show_frame, textvariable=self.show_hotkey_var, width=20)
        show_entry.pack(side=tk.LEFT, padx=5)
        # 绑定鼠标进入和点击事件
        show_entry.bind("<FocusIn>", lambda e: self._set_recording_target('show'))
        show_entry.bind("<Enter>", lambda e: self._set_recording_target('show'))
        show_entry.bind("<Button-1>", lambda e: self._set_recording_target('show'))

        # 录制按钮
        btn_frame = ttk.Frame(hotkey_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)

        self.hide_record_btn = ttk.Button(btn_frame, text="录制隐藏热键", 
                                          command=lambda: self._start_record_hotkey('hide'), width=12)
        self.hide_record_btn.pack(side=tk.LEFT, padx=5)
        
        self.show_record_btn = ttk.Button(btn_frame, text="录制显示热键", 
                                          command=lambda: self._start_record_hotkey('show'), width=12)
        self.show_record_btn.pack(side=tk.LEFT, padx=5)

        # 开机自启动选项
        startup_frame = ttk.Frame(hotkey_frame)
        startup_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(startup_frame, text="开机自启动:").pack(side=tk.LEFT, padx=5)
        self.auto_start_var = tk.BooleanVar(value=self.config.auto_start)
        ttk.Checkbutton(startup_frame, variable=self.auto_start_var).pack(side=tk.LEFT, padx=5)

        # 下部分：日志显示选项
        log_options_frame = ttk.LabelFrame(left_frame, text="日志显示选项")
        log_options_frame.pack(fill=tk.X, padx=5, pady=5)

        # 隐藏/显示窗口操作日志
        log_window_frame = ttk.Frame(log_options_frame)
        log_window_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(log_window_frame, text="隐藏/显示窗口操作日志:").pack(side=tk.LEFT, padx=5)
        self.log_window_var = tk.BooleanVar(value=getattr(self.config, 'log_window_operations', True))
        ttk.Checkbutton(log_window_frame, variable=self.log_window_var).pack(side=tk.LEFT, padx=5)

        # 时间校准日志
        log_time_frame = ttk.Frame(log_options_frame)
        log_time_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(log_time_frame, text="时间校准、检测日志:").pack(side=tk.LEFT, padx=5)
        self.log_time_var = tk.BooleanVar(value=getattr(self.config, 'log_time_calibration', True))
        ttk.Checkbutton(log_time_frame, variable=self.log_time_var).pack(side=tk.LEFT, padx=5)

        # 保存按钮
        button_frame = ttk.Frame(left_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=10)

        ttk.Button(button_frame, text="保存设置", command=self._save_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="恢复默认", command=self._reset_settings).pack(side=tk.LEFT, padx=5)

        # ============= 中栏：进程白名单 =============
        whitelist_frame = ttk.LabelFrame(middle_frame, text="进程白名单")
        whitelist_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        whitelist_input_frame = ttk.Frame(whitelist_frame)
        whitelist_input_frame.pack(fill=tk.X, padx=5, pady=5)

        self.whitelist_var = tk.StringVar()
        ttk.Entry(whitelist_input_frame, textvariable=self.whitelist_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(whitelist_input_frame, text="添加", command=self._add_whitelist).pack(side=tk.RIGHT, padx=5)

        self.whitelist_listbox = tk.Listbox(whitelist_frame)
        self.whitelist_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        whitelist_button_frame = ttk.Frame(whitelist_frame)
        whitelist_button_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(whitelist_button_frame, text="删除选中", command=self._remove_selected_whitelist).pack(side=tk.LEFT, padx=5)
        ttk.Button(whitelist_button_frame, text="全部删除", command=self._remove_all_whitelist).pack(side=tk.RIGHT, padx=5)

        # 填充白名单列表
        if self.config and self.config.process_whitelist:
            for process in self.config.process_whitelist:
                self.whitelist_listbox.insert(tk.END, process)

        # ============= 右栏：日志显示 =============
        log_display_frame = ttk.LabelFrame(right_frame, text="日志显示")
        log_display_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 创建日志显示区域
        self.log_text = scrolledtext.ScrolledText(log_display_frame, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # 配置标签样式
        self.log_text.tag_config("error", foreground="red")
        self.log_text.tag_config("warning", foreground="orange")
        self.log_text.tag_config("info", foreground="black")
        self.log_text.tag_config("debug", foreground="gray")

        # 创建但先不添加日志处理器，延迟添加避免阻塞
        self._log_handler = TextLogHandler(self.log_text)
        self._log_handler.setFormatter(
            logging.Formatter('%(asctime)s [%(levelname).1s] %(name)s: %(message)s',
                           datefmt='%Y-%m-%d %H:%M:%S')
        )
        
        # 延迟添加日志处理器
        def add_handler_later():
            try:
                logging.getLogger().addHandler(self._log_handler)
            except Exception:
                pass
        self.root.after(100, add_handler_later)

    def _set_recording_target(self, target):
        """设置录制目标

        Args:
            target: 'hide' 或 'show'
        """
        with self._state_lock:
            # 只有在没有正在录制时才切换
            if self._recording_target is None:
                self._recording_target = target

    def _start_record_hotkey(self, target):
        """开始录制热键
        
        Args:
            target: 'hide' 或 'show'
        """
        with self._state_lock:
            self._recording_target = target + '_recording'  # 标记正在录制

        # 禁用两个按钮
        self.hide_record_btn.config(state="disabled", text="录制中...")
        self.show_record_btn.config(state="disabled", text="录制中...")

        # 设置2秒后自动停止录制
        self._auto_stop_timer = self.root.after(2000, self._stop_record_hotkey)

        if self.hotkey_manager:
            self.hotkey_manager.start_recording(
                callback=self._on_hotkey_recorded,
                realtime_update_callback=self._on_hotkey_update
            )

    def _stop_record_hotkey(self):
        """停止录制热键"""
        # 取消自动停止定时器
        if self._auto_stop_timer:
            self.root.after_cancel(self._auto_stop_timer)
            self._auto_stop_timer = None

        with self._state_lock:
            target = None
            if self._recording_target and '_recording' in self._recording_target:
                target = self._recording_target.replace('_recording', '')
                self._recording_target = target

        # 恢复两个按钮
        self.hide_record_btn.config(state="normal", text="录制隐藏热键")
        self.show_record_btn.config(state="normal", text="录制显示热键")

        if self.hotkey_manager:
            self.hotkey_manager.stop_recording()

    def _on_hotkey_recorded(self, hotkey_sequence):
        """热键录制完成回调

        Args:
            hotkey_sequence: 录制的热键序列
        """
        if hotkey_sequence:
            with self._state_lock:
                target = None
                if self._recording_target and '_recording' in self._recording_target:
                    target = self._recording_target.replace('_recording', '')
                    self._recording_target = target

            # 取消自动停止定时器
            if self._auto_stop_timer:
                self.root.after_cancel(self._auto_stop_timer)
                self._auto_stop_timer = None

            # 使用root.after确保UI更新在主线程执行
            def update_ui():
                if target == 'hide':
                    self.hide_hotkey_var.set(hotkey_sequence)
                    if self.config:
                        self.config.hide_hotkey = hotkey_sequence
                elif target == 'show':
                    self.show_hotkey_var.set(hotkey_sequence)
                    if self.config:
                        self.config.show_hotkey = hotkey_sequence

                # 恢复按钮状态
                self.hide_record_btn.config(state="normal", text="录制隐藏热键")
                self.show_record_btn.config(state="normal", text="录制显示热键")

            self.root.after(0, update_ui)

    def _on_hotkey_update(self, hotkey_sequence):
        """热键录制实时更新回调

        Args:
            hotkey_sequence: 当前录制的热键序列
        """
        if hotkey_sequence:
            with self._state_lock:
                target = None
                if self._recording_target and '_recording' in self._recording_target:
                    target = self._recording_target.replace('_recording', '')

            # 使用root.after确保UI更新在主线程执行
            def update_ui():
                if target == 'hide':
                    self.hide_hotkey_var.set(hotkey_sequence)
                elif target == 'show':
                    self.show_hotkey_var.set(hotkey_sequence)

            self.root.after(0, update_ui)

    def _validate_process_name(self, process: str) -> bool:
        """验证进程名格式是否有效

        Args:
            process: 进程名

        Returns:
            bool: 是否有效
        """
        if not process:
            return False
        # 允许进程名格式：xxx.exe 或 xxx（不带扩展名）
        # 只允许字母、数字、下划线、连字符和点
        pattern = r'^[a-zA-Z0-9_.-]+(\.exe)?$'
        return bool(re.match(pattern, process, re.IGNORECASE))

    def _add_whitelist(self):
        """添加进程到白名单"""
        process = self.whitelist_var.get().strip()

        # 验证进程名格式
        if not process:
            logger.warning("进程名不能为空")
            return

        if not self._validate_process_name(process):
            logger.warning("无效的进程名格式: %s，只允许字母、数字、下划线、连字符和点", process)
            # 显示提示信息
            try:
                if TK_AVAILABLE:
                    from tkinter import messagebox
                    messagebox.showwarning("无效输入",
                        f"进程名 '{process}' 格式无效。\n"
                        "只允许字母、数字、下划线、连字符和点。\n"
                        "例如: notepad.exe 或 chrome")
            except Exception:
                pass
            return

        if self.config:
            if not self.config.process_whitelist:
                self.config.process_whitelist = []

            if process not in self.config.process_whitelist:
                self.config.process_whitelist.append(process)
                self.whitelist_listbox.insert(tk.END, process)
                self.whitelist_var.set("")
                self._save_whitelist()

    def _remove_selected_whitelist(self):
        """删除选中的白名单项"""
        selection = self.whitelist_listbox.curselection()
        if selection and self.config:
            index = selection[0]
            process = self.whitelist_listbox.get(index)
            if process in self.config.process_whitelist:
                self.config.process_whitelist.remove(process)
                self.whitelist_listbox.delete(index)
                self._save_whitelist()

    def _remove_all_whitelist(self):
        """删除所有白名单项"""
        if self.config:
            self.config.process_whitelist = []
            self.whitelist_listbox.delete(0, tk.END)
            self._save_whitelist()

    def _save_whitelist(self):
        """保存白名单到配置"""
        if self.config and self.config_manager:
            self.config_manager.save(self.config)

    def _save_settings(self):
        """保存设置"""
        if self.config and self.config_manager:
            # 保存热键设置
            self.config.hide_hotkey = self.hide_hotkey_var.get()
            self.config.show_hotkey = self.show_hotkey_var.get()

            # 保存自启动设置
            self.config.auto_start = self.auto_start_var.get()

            # 保存日志选项
            self.config.log_window_operations = self.log_window_var.get()
            self.config.log_time_calibration = self.log_time_var.get()

            # 保存配置
            self.config_manager.save(self.config)

            logger.info("Settings saved successfully")

    def _reset_settings(self):
        """恢复默认设置"""
        if self.config and self.config_manager:
            # 创建默认配置
            default_config = self.config_manager.load()

            # 恢复热键设置
            self.hide_hotkey_var.set(default_config.hide_hotkey)
            self.show_hotkey_var.set(default_config.show_hotkey)

            # 恢复自启动设置
            self.auto_start_var.set(default_config.auto_start)

            # 恢复日志选项
            self.log_window_var.set(default_config.log_window_operations)
            self.log_time_var.set(default_config.log_time_calibration)

            # 保存配置
            self.config_manager.save(default_config)

            logger.info("Settings reset to default")

    def cleanup(self):
        """清理日志处理器"""
        if self._log_handler:
            logging.getLogger().removeHandler(self._log_handler)
            self._log_handler.close()
            self._log_handler = None
