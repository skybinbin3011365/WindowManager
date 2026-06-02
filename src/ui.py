# -*- coding: utf-8 -*-
# windowmanager/ui.py
"""
窗口管理器 - 主UI模块 (PySide6版本)
整合所有UI组件的主入口
"""

import os
import time
import logging
from dataclasses import dataclass, field
from typing import Optional
from queue import Queue, Empty, Full

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
from PySide6.QtCore import QTimer, Signal, QEventLoop
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
    TimeThresholdConstants,
)
from utils import get_resource_path
from theme import theme

import ui_main
import ui_settings
import ui_about

# 常量定义（在 constants.py 中统一管理）

logger = logging.getLogger(__name__)


@dataclass
class TrayState:
    """托盘状态数据类，封装托盘相关属性"""
    icon: Optional[QSystemTrayIcon] = None
    heartbeat_timer: Optional[QTimer] = None
    last_interaction: float = 0.0


@dataclass
class LogState:
    """日志状态数据类，封装日志相关属性"""
    queue: Queue = field(default_factory=lambda: Queue(maxsize=1000))
    timer: Optional[QTimer] = None


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
        self.config_manager = ConfigManager.get_instance()
        try:
            self.config = self.config_manager.load()
        except Exception as e:
            logger.error("加载配置失败: %s", str(e), exc_info=True)
            self.config = Config()

        self.hotkey_manager: HotkeyManager = HotkeyManager()

        self._tray_state = TrayState()
        self._log_state = LogState()
        self._heartbeat_timer: QTimer = QTimer()
        self.time_sync_tool = None

    def _init_window_properties(self):
        """初始化窗口属性"""
        # 设置窗口属性
        self.setWindowTitle(AppConstants.APP_TITLE)
        self.setMinimumSize(
            UIConstants.MIN_WINDOW_WIDTH,
            UIConstants.MIN_WINDOW_HEIGHT,
        )

        # 从配置读取上次保存的窗口尺寸
        width = UIConstants.WINDOW_DEFAULT_WIDTH
        height = UIConstants.WINDOW_DEFAULT_HEIGHT
        if self.config and hasattr(self.config, "ui") and isinstance(self.config.ui, dict):
            width = self.config.ui.get("width", UIConstants.WINDOW_DEFAULT_WIDTH)
            height = self.config.ui.get("height", UIConstants.WINDOW_DEFAULT_HEIGHT)

        self.resize(width, height)

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
            self.main_window.show_selected_hidden_windows  # ✅ 修复：只显示不最小化
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
        """启动窗口管理器 - 使用QTimer延迟执行"""
        if not self.window_manager:
            return

        # 使用QTimer在事件循环中延迟执行（避免线程问题）
        def do_start():
            try:
                logger.info("QTimer回调: 开始启动窗口管理器...")
                self.window_manager.start()
                logger.info("QTimer回调: 窗口管理器启动完成, is_running=%s", self.window_manager.is_running)

                if not self.window_manager.is_running:
                    logger.warning("窗口管理器未正常运行")
                    return

                # 再次延迟刷新
                QTimer.singleShot(UIConstants.POST_START_REFRESH_DELAY, lambda: self.request_refresh_windows.emit())
                logger.info("QTimer回调: 已设置%dms后刷新信号", UIConstants.POST_START_REFRESH_DELAY)
            except Exception as e:
                logger.error("启动窗口管理器失败: %s", str(e), exc_info=True)

        from PySide6.QtCore import QTimer
        QTimer.singleShot(UIConstants.START_WINDOW_MANAGER_DELAY, do_start)

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

        self._log_state.timer = QTimer()
        self._log_state.timer.timeout.connect(self._process_log_queue)
        self._log_state.timer.start(UICommonConstants.LOG_TIMER_INTERVAL_MS)

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
                hide_hotkey = self.config.hotkey.hide_hotkey
                show_hotkey = self.config.hotkey.show_hotkey
                switch_hotkey = self.config.hotkey.switch_hotkey

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
        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("系统托盘不可用，延迟重试")
            QTimer.singleShot(UIConstants.TRAY_INIT_RETRY_DELAY, self._init_tray)
            return

        self._tray_state.icon = QSystemTrayIcon(self)

        icon_loaded = False
        icon_candidates = [get_resource_path(icon) for icon in PathConstants.ICON_CANDIDATES]

        for icon_path in icon_candidates:
            if icon_path and os.path.exists(icon_path):
                qicon = QIcon(icon_path)
                if not qicon.isNull():
                    self._tray_state.icon.setIcon(qicon)
                    icon_loaded = True
                    logger.debug("托盘图标已加载: %s", icon_path)
                    break

        if not icon_loaded:
            # 使用应用图标作为回退
            app_icon = self.windowIcon()
            if not app_icon.isNull():
                self._tray_state.icon.setIcon(app_icon)
                logger.warning("候选图标均不可用，使用窗口图标作为托盘图标")
            else:
                logger.error("无法加载任何托盘图标，托盘可能无法正常显示")

        self._tray_state.icon.setToolTip(AppConstants.APP_TITLE)

        tray_menu = QMenu()

        show_action = QAction("显示主窗口", self)
        show_action.triggered.connect(self.show_and_activate)
        tray_menu.addAction(show_action)

        tray_menu.addSeparator()

        exit_action = QAction("退出程序", self)
        exit_action.triggered.connect(self._on_close)
        tray_menu.addAction(exit_action)

        self._tray_state.icon.setContextMenu(tray_menu)
        self._tray_state.icon.activated.connect(self._on_tray_activated)
        self._tray_state.icon.show()

        # 验证托盘图标是否真正可见
        if not self._tray_state.icon.isVisible():
            logger.warning("托盘图标调用 show() 后仍不可见，尝试延迟重试")
            QTimer.singleShot(UIConstants.TRAY_VISIBLE_CHECK_DELAY, self._ensure_tray_visible)
        else:
            logger.debug("系统托盘初始化完成，图标已可见")

        self._start_tray_heartbeat()

    def _ensure_tray_visible(self) -> None:
        """确保托盘图标可见（延迟重试）"""
        if self._tray_state.icon and not self._tray_state.icon.isVisible():
            self._tray_state.icon.show()
            if self._tray_state.icon.isVisible():
                logger.debug("延迟重试后托盘图标已可见")
            else:
                logger.warning("托盘图标仍不可见，可能需要重新初始化")
                self._reinitialize_tray()

    def _start_tray_heartbeat(self) -> None:
        """启动托盘心跳检测（防止托盘图标假死）"""
        self._tray_state.heartbeat_timer = QTimer(self)
        self._tray_state.heartbeat_timer.timeout.connect(self._refresh_tray_icon)
        self._tray_state.heartbeat_timer.start(UIConstants.TRAY_HEARTBEAT_INTERVAL)
        self._tray_state.last_interaction = time.time()

    def _refresh_tray_icon(self) -> None:
        """刷新托盘图标状态（防假死）"""
        if self._tray_state.icon:
            try:
                if not self._tray_state.icon.isVisible():
                    logger.debug("托盘图标不可见，尝试重新显示")
                    self._tray_state.icon.show()
                    if not self._tray_state.icon.isVisible():
                        self._reinitialize_tray()
                        return

                current_icon = self._tray_state.icon.icon()
                if not current_icon.isNull():
                    self._tray_state.icon.hide()
                    self._tray_state.icon.setIcon(current_icon)
                    self._tray_state.icon.show()

                self._check_event_loop_health()

            except Exception as e:
                logger.debug("托盘图标刷新失败，尝试重新初始化: %s", e)
                self._reinitialize_tray()

    def _check_event_loop_health(self) -> None:
        """检查事件循环健康状态"""
        try:
            QApplication.processEvents(QEventLoop.AllEvents, 100)

            current_time = time.time()
            if current_time - self._tray_state.last_interaction > 120:
                logger.debug("检测到托盘长时间无响应，触发刷新")
                self._reinitialize_tray()
                self._tray_state.last_interaction = current_time
            else:
                self._tray_state.last_interaction = current_time

        except Exception as e:
            logger.debug("事件循环健康检查失败: %s", e)

    def _reinitialize_tray(self) -> None:
        """重新初始化托盘（假死恢复）"""
        try:
            # 先停止并清理旧定时器，防止泄漏
            if self._tray_state.heartbeat_timer:
                self._tray_state.heartbeat_timer.stop()
                self._tray_state.heartbeat_timer.deleteLater()
                self._tray_state.heartbeat_timer = None

            if self._tray_state.icon:
                self._tray_state.icon.hide()
                self._tray_state.icon.deleteLater()

            self._init_tray()
            logger.debug("托盘图标已重新初始化（假死恢复）")

        except Exception as e:
            logger.error("托盘重新初始化失败: %s", e)

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """托盘图标激活事件

        Args:
            reason: 激活原因
        """
        self._tray_state.last_interaction = time.time()

        if reason in (QSystemTrayIcon.DoubleClick, QSystemTrayIcon.Trigger):
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
        # 验证托盘图标是否可见，不可见则先尝试修复
        if not self._tray_state.icon or not self._tray_state.icon.isVisible():
            logger.warning("托盘图标不可见，尝试重新初始化后再隐藏")
            self._reinitialize_tray()
            # 重新初始化后仍不可见，则不隐藏窗口
            if not self._tray_state.icon or not self._tray_state.icon.isVisible():
                logger.error("托盘图标不可用，无法隐藏到托盘")
                return

        self.hide()
        if self._tray_state.icon:
            self._tray_state.icon.showMessage(
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

        # 保存窗口尺寸到配置
        if self.config and hasattr(self.config, "ui") and isinstance(self.config.ui, dict):
            self.config.ui["width"] = self.width()
            self.config.ui["height"] = self.height()
            logger.info(f"已保存窗口尺寸: {self.width()}x{self.height()}")

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

        if self._tray_state.icon:
            self._tray_state.icon.hide()

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
                    self.log_queue.put_nowait(msg)
                except Full:
                    # 队列满时丢弃最旧的一条日志，再写入新日志
                    try:
                        self.log_queue.get_nowait()
                        self.log_queue.put_nowait(msg)
                    except Exception:
                        pass
                except Exception:
                    self.handleError(record)

        # 创建并添加日志处理器
        log_handler = QtLogHandler(self._log_state.queue)
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
                    msg = self._log_state.queue.get_nowait()
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
        # 仅当偏移量 >= 阈值时才记录
        import re
        match = re.search(r"系统时间已调整：([\d.]+)ms", message)
        if match:
            offset_ms = float(match.group(1))
            if abs(offset_ms) >= TimeThresholdConstants.LOG_TIME_OFFSET_THRESHOLD_MS:
                return True
        return False

    def _should_log_time_offset(self, message: str) -> bool:
        """判断是否应该记录时间差日志"""
        if self._get_ntp_log_enabled():
            return True
        # 仅当偏移量 >= 阈值时才记录
        import re
        match = re.search(r"时间差：([\d.]+) 毫秒", message)
        if match:
            offset_ms = float(match.group(1))
            if abs(offset_ms) >= TimeThresholdConstants.LOG_TIME_OFFSET_THRESHOLD_MS:
                return True
        return False

    def _is_ntp_log(self, message: str) -> bool:
        """判断是否为 NTP/校时相关日志"""
        return any(keyword in message for keyword in ["NTP", "校准", "时间同步", "校时"])

    def _is_window_refresh_log(self, message: str) -> bool:
        """判断是否为窗口刷新相关日志"""
        return any(keyword in message for keyword in [
            "已刷新", "刷新窗口", "窗口列表",
            "指定进程扫描", "目标 PID", "发现 个窗口",
            "窗口: hwnd=", "PID=", "进程=", "状态=可见", "状态=隐藏"
        ])

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
