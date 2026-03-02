# windowmanager/ui.py
"""
窗口管理器 - 主UI模块
整合所有UI组件的主入口
"""
import sys
import os
import logging
import threading
import time
from typing import Optional

try:
    import tkinter as tk
    from tkinter import ttk, messagebox
    TK_AVAILABLE = True
except ImportError:
    TK_AVAILABLE = False
    tk = ttk = messagebox = None

try:
    from pystray import Icon, Menu, MenuItem
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False
    Icon = Menu = MenuItem = Image = ImageDraw = None

from .config import ConfigManager, Config
from . import hotkey_manager
HotkeyManager = hotkey_manager.HotkeyManager
from .constants import WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT, APP_TITLE

from . import ui_main
from . import ui_time_sync
from . import ui_settings
from . import ui_about

logger = logging.getLogger(__name__)


class AppWindow:
    """主窗口类 - 整合所有UI组件"""

    def __init__(self, window_manager=None):
        """初始化主窗口

        Args:
            window_manager: 窗口管理器实例
        """
        if not TK_AVAILABLE:
            raise RuntimeError("Tkinter is required")

        self.window_manager = window_manager

        # 创建主窗口
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry(f"{WINDOW_DEFAULT_WIDTH}x{WINDOW_DEFAULT_HEIGHT}")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # 捕获最小化事件
        self.root.bind("<Unmap>", self._on_minimize)

        self._is_visible = True
        self._minimize_to_tray = False  # 是否允许最小化到托盘
        self.on_exit_callback = None
        self._tray_icon = None

        # 初始化配置管理器
        self.config_manager = ConfigManager()
        try:
            self.config = self.config_manager.load()
        except Exception as e:
            logger.error("Failed to load config: %s", str(e), exc_info=True)
            # 使用默认配置
            self.config = Config()
            # 尝试保存默认配置
            try:
                self.config_manager.save(self.config)
                logger.info("Saved default config")
            except Exception as save_error:
                logger.error("Failed to save default config: %s", str(save_error))

        # 初始化热键管理器
        self.hotkey_manager = HotkeyManager()

        # 初始化各个UI模块
        self.main_window = ui_main.MainWindow(
            self.root,
            window_manager=window_manager,
            config_manager=self.config_manager,
            config=self.config,
            hotkey_manager=self.hotkey_manager
        )
        self.main_window.status_var = tk.StringVar(value="就绪")

        # 延迟初始化时间校准选项卡，避免启动时出现问题
        self.time_sync_tab = None
        self._time_sync_tab_initialized = False

        self.settings_tab = ui_settings.SettingsTab(
            self.root,
            config_manager=self.config_manager,
            config=self.config,
            hotkey_manager=self.hotkey_manager
        )

        self.about_tab = ui_about.AboutTab(self.root)

        # 构建UI
        self._build_ui()

        # 启动窗口管理器
        if window_manager:
            window_manager.start()
            self.main_window.refresh_windows()

        # 设置热键
        self._setup_hotkeys()

        # 程序启动时创建托盘图标
        if TRAY_AVAILABLE:
            self._create_tray_icon()
        
        # 延迟30秒自动初始化时间校准选项卡
        self._init_time_sync_scheduled = False
        self.root.after(30000, self._auto_init_time_sync_tab)

    def _setup_hotkeys(self):
        """设置热键"""
        try:
            self.hotkey_manager.register_hide_hotkey(
                self.main_window.hide_keyword_windows,
                self.config.hide_hotkey
            )
            self.hotkey_manager.register_show_hotkey(
                self.main_window.show_and_minimize_selected_hidden_windows,
                self.config.show_hotkey
            )

            # 尝试启动热键管理器
            if not self.hotkey_manager.start():
                logger.warning("Hook mode failed, falling back to polling mode")
                # 切换到轮询模式
                self.hotkey_manager._use_hook = False
                # 重新启动
                if not self.hotkey_manager.start():
                    logger.error("Failed to start hotkey manager in polling mode")
                    messagebox.showwarning(
                        "热键功能不可用",
                        "热键功能启动失败，请检查日志获取详细信息。"
                    )
        except Exception as e:
            logger.error("Failed to setup hotkeys: %s", str(e), exc_info=True)
            messagebox.showerror(
                "热键设置失败",
                f"设置热键时出错: {str(e)}\n热键功能将不可用。"
            )

    def _build_ui(self):
        """构建主界面"""
        # 控制按钮区域 - 分为左右两部分
        control_frame = ttk.Frame(self.root)
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        # 左侧按钮
        left_frame = ttk.Frame(control_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Button(left_frame, text="刷新窗口",
                 command=self.main_window.refresh_windows).pack(side=tk.LEFT, padx=2)
        ttk.Button(left_frame, text="隐藏窗口",
                 command=self.main_window.hide_selected_windows).pack(side=tk.LEFT, padx=2)
        ttk.Button(left_frame, text="显示窗口",
                 command=self.main_window.show_selected_hidden_windows).pack(side=tk.LEFT, padx=2)

        # 右侧按钮 - 全部放在右下角
        right_frame = ttk.Frame(control_frame)
        right_frame.pack(side=tk.RIGHT)
        
        ttk.Button(right_frame, text="隐藏到任务栏",
                 command=self._hide_to_tray).pack(side=tk.LEFT, padx=2)
        ttk.Button(right_frame, text="全部重置",
                 command=self._reset_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(right_frame, text="退出",
                 command=self._on_close).pack(side=tk.LEFT, padx=2)

        # 创建选项卡
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 窗口管理选项卡
        main_tab = ttk.Frame(self.notebook)
        self.notebook.add(main_tab, text="窗口管理")
        self.main_window.build_main_tab(main_tab)

        # 时间校准选项卡 - 延迟初始化
        self.time_sync_tab_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.time_sync_tab_frame, text="时间校准")

        # 设置选项卡
        settings_tab = ttk.Frame(self.notebook)
        self.notebook.add(settings_tab, text="设置")
        self.settings_tab.build_settings_tab(settings_tab)

        # 关于选项卡
        about_tab = ttk.Frame(self.notebook)
        self.notebook.add(about_tab, text="关于")
        self.about_tab.build_about_tab(about_tab)

        # 绑定选项卡切换事件
        def on_tab_change(event):
            """处理选项卡切换事件"""
            try:
                selected_tab = event.widget.select()
                tab_text = event.widget.tab(selected_tab, "text")
                logger.info("Tab changed to: %s", tab_text)

                # 如果切换到时间校准选项卡且未初始化，则初始化
                if tab_text == "时间校准":
                    if self._time_sync_tab_initialized:
                        logger.debug("Time sync tab already initialized, skipping")
                        return

                    if self.time_sync_tab is not None:
                        logger.warning("Time sync tab object already exists, skipping initialization")
                        return

                    try:
                        self.time_sync_tab = ui_time_sync.TimeSyncTab(
                            self.root,
                            config_manager=self.config_manager,
                            config=self.config
                        )
                        self.time_sync_tab.build_time_sync_tab(self.time_sync_tab_frame)
                        self._time_sync_tab_initialized = True
                        logger.info("Time sync tab initialized successfully")
                    except Exception as e:
                        logger.error("Failed to initialize time sync tab: %s", str(e), exc_info=True)
                        messagebox.showerror("错误", f"时间校准选项卡初始化失败: {str(e)}")
                        # 标记为已初始化，避免重复尝试
                        self._time_sync_tab_initialized = True
            except Exception as e:
                logger.error("Error in tab change event: %s", str(e), exc_info=True)
                # 不要调用messagebox，避免可能的递归问题

        self.notebook.bind("<<NotebookTabChanged>>", on_tab_change)
    
    def _auto_init_time_sync_tab(self):
        """自动初始化时间校准选项卡（延迟30秒执行）"""
        try:
            # 如果已经初始化过了，跳过
            if self._time_sync_tab_initialized:
                logger.debug("Time sync tab already initialized, skipping auto-init")
                return
            
            if self.time_sync_tab is not None:
                logger.warning("Time sync tab object already exists, skipping auto-init")
                return
            
            logger.info("Auto-initializing time sync tab (30 seconds after startup)")
            
            try:
                self.time_sync_tab = ui_time_sync.TimeSyncTab(
                    self.root,
                    config_manager=self.config_manager,
                    config=self.config
                )
                self.time_sync_tab.build_time_sync_tab(self.time_sync_tab_frame)
                self._time_sync_tab_initialized = True
                logger.info("Time sync tab auto-initialized successfully")
            except Exception as e:
                logger.error("Failed to auto-initialize time sync tab: %s", str(e), exc_info=True)
                # 标记为已初始化，避免重复尝试
                self._time_sync_tab_initialized = True
        except Exception as e:
            logger.error("Error in auto_init_time_sync_tab: %s", str(e), exc_info=True)

        # 状态栏
        ttk.Label(self.root, textvariable=self.main_window.status_var,
                 relief=tk.SUNKEN, anchor=tk.W).pack(side=tk.BOTTOM, fill=tk.X)

    def _reset_all(self):
        """全部重置"""
        # 清空关键字
        self.main_window.clear_all_keywords()

        # 清空选中的窗口
        self.main_window.clear_selected_windows()

        # 刷新窗口列表
        self.main_window.refresh_windows()

        self.main_window.status_var.set("已重置")

    def _hide_to_tray(self):
        """隐藏到系统托盘"""
        if not TRAY_AVAILABLE:
            messagebox.showerror("错误", "系统托盘功能不可用")
            return

        self._is_visible = False
        self._minimize_to_tray = True  # 标记允许最小化到托盘
        self.root.withdraw()

        # 创建托盘图标
        if not self._tray_icon:
            self._create_tray_icon()

        logger.info("Window hidden to tray")

    def _create_tray_icon(self):
        """创建系统托盘图标"""
        try:
            # 尝试加载WinHide.png图标
            icon_path = None
            # 检查打包环境
            if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                # PyInstaller打包环境
                icon_path = os.path.join(sys._MEIPASS, 'WinHide.png')
            else:
                # 开发环境，先检查项目根目录
                current_dir = os.getcwd()
                icon_path = os.path.join(current_dir, 'WinHide.png')
                if not os.path.exists(icon_path):
                    # 如果根目录没有，检查src目录的父目录
                    try:
                        src_dir = os.path.dirname(os.path.abspath(__file__))
                        parent_dir = os.path.dirname(src_dir)
                        icon_path = os.path.join(parent_dir, 'WinHide.png')
                    except NameError:
                        pass
            
            # 尝试加载图标
            image = None
            if icon_path and os.path.exists(icon_path):
                try:
                    image = Image.open(icon_path)
                    # 调整图标大小
                    if image.size != (64, 64):
                        image = image.resize((64, 64), Image.Resampling.LANCZOS)
                    logger.info("Loaded custom icon from: %s", icon_path)
                except Exception as img_error:
                    logger.warning("Failed to load custom icon: %s", str(img_error))
            
            # 如果加载失败，使用默认图标
            if image is None:
                logger.warning("Using default icon")
                image = Image.new('RGB', (64, 64), color=(0, 0, 0))
                dc = ImageDraw.Draw(image)
                dc.rectangle((16, 16, 48, 48), fill=(255, 255, 255))

            # 创建菜单项
            menu = Menu(
                MenuItem('显示', self._show_from_tray),
                MenuItem('退出', lambda _icon, _item: self._on_close())
            )

            # 创建托盘图标
            self._tray_icon = Icon(
                'window_manager',
                image,
                title='窗口管理器',
                menu=menu
            )

            # 设置双击事件
            self._tray_icon.default_action = self._show_from_tray

            self._tray_icon.run_detached()
            logger.info("Tray icon created successfully")
        except Exception as e:
            logger.error("Failed to create tray icon: %s", str(e), exc_info=True)
            # 如果托盘图标创建失败，显示窗口
            self._show_from_tray()
            # 显示警告信息
            try:
                messagebox.showwarning(
                    "系统托盘不可用",
                    "系统托盘功能不可用，窗口将无法隐藏到托盘。\n"
                    "请确保已安装pystray和Pillow库。\n"
                    "运行: pip install pystray Pillow"
                )
            except Exception as msg_error:
                logger.error("Failed to show warning message: %s", str(msg_error))

    def _show_from_tray(self, icon=None, item=None):
        """从系统托盘显示窗口

        Args:
            icon: 托盘图标对象
            item: 菜单项对象
        """
        self._is_visible = True
        self.root.deiconify()
        self.root.lift()

    def _on_minimize(self, event):
        """处理最小化事件

        Args:
            event: 事件对象
        """
        # 只有当明确允许最小化到托盘时才隐藏
        # 这样可以避免切换选项卡时意外隐藏窗口
        if self._is_visible and self._minimize_to_tray:
            self._hide_to_tray()

    def _on_close(self):
        """处理关闭事件"""
        # 停止热键管理器
        if self.hotkey_manager:
            self.hotkey_manager.stop()

        # 清理设置选项卡的日志处理器
        if self.settings_tab:
            self.settings_tab.cleanup()

        # 清理时间校准选项卡
        if self.time_sync_tab:
            self.time_sync_tab = None
            self._time_sync_tab_initialized = False

        # 隐藏托盘图标
        if self._tray_icon:
            self._tray_icon.stop()
            self._tray_icon = None

        # 停止窗口管理器
        if self.window_manager:
            self.window_manager.stop()

        # 保存配置
        if self.config_manager:
            self.config_manager.save(self.config)

        # 销毁主窗口
        self.root.destroy()

        # 调用退出回调
        if self.on_exit_callback:
            self.on_exit_callback()

    def run(self):
        """运行主窗口"""
        self.root.mainloop()


def create_main_window(window_manager=None):
    """创建主窗口的工厂函数

    Args:
        window_manager: 窗口管理器实例

    Returns:
        AppWindow: 主窗口实例
    """
    return AppWindow(window_manager)
