# windowmanager/ui.py
"""
窗口管理器 - 主UI模块
整合所有UI组件的主入口
"""
import sys
import os
import logging
import time
import datetime
from typing import Optional

try:
    import tkinter as tk
    from tkinter import ttk, messagebox
    TK_AVAILABLE = True
except ImportError:
    TK_AVAILABLE = False
    tk = ttk = messagebox = None

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
        
        # 设置窗口图标（包括最小化到任务栏显示的图标）
        self._set_window_icon()

        self._is_visible = True
        self.on_exit_callback = None

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

        # 立即初始化时间校准选项卡（作为启动界面）
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

        # 启动心跳检测和自动恢复机制
        self._heartbeat_running = True
        self._last_heartbeat_time = time.time()
        self._heartbeat_check_interval = 60000  # 60秒检查一次
        self._start_heartbeat()

        # 启动自动切换回时间校准选项卡的定时器
        self._auto_switch_interval = 30000  # 30秒
        self._auto_switch_running = True
        self._schedule_auto_switch()

    def _set_window_icon(self):
        """设置窗口图标（包括最小化到任务栏显示的图标）"""
        try:
            # 查找图标文件
            icon_path = None
            # 检查打包环境
            if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                # PyInstaller打包环境
                icon_path = os.path.join(sys._MEIPASS, 'WinHide2.png')
            else:
                # 开发环境，先检查项目根目录
                current_dir = os.getcwd()
                icon_path = os.path.join(current_dir, 'WinHide2.png')
                if not os.path.exists(icon_path):
                    # 如果根目录没有，检查src目录的父目录
                    try:
                        src_dir = os.path.dirname(os.path.abspath(__file__))
                        parent_dir = os.path.dirname(src_dir)
                        icon_path = os.path.join(parent_dir, 'WinHide2.png')
                    except NameError:
                        pass
            
            # 设置窗口图标
            if icon_path and os.path.exists(icon_path):
                try:
                    # 使用PIL将PNG转换为PhotoImage
                    from PIL import Image, ImageTk
                    image = Image.open(icon_path)
                    # 调整图标大小为多个尺寸（16x16, 32x32, 48x48）
                    icon_images = []
                    for size in [16, 32, 48, 64]:
                        resized = image.resize((size, size), Image.Resampling.LANCZOS)
                        icon_images.append(ImageTk.PhotoImage(resized))
                    # 设置窗口图标（使用多个尺寸以适应不同显示）
                    self.root.iconphoto(True, *icon_images)
                    logger.info("Window icon set successfully from: %s", icon_path)
                except Exception as img_error:
                    logger.warning("Failed to set icon with PIL: %s", str(img_error))
                    # 备用方案：直接使用tk.PhotoImage
                    try:
                        icon_image = tk.PhotoImage(file=icon_path)
                        self.root.iconphoto(True, icon_image)
                        logger.info("Window icon set (fallback method) from: %s", icon_path)
                    except Exception as tk_error:
                        logger.warning("Failed to set icon with tk.PhotoImage: %s", str(tk_error))
            else:
                logger.warning("Icon file not found: %s", icon_path)
        except Exception as e:
            logger.error("Error setting window icon: %s", str(e), exc_info=True)

    def _setup_hotkeys(self):
        """设置热键（使用pynput钩子模式）"""
        try:
            self.hotkey_manager.register_hide_hotkey(
                self.main_window.hide_keyword_windows,
                self.config.hide_hotkey
            )
            self.hotkey_manager.register_show_hotkey(
                self.main_window.show_and_minimize_selected_hidden_windows,
                self.config.show_hotkey
            )

            # 启动热键管理器（使用pynput钩子模式）
            if not self.hotkey_manager.start():
                logger.error("Failed to start hotkey manager")
                messagebox.showwarning(
                    "热键功能不可用",
                    "热键功能启动失败，请检查日志获取详细信息。"
                )
            else:
                logger.info("Hotkey manager started successfully with pynput (hook mode)")
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
        
        ttk.Button(right_frame, text="全部重置",
                 command=self._reset_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(right_frame, text="退出",
                 command=self._on_close).pack(side=tk.LEFT, padx=2)

        # 创建选项卡
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 时间校准选项卡（首先创建，作为启动界面）
        self.time_sync_tab_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.time_sync_tab_frame, text="时间校准")
        
        # 立即初始化时间校准选项卡
        try:
            self.time_sync_tab = ui_time_sync.TimeSyncTab(
                self.root,
                config_manager=self.config_manager,
                config=self.config
            )
            self.time_sync_tab.build_time_sync_tab(self.time_sync_tab_frame)
            self._time_sync_tab_initialized = True
            logger.info("Time sync tab initialized successfully on startup")
        except Exception as e:
            logger.error("Failed to initialize time sync tab: %s", str(e), exc_info=True)
            self._time_sync_tab_initialized = True

        # 窗口管理选项卡
        main_tab = ttk.Frame(self.notebook)
        self.notebook.add(main_tab, text="窗口管理")
        self.main_window.build_main_tab(main_tab)

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
            except Exception as e:
                logger.error("Error in tab change event: %s", str(e), exc_info=True)

        self.notebook.bind("<<NotebookTabChanged>>", on_tab_change)
        
        # 状态栏 - 只创建一次
        ttk.Label(self.root, textvariable=self.main_window.status_var,
                 relief=tk.SUNKEN, anchor=tk.W).pack(side=tk.BOTTOM, fill=tk.X)

    def _schedule_auto_switch(self):
        """调度自动切换回时间校准选项卡"""
        if not self._auto_switch_running:
            return
        
        try:
            self._auto_switch_to_time_sync()
        except Exception as e:
            logger.error("Error in auto switch: %s", str(e))
        
        # 继续下一次调度
        if self._auto_switch_running and self.root and self.root.winfo_exists():
            self.root.after(self._auto_switch_interval, self._schedule_auto_switch)

    def _auto_switch_to_time_sync(self):
        """自动切换回时间校准选项卡"""
        try:
            if self.notebook and self.notebook.winfo_exists():
                # 切换到第一个选项卡（时间校准）
                self.notebook.select(0)
                logger.debug("Auto-switched to time sync tab")
        except Exception as e:
            logger.error("Error switching to time sync tab: %s", str(e))
    
    def _start_heartbeat(self):
        """启动心跳检测"""
        if not self._heartbeat_running:
            return
        
        try:
            self._heartbeat_check()
        except Exception as e:
            logger.error("Error in heartbeat: %s", str(e), exc_info=True)
        
        # 继续下一次心跳检测
        if self._heartbeat_running and self.root and self.root.winfo_exists():
            self.root.after(self._heartbeat_check_interval, self._start_heartbeat)

    def _heartbeat_check(self):
        """执行心跳检测和自动恢复"""
        try:
            current_time = time.time()
            self._last_heartbeat_time = current_time
            
            # 检查热键管理器是否还在运行
            if self.hotkey_manager:
                hotkey_running = getattr(self.hotkey_manager, '_running', False)
                if not hotkey_running:
                    logger.warning("Hotkey manager is not running, attempting to restart...")
                    try:
                        # 先尝试停止，确保状态干净
                        try:
                            self.hotkey_manager.stop()
                        except Exception:
                            pass
                        
                        # 重新启动
                        if self.hotkey_manager.start():
                            logger.info("Hotkey manager restarted successfully")
                    except Exception as e:
                        logger.error("Failed to restart hotkey manager: %s", str(e), exc_info=True)
                else:
                    logger.debug("Hotkey manager is running normally")
            
            logger.debug("Heartbeat check completed at %s", datetime.datetime.fromtimestamp(current_time).strftime("%Y-%m-%d %H:%M:%S"))
            
        except Exception as e:
            logger.error("Error in heartbeat check: %s", str(e), exc_info=True)

    def _reset_all(self):
        """全部重置"""
        # 清空关键字
        self.main_window.clear_all_keywords()

        # 清空选中的窗口
        self.main_window.clear_selected_windows()

        # 刷新窗口列表
        self.main_window.refresh_windows()

        self.main_window.status_var.set("已重置")

    def _on_close(self):
        """处理关闭事件"""
        logger.info("Starting application shutdown...")
        
        # 停止自动切换
        self._auto_switch_running = False
        
        # 停止心跳检测
        self._heartbeat_running = False
        
        # 停止热键管理器
        if self.hotkey_manager:
            try:
                logger.info("Stopping hotkey manager...")
                self.hotkey_manager.stop()
            except Exception as e:
                logger.error("Error stopping hotkey manager: %s", str(e))

        # 清理设置选项卡的日志处理器
        if self.settings_tab:
            try:
                self.settings_tab.cleanup()
            except Exception as e:
                logger.error("Error cleaning up settings tab: %s", str(e))

        # 清理时间校准选项卡
        if self.time_sync_tab:
            try:
                self.time_sync_tab = None
                self._time_sync_tab_initialized = False
            except Exception as e:
                logger.error("Error cleaning up time sync tab: %s", str(e))

        # 停止窗口管理器
        if self.window_manager:
            try:
                logger.info("Stopping window manager...")
                self.window_manager.stop()
            except Exception as e:
                logger.error("Error stopping window manager: %s", str(e))

        # 保存配置
        if self.config_manager:
            try:
                logger.info("Saving config...")
                self.config_manager.save(self.config)
            except Exception as e:
                logger.warning("Error saving config: %s", str(e))

        # 销毁主窗口
        try:
            if self.root and self.root.winfo_exists():
                logger.info("Destroying main window...")
                self.root.destroy()
        except Exception as e:
            logger.warning("Error destroying root window: %s", str(e), exc_info=True)

        # 调用退出回调
        if self.on_exit_callback:
            try:
                self.on_exit_callback()
            except Exception as e:
                logger.warning("Error calling exit callback: %s", str(e))
        
        logger.info("Application shutdown completed")
        
        # 确保进程真正退出
        try:
            import os
            import sys
            # 延迟一点，让清理工作完成
            time.sleep(0.3)
            # 强制退出
            os._exit(0)
        except Exception as e:
            logger.error("Error during force exit: %s", str(e))

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
