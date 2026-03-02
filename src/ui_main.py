# windowmanager/ui_main.py
"""
窗口管理器 - 主窗口模块
包含主窗口和窗口管理功能
"""
import logging
import threading
from typing import Optional, List

try:
    import tkinter as tk
    from tkinter import ttk
    TK_AVAILABLE = True
except ImportError:
    TK_AVAILABLE = False
    tk = ttk = None

from . import core
from . import manager
WindowState = core.WindowState
WindowManager = manager.WindowManager

logger = logging.getLogger(__name__)


class MainWindow:
    """主窗口类 - 负责窗口管理功能"""

    def __init__(self, root, window_manager: Optional[WindowManager] = None,
                 config_manager=None, config=None, hotkey_manager=None):
        """初始化主窗口

        Args:
            root: Tkinter根窗口
            window_manager: 窗口管理器实例
            config_manager: 配置管理器实例
            config: 配置对象
            hotkey_manager: 热键管理器实例
        """
        if not TK_AVAILABLE:
            raise RuntimeError("Tkinter is required")

        self.root = root
        self.window_manager = window_manager
        self.config_manager = config_manager
        self.config = config
        self.hotkey_manager = hotkey_manager

        # 窗口选择和关键字
        self._selected_windows: set = set()
        self._keywords: List[str] = []

        # 从配置加载关键字
        if hasattr(self.config, 'keywords') and self.config.keywords:
            # 去重关键字（使用set去重，保持原顺序）
            seen = set()
            self._keywords = [k for k in self.config.keywords if not (k in seen or seen.add(k))]

        # 从配置加载选中的窗口
        if hasattr(self.config, 'selected_windows') and self.config.selected_windows:
            for hwnd in self.config.selected_windows:
                self._selected_windows.add(hwnd)

        # UI变量
        self.status_var = None
        self.keyword_var = None
        self.keyword_listbox = None
        self.window_tree = None

    def build_main_tab(self, parent):
        """构建主选项卡

        Args:
            parent: 父容器
        """
        left_frame = ttk.Frame(parent, width=300)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        keyword_frame = ttk.LabelFrame(left_frame, text="关键字管理")
        keyword_frame.pack(fill=tk.BOTH, expand=True)

        keyword_input_frame = ttk.Frame(keyword_frame)
        keyword_input_frame.pack(fill=tk.X, padx=5, pady=5)

        self.keyword_var = tk.StringVar()
        ttk.Entry(keyword_input_frame, textvariable=self.keyword_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(keyword_input_frame, text="添加", command=self._add_keyword).pack(side=tk.RIGHT, padx=5)

        self.keyword_listbox = tk.Listbox(keyword_frame)
        self.keyword_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 填充已加载的关键字
        for keyword in self._keywords:
            self.keyword_listbox.insert(tk.END, keyword)

        keyword_button_frame = ttk.Frame(keyword_frame)
        keyword_button_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(keyword_button_frame, text="删除选中", command=self._remove_selected_keyword).pack(side=tk.LEFT, padx=5)
        ttk.Button(keyword_button_frame, text="全部删除", command=self._remove_all_keywords).pack(side=tk.RIGHT, padx=5)

        right_frame = ttk.Frame(parent)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        window_frame = ttk.LabelFrame(right_frame, text="窗口列表")
        window_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("Select", "Status", "HWND", "Title", "Class", "PID")
        self.window_tree = ttk.Treeview(window_frame, columns=columns, show="headings")

        self.window_tree.heading("Select", text="选择")
        self.window_tree.column("Select", width=80, anchor=tk.CENTER)
        self.window_tree.heading("Status", text="状态")
        self.window_tree.column("Status", width=60, anchor=tk.CENTER)
        self.window_tree.heading("HWND", text="句柄")
        self.window_tree.column("HWND", width=100)
        self.window_tree.heading("Title", text="标题")
        self.window_tree.column("Title", width=250)
        self.window_tree.heading("Class", text="类名")
        self.window_tree.column("Class", width=120)
        self.window_tree.heading("PID", text="PID")
        self.window_tree.column("PID", width=80)
        
        # 配置Treeview标签样式
        self.window_tree.tag_configure("selected", background="#e6ffe6", foreground="#0078d7", font=("Arial", 10))
        self.window_tree.tag_configure("unselected_visible", background="#e6f2ff", font=("Arial", 10))
        self.window_tree.tag_configure("unselected_hidden", background="#ffe6e6", font=("Arial", 10))
        
        # 增大Treeview的行高
        try:
            style = ttk.Style()
            style.configure("Treeview", rowheight=36)
        except Exception:
            pass

        # 添加滚动条
        scrollbar = ttk.Scrollbar(window_frame, orient=tk.VERTICAL, command=self.window_tree.yview)
        self.window_tree.configure(yscrollcommand=scrollbar.set)

        self.window_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 绑定事件
        self.window_tree.bind("<Double-1>", self._on_window_double_click)
        self.window_tree.bind("<Button-1>", self._on_window_click)

    def _add_keyword(self):
        """添加关键字"""
        try:
            keyword = self.keyword_var.get().strip()
            logger.debug("Attempting to add keyword: '%s'", keyword)
            logger.debug("Current keywords: %s", self._keywords)

            if not keyword:
                logger.warning("Keyword is empty, not adding")
                return

            if keyword in self._keywords:
                logger.warning("Keyword '%s' already exists, not adding", keyword)
                return

            # 添加关键字
            self._keywords.append(keyword)
            self.keyword_listbox.insert(tk.END, keyword)
            self.keyword_var.set("")

            logger.info("Successfully added keyword: '%s'", keyword)
            logger.debug("Updated keywords: %s", self._keywords)

            # 保存配置
            self._save_keywords()
        except Exception as e:
            logger.error("Error adding keyword: %s", str(e), exc_info=True)

    def _remove_selected_keyword(self):
        """删除选中的关键字"""
        selection = self.keyword_listbox.curselection()
        if selection:
            index = selection[0]
            keyword = self.keyword_listbox.get(index)
            self._keywords.remove(keyword)
            self.keyword_listbox.delete(index)
            self._save_keywords()

    def _remove_all_keywords(self):
        """删除所有关键字"""
        self._keywords.clear()
        self.keyword_listbox.delete(0, tk.END)
        self._save_keywords()

    def _save_keywords(self):
        """保存关键字到配置"""
        try:
            logger.debug("Saving keywords to config: %s", self._keywords)
            if self.config:
                self.config.keywords = self._keywords
                if self.config_manager:
                    success = self.config_manager.save(self.config)
                    if success:
                        logger.info("Keywords saved successfully")
                    else:
                        logger.error("Failed to save keywords")
            else:
                logger.error("Config is None, cannot save keywords")
        except Exception as e:
            logger.error("Error saving keywords: %s", str(e), exc_info=True)

    def _on_window_click(self, event):
        """处理窗口列表点击事件

        Args:
            event: 事件对象
        """
        region = self.window_tree.identify_region(event.x, event.y)
        if region == "cell":
            column = self.window_tree.identify_column(event.x)
            if column == "#1":  # 选择列
                item = self.window_tree.identify_row(event.y)
                if item:
                    values = self.window_tree.item(item, "values")
                    if values:
                        hwnd = int(values[2])
                        if hwnd in self._selected_windows:
                            self._selected_windows.remove(hwnd)
                            self.window_tree.set(item, "Select", "⬜")
                        else:
                            self._selected_windows.add(hwnd)
                            self.window_tree.set(item, "Select", "✅")
                        self._save_selected_windows()

    def _on_window_double_click(self, event):
        """处理窗口列表双击事件

        Args:
            event: 事件对象
        """
        item = self.window_tree.identify_row(event.y)
        if item:
            values = self.window_tree.item(item, "values")
            if values:
                hwnd = int(values[2])
                if self.window_manager:
                    window = self.window_manager.get_window(hwnd)
                    if window:
                        if window.state == WindowState.HIDDEN:
                            self.window_manager.show_window(hwnd)
                        else:
                            self.window_manager.hide_window(hwnd)
                        self._refresh_window_item(item)

    def _refresh_window_item(self, item):
        """刷新窗口项的状态

        Args:
            item: 树视图项
        """
        values = self.window_tree.item(item, "values")
        if values:
            hwnd = int(values[2])
            if self.window_manager:
                window = self.window_manager.get_window(hwnd)
                if window:
                    status = "隐藏" if window.state == WindowState.HIDDEN else "显示"
                    self.window_tree.set(item, "Status", status)

    def _save_selected_windows(self):
        """保存选中的窗口到配置"""
        if self.config:
            self.config.selected_windows = list(self._selected_windows)
            if self.config_manager:
                self.config_manager.save(self.config)

    def refresh_windows(self):
        """刷新窗口列表"""
        if not self.window_manager:
            logger.warning("Window manager not available")
            if self.status_var:
                self.status_var.set("窗口管理器未运行")
            return

        if not self.window_manager.is_running:
            logger.warning("Window manager is not running")
            if self.status_var:
                self.status_var.set("窗口管理器未运行")
            return

        def _refresh_in_background():
            """在后台线程中执行窗口刷新"""
            try:
                # 在后台线程中刷新窗口
                windows = self.window_manager.refresh_windows()

                # 在UI线程中更新界面
                self.root.after(0, lambda: self._update_window_list(windows))
            except Exception as e:
                logger.error("Error in refresh_windows background thread: %s", str(e))
                # 在UI线程中更新状态
                self.root.after(0, lambda: self._update_status("刷新失败"))

        # 更新状态并启动后台线程
        if self.status_var:
            self.status_var.set("正在刷新...")

        # 启动后台线程
        refresh_thread = threading.Thread(target=_refresh_in_background, daemon=True)
        refresh_thread.start()

    def _update_window_list(self, windows):
        """更新窗口列表UI

        Args:
            windows: 窗口信息列表
        """
        # 保存人工选择的窗口状态
        selected_before = self._selected_windows.copy()

        # 清空窗口列表
        for item in self.window_tree.get_children():
            self.window_tree.delete(item)

        # 填充窗口列表
        logger.debug("Total windows from manager: %d", len(windows))
        logger.debug("Keywords: %s", self._keywords)
        logger.debug("Window tree initialized: %s", self.window_tree is not None)

        # 过滤白名单中的进程
        matched_windows = self._filter_windows_by_whitelist(windows)

        # 分组窗口
        selected_windows, unselected_visible_windows, unselected_hidden_windows = self._group_windows(
            matched_windows, selected_before
        )

        # 添加窗口到列表
        added_count = 0

        # 1. 已选择窗口
        added_count += self._add_windows_to_tree(
            selected_windows, "已选择", "selected", "lightblue"
        )

        # 添加分割线
        if selected_windows and (unselected_visible_windows or unselected_hidden_windows):
            self._add_separator()

        # 2. 未选择但显示的窗口
        added_count += self._add_windows_to_tree(
            unselected_visible_windows, "未选择", "unselected_visible", "lightgreen"
        )

        # 添加分割线
        if (selected_windows or unselected_visible_windows) and unselected_hidden_windows:
            self._add_separator()

        # 3. 未选择且隐藏的窗口
        added_count += self._add_windows_to_tree(
            unselected_hidden_windows, "未选择", "unselected_hidden", "lightgray"
        )

        logger.debug("Added %d windows to list", added_count)
        logger.debug("Final tree item count: %d", len(self.window_tree.get_children()))

        self._update_status("就绪")

    def _filter_windows_by_whitelist(self, windows):
        """根据白名单过滤窗口

        Args:
            windows: 窗口信息列表

        Returns:
            List[WindowInfo]: 过滤后的窗口列表
        """
        whitelist = []
        if self.config and hasattr(self.config, 'process_whitelist') and self.config.process_whitelist:
            whitelist = self.config.process_whitelist

        matched_windows = []
        for window in windows:
            # 获取进程名（带或不带.exe后缀）
            process_name = window.process_name.lower() if window.process_name else ""
            process_name_no_ext = process_name.replace('.exe', '')

            # 检查是否在白名单中
            is_whitelisted = False
            for whitelist_item in whitelist:
                whitelist_item_lower = whitelist_item.lower()
                whitelist_item_no_ext = whitelist_item_lower.replace('.exe', '')
                if process_name == whitelist_item_lower or process_name_no_ext == whitelist_item_no_ext:
                    is_whitelisted = True
                    break

            if not is_whitelisted:
                matched_windows.append(window)

        return matched_windows

    def _group_windows(self, windows, selected_before):
        """根据选择状态和可见性分组窗口

        Args:
            windows: 窗口信息列表
            selected_before: 之前选择的窗口句柄集合

        Returns:
            Tuple: (已选择窗口, 未选择可见窗口, 未选择隐藏窗口)
        """
        selected_windows = []
        unselected_visible_windows = []
        unselected_hidden_windows = []

        for window in windows:
            # 检查窗口标题是否包含任何关键字
            is_keyword_match = False
            for keyword in self._keywords:
                if keyword.lower() in window.title.lower():
                    is_keyword_match = True
                    break
            
            if window.hwnd in selected_before or is_keyword_match:
                # 如果之前已选择或标题包含关键字，则添加到已选择列表
                selected_windows.append(window)
                # 确保这个窗口在选中集合中
                self._selected_windows.add(window.hwnd)
            elif window.state == WindowState.HIDDEN:
                unselected_hidden_windows.append(window)
            else:
                unselected_visible_windows.append(window)

        return selected_windows, unselected_visible_windows, unselected_hidden_windows

    def _add_windows_to_tree(self, windows, selected_text, tag, color):
        """添加窗口到树视图

        Args:
            windows: 窗口信息列表
            selected_text: 选择状态文本
            tag: 标签名称
            color: 背景颜色

        Returns:
            int: 添加的窗口数量
        """
        added_count = 0
        for window in windows:
            status = "隐藏" if window.state == WindowState.HIDDEN else "显示"
            logger.debug(f"Adding window with tag '{tag}': {window.title}")
            try:
                # 使用更明显的选择框符号
                checkbox = "✅" if selected_text == "已选择" else "⬜"
                item = self.window_tree.insert("", tk.END, values=(
                    checkbox, status, str(window.hwnd),
                    window.title, window.class_name, str(window.pid)
                ))
                self.window_tree.item(item, tags=(tag,))
                self.window_tree.tag_configure(tag, background=color)
                added_count += 1
            except Exception as e:
                logger.error("Error adding window to tree: %s", str(e))
        return added_count

    def _add_separator(self):
        """添加分割线到树视图"""
        try:
            separator_item = self.window_tree.insert("", tk.END, values=("─", "─", "─", "─", "─", "─"))
            self.window_tree.item(separator_item, tags=("separator",))
            # 使用蓝色背景，更细的分割线
            self.window_tree.tag_configure("separator", background="#0078D7", foreground="white")
        except Exception as e:
            logger.error("Error adding separator to tree: %s", str(e))

    def _update_status(self, status_text):
        """更新状态栏文本

        Args:
            status_text: 状态文本
        """
        if self.status_var:
            self.status_var.set(status_text)

    def hide_selected_windows(self):
        """隐藏选中的窗口"""
        if not self.window_manager:
            return

        count = 0
        for hwnd in self._selected_windows:
            try:
                self.window_manager.hide_window(hwnd)
                count += 1
            except Exception as e:
                logger.error("Failed to hide window %s: %s", hwnd, str(e))

        if self.status_var:
            self.status_var.set("已隐藏 %d 个窗口" % count)

        self.refresh_windows()

    def show_selected_hidden_windows(self):
        """显示选中的隐藏窗口"""
        if not self.window_manager:
            return

        count = 0
        for hwnd in self._selected_windows:
            try:
                window = self.window_manager.get_window(hwnd)
                if window and window.state == WindowState.HIDDEN:
                    self.window_manager.show_window(hwnd)
                    count += 1
            except Exception as e:
                logger.error("Failed to show window %s: %s", hwnd, str(e))

        if self.status_var:
            self.status_var.set("已显示 %d 个窗口" % count)

        self.refresh_windows()

    def hide_keyword_windows(self):
        """隐藏包含关键字的窗口"""
        if not self.window_manager:
            return

        count = 0
        for window in self.window_manager.windows:
            # 检查是否在白名单中
            if self.config and self.config.process_whitelist:
                if window.process_name.lower() in [p.lower() for p in self.config.process_whitelist]:
                    continue

            # 检查关键字
            for keyword in self._keywords:
                if keyword.lower() in window.title.lower():
                    try:
                        if window.state != WindowState.HIDDEN:
                            self.window_manager.hide_window(window.hwnd)
                            count += 1
                    except Exception as e:
                        logger.error("Failed to hide window %s: %s", window.hwnd, str(e))
                    break

        if self.status_var:
            self.status_var.set("已隐藏 %d 个窗口" % count)

        self.refresh_windows()

    def show_all_hidden_windows(self):
        """显示所有隐藏的窗口"""
        if not self.window_manager:
            return

        count = 0
        for window in self.window_manager.windows:
            if window.state == WindowState.HIDDEN:
                try:
                    self.window_manager.show_window(window.hwnd)
                    count += 1
                except Exception as e:
                    logger.error("Failed to show window %s: %s", window.hwnd, str(e))

        if self.status_var:
            self.status_var.set("已显示 %d 个窗口" % count)

        self.refresh_windows()

    def show_and_minimize_all_hidden_windows(self):
        """显示所有隐藏的窗口并立即最小化到任务栏"""
        if not self.window_manager:
            return

        count = 0
        for window in self.window_manager.windows:
            if window.state == WindowState.HIDDEN:
                try:
                    self.window_manager.show_and_minimize_window(window.hwnd)
                    count += 1
                except Exception as e:
                    logger.error("Failed to show and minimize window %s: %s", window.hwnd, str(e))

        if self.status_var:
            self.status_var.set("已显示并最小化 %d 个窗口" % count)

        self.refresh_windows()

    def show_and_minimize_selected_hidden_windows(self):
        """显示选中的隐藏窗口并立即最小化到任务栏"""
        if not self.window_manager:
            return

        count = 0
        for hwnd in self._selected_windows:
            try:
                window = self.window_manager.get_window(hwnd)
                if window and window.state == WindowState.HIDDEN:
                    self.window_manager.show_and_minimize_window(hwnd)
                    count += 1
            except Exception as e:
                logger.error("Failed to show and minimize window %s: %s", hwnd, str(e))

        if self.status_var:
            self.status_var.set("已显示并最小化 %d 个窗口" % count)

        self.refresh_windows()

    def reset_all(self):
        """重置所有设置"""
        self._selected_windows.clear()
        self._keywords.clear()
        self.keyword_listbox.delete(0, tk.END)
        self._save_keywords()
        self._save_selected_windows()
        self.refresh_windows()

        if self.status_var:
            self.status_var.set("已重置")

    def clear_all_keywords(self):
        """清除所有关键字（公共方法，供AppWindow调用）"""
        self._remove_all_keywords()

    def clear_selected_windows(self):
        """清除所有选中的窗口（公共方法，供AppWindow调用）"""
        self._selected_windows.clear()
        self._save_selected_windows()
