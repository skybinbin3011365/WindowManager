# windowmanager/ui_main.py
"""
窗口管理器 - 主界面模块 (PySide6 版本)
精简后的主类，通过 Mixin 组合各个功能模块

依赖关系：
├── window_table.py      - WindowTableWidget 表格组件（独立）
├── window_thread.py      - WindowRefreshThread 后台刷新线程（独立）
├── window_keywords.py    - KeywordMixin 关键字管理
├── window_operations.py  - WindowOperationsMixin 窗口隐藏/显示
├── window_switch.py      - SwitchMixin 切换窗口功能
├── config_handler.py     - ConfigHandlerMixin 配置管理
└── window_manager_ui.py  - WindowManagerUIMixin UI布局与更新
"""

import logging
import threading
from typing import Optional, Set

from PySide6.QtWidgets import QWidget, QVBoxLayout, QMessageBox
from PySide6.QtCore import Qt, QTimer, Signal

from window_base import WindowInfo, WindowState
from core import SafeWindowsAPI
from manager import WindowManager
from config import ConfigManager, Config
from constants import UIMainConstants

from window_table import WindowTableWidget
from window_thread import WindowRefreshThread
from window_keywords import KeywordMixin
from main_window_ops import WindowOperationsMixin
from window_switch import SwitchMixin
from config_handler import ConfigHandlerMixin
from window_manager_ui import WindowManagerUIMixin

logger = logging.getLogger(__name__)


