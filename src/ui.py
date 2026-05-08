# windowmanager/ui.py
"""
窗口管理器 - 主UI模块 (PySide6版本)
整合所有UI组件的主入口
"""

import os
import logging
import threading
import time
from typing import Optional
from queue import Queue, Empty

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTabWidget,
    QLabel,
    QSystemTrayIcon,
    QMenu,
)
from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QIcon, QAction

from config import ConfigManager, Config
from hotkey_manager import HotkeyManager
from manager import WindowManager
from time_sync import TimeSyncTool
from constants import (
    AppConstants,
    UIConstants,
    HotkeyConstants,
    UICommonConstants,
    NTPConstants,
    PathConstants,
)
from utils import get_resource_path
from theme import theme

import ui_main
import ui_settings
import ui_about

# 常量定义（在 constants.py 中统一管理）

logger = logging.getLogger(__name__)


class AppWindow(QMainWindow):
    """主窗口类 - PySide6版本"""

    # 定义热键回调信号（确保在主线程执行）
    hide_hotkey_triggered = Signal()
    show_hotkey_triggered = Signal()
    switch_hotkey_triggered = Signal()

    # 定义日志更新信号
    log_updated = Signal(str)
    # 请求在主线程刷新窗口列表（后台线程安全触发）
    request_refresh_windows = Signal()

    def __init__(self, window_manager: Optional[WindowManager] = None) -> None:
        """初始化主窗口

        Args:
            window_manager: 窗口管理器实例
        """
        super().__init__()

        logger.info("开始初始化主窗口")
        self.window_manager = window_manager
        self._is_visible: bool = True

        # 初始化基础组件
        self._init_basic_components()

        # 初始化窗口属性
        self._init_window_properties()

        # 创建 UI 布局
        self._create_ui_layout()

        # 初始化各个选项卡
        self._init_tabs()

        # 初始化时间同步工具
        self._init_time_sync_tool()

        # 显示窗口
        self._show_window()

        # 启动窗口管理器
        self._start_window_manager()

        # 初始化热键和托盘
        self._init_hotkeys_and_tray()

        # 初始化日志处理
        self._init_logging()

        # 启动心跳检测
        self._start_heartbeat_check()

        logger.info("主窗口初始化完成")

    def _init_basic_components(self):
        """初始化基础组件"""
        # 初始化配置管理器
        self.config_manager = ConfigManager.get_instance()
        try:
            self.config = self.config_manager.load()
        except Exception as e:
            logger.error("加载配置失败: %s", str(e), exc_info=True)
            self.config = Config()

        # 初始化热键管理器 - 使用pynput实现全局热键
        self.hotkey_manager: HotkeyManager = HotkeyManager()

        # 托盘图标
        self.tray_icon: Optional[QSystemTrayIcon] = None

        # 心跳检测定时器
        self._heartbeat_timer: QTimer = QTimer()

        # 日志队列和定时器
        self._log_queue: Queue = Queue()
        self._log_timer: QTimer = QTimer()

        # 时间同步工具
        self.time_sync_tool = None

    def _init_window_properties(self):
        """初始化窗口属性"""
        # 设置窗口属性
        self.setWindowTitle(AppConstants.APP_TITLE)
        self.setMinimumSize(
            UIConstants.WINDOW_DEFAULT_WIDTH,
            UIConstants.WINDOW_DEFAULT_HEIGHT,
        )
        self.resize(
            UIConstants.WINDOW_DEFAULT_WIDTH,
            UIConstants.WINDOW_DEFAULT_HEIGHT,
        )

        # 设置主窗口样式
        self.setStyleSheet(theme.get_global_stylesheet())

        # 设置窗口图标
        self._set_window_icon()

    def _create_ui_layout(self):
        """创建 UI 布局"""
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # 创建控制按钮区域
        control_frame = QWidget()
        control_layout = QHBoxLayout(control_frame)
        control_layout.setContentsMargins(0, 0, 0, 0)

        control_layout.addStretch()

        main_layout.addWidget(control_frame)

        # 创建选项卡
        self.notebook = QTabWidget()
        main_layout.addWidget(self.notebook)

        # 添加底部按钮区域
        bottom_frame = QWidget()
        bottom_layout = QHBoxLayout(bottom_frame)
        bottom_layout.setContentsMargins(0, 0, 0, 0)

        bottom_layout.addStretch()

        # 隐藏托盘按钮
        self.hide_to_tray_btn = QPushButton("隐藏托盘")
        self.hide_to_tray_btn.clicked.connect(self.hide_to_tray)
        bottom_layout.addWidget(self.hide_to_tray_btn)

        # 退出按钮
        self.exit_btn = QPushButton("退出")
        self.exit_btn.clicked.connect(self._on_close)
        bottom_layout.addWidget(self.exit_btn)

        main_layout.addWidget(bottom_frame)

        # 状态栏
        self.status_label = QLabel("就绪")
        self.statusBar().addPermanentWidget(self.status_label)

    def _init_tabs(self):
        """初始化各个选项卡"""
        # 初始化各个UI模块
        self.main_window = ui_main.MainWindowTab(
            window_manager=self.window_manager,
            config_manager=self.config_manager,
            config=self.config,
        )
        # 连接状态栏更新信号
        self.main_window.status_updated.connect(self._on_status_update)
        self.notebook.addTab(self.main_window, "窗口管理")

        self.settings_tab = ui_settings.SettingsTab(
            config_manager=self.config_manager,
            config=self.config,
            hotkey_manager=self.hotkey_manager,
            parent_window=self,
            window_manager=self.window_manager,
        )
        self.notebook.addTab(self.settings_tab, "设置")
        # 连接设置选项卡的状态更新信号
        self.settings_tab.status_update.connect(self._on_status_update)

        self.about_tab = ui_about.AboutTab(config=self.config)
        self.notebook.addTab(self.about_tab, "关于")

        # 线程安全：后台线程只发信号，主线程执行刷新
        self.request_refresh_windows.connect(self.main_window.refresh_windows)

        # 连接设置选项卡的热键更改信号
        if hasattr(self, "settings_tab") and self.settings_tab:
            self.settings_tab.hotkeys_changed.connect(self._register_hotkeys)

        # 连接热键回调信号（确保在主线程执行）
        self.hide_hotkey_triggered.connect(self.main_window.hide_selected_windows)
        self.show_hotkey_triggered.connect(
            self.main_window.show_and_minimize_selected_hidden_windows
        )
        self.switch_hotkey_triggered.connect(self.main_window.switch_all_processes_to_foreground)

    def _init_time_sync_tool(self):
        """初始化时间同步工具"""
        # 初始化时间同步工具
        self.time_sync_tool = TimeSyncTool(
            NTPConstants.DEFAULT_NTP_SERVERS.copy(),
            enable_log=self.about_tab.get_ntp_log_enabled(),
        )

        # 将时间同步工具传递给设置选项卡
        self.settings_tab.set_time_sync_tool(self.time_sync_tool)

    def _show_window(self):
        """显示窗口"""
        # 立即显示窗口
        logger.info("显示主窗口")
        self.show()
        self.activateWindow()
        self.raise_()
        logger.info("主窗口显示状态: %s", self.isVisible())

    def _start_window_manager(self):
        """启动窗口管理器"""
        # 启动窗口管理器
        if self.window_manager:
            # 在后台线程中启动窗口管理器，避免阻塞主线程
            def start_window_manager():
                try:
                    self.window_manager.start()
                    # 延迟刷新窗口列表，确保 UI 已经完全初始化
                    time.sleep(0.5)
                    # 通过信号让主线程刷新窗口列表
                    self.request_refresh_windows.emit()
                except Exception as e:
                    logger.error("启动窗口管理器失败: %s", str(e), exc_info=True)

            threading.Thread(target=start_window_manager, daemon=True).start()

    def _init_hotkeys_and_tray(self):
        """初始化热键和托盘"""
        # 设置热键
        self._setup_hotkeys()

        # 初始化系统托盘
        self._init_tray()

        # 注册热键回调
        self._register_hotkeys()

        # 启动热键管理器
        if not self.hotkey_manager.start():
            logger.error("热键管理器启动失败，请检查pynput库是否安装")
        else:
            logger.info("热键管理器已启动")

    def _init_logging(self):
        """初始化日志处理"""
        # 连接日志更新信号
        self.log_updated.connect(self._on_log_updated)

        # 设置日志定时器（每100ms检查一次队列）
        self._log_timer.timeout.connect(self._process_log_queue)
        self._log_timer.start(UICommonConstants.LOG_TIMER_INTERVAL_MS)

        # 设置日志处理器
        self._setup_log_handler()

    def _start_heartbeat_check(self):
        """启动心跳检测"""
        # 心跳检测定时器
        self._heartbeat_timer.timeout.connect(self._heartbeat_check)
        self._heartbeat_timer.start(HotkeyConstants.HOTKEY_HEALTH_CHECK_INTERVAL)

    def _setup_hotkeys(self) -> None:
        """设置热键（热键已在 __init__ 中注册，此方法用于刷新）"""
        self._register_hotkeys()

    def _register_hotkeys(self) -> None:
        """注册热键回调"""
        if self.hotkey_manager and self.config:
            try:
                # 从配置中获取当前热键设置
                hide_hotkey = self.config.hide_hotkey
                show_hotkey = self.config.show_hotkey
                switch_hotkey = self.config.switch_hotkey

                # 注册热键回调
                self.hotkey_manager.register_hide_hotkey(
                    lambda: self.hide_hotkey_triggered.emit(), hide_hotkey
                )
                self.hotkey_manager.register_show_hotkey(
                    lambda: self.show_hotkey_triggered.emit(), show_hotkey
                )
                self.hotkey_manager.register_switch_hotkey(
                    lambda: self.switch_hotkey_triggered.emit(), switch_hotkey
                )

                logger.info(
                    "热键已更新：隐藏=%s，显示=%s，切换=%s", hide_hotkey, show_hotkey, switch_hotkey
                )
            except Exception as e:
                logger.error("注册热键失败: %s", str(e))

    def _heartbeat_check(self) -> None:
        """热键心跳检测（检查热键是否仍然有效）"""
        if self.hotkey_manager:
            self.hotkey_manager.check_health()

    def _set_window_icon(self) -> None:
        """设置窗口图标"""
        icon_candidates = [get_resource_path(icon) for icon in PathConstants.ICON_CANDIDATES]

        for icon_path in icon_candidates:
            if icon_path and os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
                logger.info("窗口图标已设置: %s", icon_path)
                return

        logger.warning("未找到图标文件")

    def _init_tray(self) -> None:
        """初始化系统托盘"""
        self.tray_icon = QSystemTrayIcon(self)

        # 设置托盘图标
        icon_candidates = [get_resource_path(icon) for icon in PathConstants.ICON_CANDIDATES]

        for icon_path in icon_candidates:
            if icon_path and os.path.exists(icon_path):
                self.tray_icon.setIcon(QIcon(icon_path))
                break

        self.tray_icon.setToolTip(AppConstants.APP_TITLE)

        # 创建托盘菜单
        tray_menu = QMenu()

        show_action = QAction("显示主窗口", self)
        show_action.triggered.connect(self.show_and_activate)
        tray_menu.addAction(show_action)

        tray_menu.addSeparator()

        exit_action = QAction("退出程序", self)
        exit_action.triggered.connect(self._on_close)
        tray_menu.addAction(exit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

        logger.info("系统托盘初始化完成")

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """托盘图标激活事件

        Args:
            reason: 激活原因
        """
        if reason == QSystemTrayIcon.DoubleClick or reason == QSystemTrayIcon.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show_and_activate()

    def show_and_activate(self) -> None:
        """显示并激活窗口"""
        self.show()
        self.activateWindow()
        self.raise_()

    def hide_to_tray(self) -> None:
        """隐藏到托盘"""
        self.hide()
        if self.tray_icon:
            self.tray_icon.showMessage(
                AppConstants.APP_TITLE,
                "程序已最小化到托盘，点击托盘图标恢复窗口",
                QSystemTrayIcon.Information,
                UICommonConstants.TRAY_MESSAGE_DURATION,
            )

    def _on_status_update(self, message: str) -> None:
        """处理设置选项卡的状态更新

        Args:
            message: 状态消息（已包含时间戳）
        """
        self.status_label.setText(message)

    def _on_close(self) -> None:
        """关闭窗口"""
        logger.info("开始关闭应用程序...")

        # 停止心跳检测
        self._heartbeat_timer.stop()

        # 清理设置选项卡资源
        if hasattr(self, "settings_tab") and self.settings_tab:
            self.settings_tab.cleanup()

        # 停止热键管理器
        if self.hotkey_manager:
            self.hotkey_manager.stop()

        # 停止窗口管理器
        if self.window_manager:
            self.window_manager.stop()

        # 保存配置
        if self.config_manager:
            # 退出时强制落盘，避免防抖保存还未触发导致配置丢失
            try:
                self.config_manager.save(self.config, immediate=True)
            except TypeError:
                # 兼容旧接口：如果没有 immediate 参数则退化到 flush()
                if hasattr(self.config_manager, "flush"):
                    self.config_manager.flush()
            finally:
                # 取消延迟保存定时器，避免退出后后台写入
                if hasattr(self.config_manager, "close"):
                    self.config_manager.close()

        # 隐藏托盘图标
        if self.tray_icon:
            self.tray_icon.hide()

        # 退出应用
        QApplication.quit()

    def closeEvent(self, event) -> None:
        """窗口关闭事件 - 隐藏到托盘

        Args:
            event: 关闭事件
        """
        event.ignore()
        self.hide_to_tray()

    def refresh_hotkeys(self) -> None:
        """刷新热键设置（从设置页面调用）"""
        self._setup_hotkeys()

    def _setup_log_handler(self) -> None:
        """设置日志处理器，将日志输出到关于选项卡的日志窗口（线程安全版本）"""

        class QtLogHandler(logging.Handler):
            """自定义日志处理器，将日志输出到队列"""

            def __init__(self, log_queue):
                super().__init__()
                self.log_queue = log_queue

            def emit(self, record):
                try:
                    msg = self.format(record)
                    self.log_queue.put(msg)
                except Exception:
                    # 格式化或队列操作失败时，使用标准错误处理
                    self.handleError(record)

        # 创建并添加日志处理器
        log_handler = QtLogHandler(self._log_queue)
        log_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
            )
        )

        # 获取根日志记录器并添加处理器
        root_logger = logging.getLogger()
        root_logger.addHandler(log_handler)
        log_handler.setLevel(logging.DEBUG)

    def _process_log_queue(self) -> None:
        """处理日志队列，在主线程中更新UI

        每次调用最多处理 MAX_BATCH 条，防止日志突发时长时间阻塞主线程。
        """
        MAX_BATCH = 50
        try:
            for _ in range(MAX_BATCH):
                try:
                    msg = self._log_queue.get_nowait()
                    self.log_updated.emit(msg)
                except Empty:
                    break
        except Exception as e:
            logger.warning("处理日志队列出错: %s", str(e))

    def _on_log_updated(self, message: str) -> None:
        """日志更新回调（在主线程中执行）

        Args:
            message: 日志消息
        """
        try:
            if hasattr(self.about_tab, "append_log"):
                if self._should_log_debug(message):
                    return
                if self._should_log_message(message):
                    self.about_tab.append_log(message)
        except Exception as e:
            logger.warning("更新日志UI出错: %s", str(e))

    def _should_log_debug(self, message: str) -> bool:
        """判断是否应该记录 DEBUG 日志"""
        if "[DEBUG]" in message:
            if (
                hasattr(self.about_tab, "get_debug_log_enabled")
                and self.about_tab.get_debug_log_enabled()
            ):
                self.about_tab.append_log(message)
            return True
        return False

    def _should_log_message(self, message: str) -> bool:
        """判断是否应该记录日志消息"""
        # 检查是否为时间调整日志（系统时间已调整）
        if "系统时间已调整" in message:
            return self._should_log_time_adjustment(message)

        # 检查是否为时间差日志（NTP时间获取成功）
        if "时间差：" in message and "毫秒" in message:
            return self._should_log_time_offset(message)

        # 检查是否为偏移量过小日志
        if "偏移量过小，无需调整" in message:
            return self._get_ntp_log_enabled()

        # 检查是否为 NTP / 校时日志
        if self._is_ntp_log(message):
            return self._get_ntp_log_enabled()

        # 检查是否为窗口刷新日志
        if self._is_window_refresh_log(message):
            return self._get_window_refresh_log_enabled()

        # 检查是否为窗口操作日志
        if self._is_window_operation_log(message):
            return self._get_window_operation_log_enabled()

        # 过滤掉自动保存的配置日志（避免刷屏）
        if "配置保存成功" in message and "自动保存" not in message:
            return False

        # 其他日志默认输出
        return True

    def _should_log_time_adjustment(self, message: str) -> bool:
        """判断是否应该记录时间调整日志"""
        if self._get_ntp_log_enabled():
            return True
        # 仅当偏移量 >= 1000ms 时才记录
        import re
        match = re.search(r"系统时间已调整：([\d.]+)ms", message)
        if match:
            offset_ms = float(match.group(1))
            if abs(offset_ms) >= 1000:
                return True
        return False

    def _should_log_time_offset(self, message: str) -> bool:
        """判断是否应该记录时间差日志"""
        if self._get_ntp_log_enabled():
            return True
        # 仅当偏移量 >= 1000ms 时才记录
        import re
        match = re.search(r"时间差：([\d.]+) 毫秒", message)
        if match:
            offset_ms = float(match.group(1))
            if abs(offset_ms) >= 1000:
                return True
        return False

    def _is_ntp_log(self, message: str) -> bool:
        """判断是否为 NTP/校时相关日志"""
        return any(keyword in message for keyword in ["NTP", "校准", "时间同步", "校时"])

    def _is_window_refresh_log(self, message: str) -> bool:
        """判断是否为窗口刷新相关日志"""
        return any(keyword in message for keyword in ["已刷新", "刷新窗口", "窗口列表"])

    def _is_window_operation_log(self, message: str) -> bool:
        """判断是否为窗口操作相关日志"""
        return any(keyword in message for keyword in ["隐藏窗口", "显示窗口", "窗口已隐藏", "窗口已显示"])

    def _get_ntp_log_enabled(self) -> bool:
        """获取 NTP 日志开关状态"""
        return (
            hasattr(self.about_tab, "get_ntp_log_enabled")
            and self.about_tab.get_ntp_log_enabled()
        )

    def _get_window_refresh_log_enabled(self) -> bool:
        """获取窗口刷新日志开关状态"""
        return (
            hasattr(self.about_tab, "get_window_refresh_log_enabled")
            and self.about_tab.get_window_refresh_log_enabled()
        )

    def _get_window_operation_log_enabled(self) -> bool:
        """获取窗口操作日志开关状态"""
        return (
            hasattr(self.about_tab, "get_window_operation_log_enabled")
            and self.about_tab.get_window_operation_log_enabled()
        )


def create_main_window(window_manager: Optional[WindowManager] = None) -> AppWindow:
    """创建主窗口的工厂函数

    Args:
        window_manager: 窗口管理器实例

    Returns:
        AppWindow: 主窗口实例
    """
    return AppWindow(window_manager)