class MainWindowTab(
    WindowManagerUIMixin,
    KeywordMixin,
    WindowOperationsMixin,
    SwitchMixin,
    ConfigHandlerMixin,
    QWidget,
):
    """主窗口选项卡 - PySide6版本

    通过多重继承组合各功能模块：
    - WindowManagerUIMixin: UI 布局与表格更新
    - KeywordMixin: 关键字管理
    - WindowOperationsMixin: 窗口隐藏/显示操作
    - SwitchMixin: 切换窗口管理
    - ConfigHandlerMixin: 配置保存/加载
    """

    # 定义信号
    status_updated = Signal(str)  # 状态栏更新信号
    request_refresh = Signal()  # 请求在主线程刷新窗口列表
    request_save_hidden_windows = Signal()  # 请求在主线程保存隐藏窗口列表

    def __init__(
        self,
        window_manager: Optional[WindowManager] = None,
        config_manager: Optional[ConfigManager] = None,
        config: Optional[Config] = None,
    ) -> None:
        """初始化主窗口选项卡"""
        super().__init__()

        self.window_manager = window_manager
        self.config_manager = config_manager
        self.config = config

        # 选中的窗口集合（持久化存储，存储句柄）
        self._selected_windows: Set[int] = set()
        # 临时忽略的窗口集合（非持久化，点击刷新后会重新显示）
        self._ignored_windows: Set[int] = set()
        # 标记是否已从配置加载选中窗口
        self._selected_windows_loaded_from_config: bool = False
        # 线程锁，保护共享数据访问
        self._lock = threading.RLock()

        # 初始化UI
        self._init_ui()

        # 线程安全：后台线程只发信号，主线程执行 Qt/配置相关操作
        self.request_refresh.connect(self.refresh_windows)
        self.request_save_hidden_windows.connect(self._save_hidden_windows)

        # 注册为配置观察者
        if self.config_manager:
            self.config_manager.register_observer(self)

        # 延迟初始化
        QTimer.singleShot(500, self._restore_hidden_windows)
        QTimer.singleShot(600, self._load_switch_processes_from_config)

        # 设置定时刷新
        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self.refresh_windows)
        refresh_interval = (
            getattr(self.config, "auto_refresh_interval", UIMainConstants.DEFAULT_AUTO_REFRESH_INTERVAL)
            * 1000
        )
        self._refresh_timer.start(int(refresh_interval))

        # 初始化窗口刷新线程
        self._refresh_thread = None

        QTimer.singleShot(UIMainConstants.INITIAL_REFRESH_DELAY, self.refresh_windows)
        QTimer.singleShot(1500, self._auto_select_keyword_windows)

    def closeEvent(self, event) -> None:
        """窗口关闭事件 - 清理资源"""
        if self.config_manager:
            self.config_manager.unregister_observer(self)

        if hasattr(self, "_refresh_timer") and self._refresh_timer:
            self._refresh_timer.stop()

        if hasattr(self, "_refresh_thread") and self._refresh_thread:
            if self._refresh_thread.isRunning():
                self._refresh_thread.requestInterruption()
                if not self._refresh_thread.wait(1000):
                    logger.warning("窗口刷新线程未能及时停止，强制终止")
            self._refresh_thread.deleteLater()
            self._refresh_thread = None

        super().closeEvent(event)

    def update(self, new_config: Config) -> None:
        """配置变更回调 - 观察者模式实现"""
        logger.debug("收到配置更新通知，正在更新 UI...")

        self.config = new_config

        if hasattr(self, "_refresh_timer") and self._refresh_timer:
            refresh_interval = (
                getattr(self.config, "auto_refresh_interval", UIMainConstants.DEFAULT_AUTO_REFRESH_INTERVAL)
                * 1000
            )
            self._refresh_timer.setInterval(int(refresh_interval))

        self.status_updated.emit("配置已更新")

    def _restore_hidden_windows(self) -> None:
        """启动时设置隐藏窗口列表到窗口管理器"""
        if not self.window_manager or not self.config:
            return
        if not getattr(self.window_manager, "is_running", False):
            logger.warning("窗口管理器未运行，跳过设置隐藏窗口列表")
            return

        target_windows = getattr(self.config, "target_windows", [])
        hidden_windows_info = [
            w for w in target_windows
            if isinstance(w, dict) and w.get("state") == "hidden"
        ]

        if not hidden_windows_info:
            return

        if not hasattr(self.window_manager, "set_software_hidden_windows"):
            return

        try:
            import win32gui
        except ImportError:
            logger.warning("win32gui 不可用，无法恢复隐藏窗口")
            return

        try:
            import psutil
            PSUTIL_AVAILABLE = True
        except ImportError:
            PSUTIL_AVAILABLE = False
            psutil = None

        hwnds = []
        restored_count = 0
        fallback_count = 0

        for window_info in hidden_windows_info:
            saved_hwnd = window_info.get("hwnd")
            process_name = window_info.get("process_name", "")
            title = window_info.get("title", "")

            if saved_hwnd and SafeWindowsAPI.is_window(saved_hwnd):
                try:
                    curr_title = SafeWindowsAPI.get_window_text(saved_hwnd).strip()
                    if curr_title == title:
                        hwnds.append(saved_hwnd)
                        restored_count += 1

                        win_info = self.window_manager.get_window(saved_hwnd)
                        if not win_info:
                            _, pid = SafeWindowsAPI.get_window_thread_process_id(saved_hwnd)
                            win_info = WindowInfo(
                                hwnd=saved_hwnd, title=title, process_name=process_name,
                                is_visible=False, is_taskbar=False,
                                state=WindowState.HIDDEN, pid=pid,
                            )
                        else:
                            win_info.state = WindowState.HIDDEN
                            win_info.is_visible = False
                        self.window_manager._hidden_windows[saved_hwnd] = win_info
                        continue
                except Exception:
                    pass

            if process_name and PSUTIL_AVAILABLE and psutil is not None:
                try:
                    for proc in psutil.process_iter(["pid", "name"]):
                        try:
                            if proc.info["name"].lower() == process_name.lower():
                                pid = proc.info["pid"]

                                def callback(hwnd, result):
                                    try:
                                        if not SafeWindowsAPI.is_window(hwnd):
                                            return True
                                        _, curr_pid = SafeWindowsAPI.get_window_thread_process_id(hwnd)
                                        if curr_pid != pid:
                                            return True
                                        curr_title = SafeWindowsAPI.get_window_text(hwnd).strip()
                                        if curr_title == title:
                                            result.append(hwnd)
                                    except Exception:
                                        pass
                                    return True

                                windows = []
                                win32gui.EnumWindows(callback, windows)
                                for hwnd in windows:
                                    if hwnd not in hwnds:
                                        hwnds.append(hwnd)
                                        fallback_count += 1

                                        win_info = self.window_manager.get_window(hwnd)
                                        if not win_info:
                                            win_info = WindowInfo(
                                                hwnd=hwnd, title=title, process_name=process_name,
                                                is_visible=False, is_taskbar=False,
                                                state=WindowState.HIDDEN, pid=pid,
                                            )
                                        else:
                                            win_info.state = WindowState.HIDDEN
                                            win_info.is_visible = False
                                        self.window_manager._hidden_windows[hwnd] = win_info
                        except Exception:
                            continue
                except Exception:
                    pass

        if hwnds:
            self.window_manager.set_software_hidden_windows(hwnds)

    def _on_window_double_clicked(self, hwnd: int) -> None:
        """处理窗口双击事件"""
        if self.window_manager:
            try:
                self.window_manager.show_window(hwnd)
            except Exception as e:
                logger.error("显示窗口 %d 失败: %s", hwnd, str(e))

    def refresh_windows(self) -> None:
        """刷新窗口列表 - 三栏布局版本"""
        if not self.window_manager:
            return

        if not self._selected_windows_loaded_from_config:
            self._load_selected_windows_from_config()
            self._selected_windows_loaded_from_config = True

        self._ignored_windows.clear()

        if self._refresh_thread and self._refresh_thread.isRunning():
            self._refresh_thread.requestInterruption()

        process_whitelist = getattr(self.config, "process_whitelist", []) if self.config else []
        keywords = getattr(self.config, "keywords", []) if self.config else []

        self._refresh_thread = WindowRefreshThread(
            window_manager=self.window_manager,
            selected_windows=self._selected_windows,
            ignored_windows=self._ignored_windows,
            process_whitelist=process_whitelist,
            keywords=keywords,
            config=self.config,
        )
        self._refresh_thread.refresh_finished.connect(self._on_refresh_finished)
        self._refresh_thread.auto_selected.connect(self._on_auto_selected)
        self._refresh_thread.hwnd_updated.connect(self._on_hwnd_updated)
        self._refresh_thread.start()

        from PySide6.QtCore import QDateTime
        timestamp = QDateTime.currentDateTime().toString("HH:mm:ss")
        self.status_updated.emit(f"刷新中... {timestamp}")

    def cleanup(self) -> None:
        """清理资源"""
        if hasattr(self, "_refresh_timer"):
            self._refresh_timer.stop()
