# -*- coding: utf-8 -*-
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

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QTimer, Signal

from window_base import WindowInfo, WindowState
from core import SafeWindowsAPI
from manager import WindowManager
from config import ConfigManager, Config
from constants import UIMainConstants, WindowConstants
from deps import PSUTIL_AVAILABLE, psutil, win32con
from window_models import WindowEntryState

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
        # 超级窗口字典：{process_name_lower: SimpleWindowInfo}
        # 由 WindowRefreshThread 每次刷新时更新，所有窗口确认统一从此字典查找
        self._super_windows_by_process: dict = {}

        # 初始化UI
        self._init_ui()

        # 线程安全：后台线程只发信号，主线程执行 Qt/配置相关操作
        self.request_refresh.connect(self.refresh_windows)
        self.request_save_hidden_windows.connect(self._save_hidden_windows)

        # 注册为配置观察者
        if self.config_manager:
            self.config_manager.register_observer(self)

        # 延迟初始化
        QTimer.singleShot(UIMainConstants.RESTORE_HIDDEN_WINDOWS_DELAY, self._restore_hidden_windows)
        QTimer.singleShot(UIMainConstants.LOAD_SWITCH_PROCESSES_DELAY, self._load_switch_processes_from_config)

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
        QTimer.singleShot(UIMainConstants.AUTO_SELECT_KEYWORD_DELAY, self._auto_select_keyword_windows)

    def closeEvent(self, event) -> None:
        """窗口关闭事件 - 清理资源"""
        if self.config_manager:
            self.config_manager.unregister_observer(self)

        if hasattr(self, "_refresh_timer") and self._refresh_timer:
            self._refresh_timer.stop()

        if hasattr(self, "_refresh_thread") and self._refresh_thread:
            if self._refresh_thread.isRunning():
                self._refresh_thread.requestInterruption()
                if not self._refresh_thread.wait(UIMainConstants.THREAD_WAIT_TIMEOUT):
                    logger.warning("窗口刷新线程未能及时停止，强制终止")
            self._refresh_thread.deleteLater()
            self._refresh_thread = None

        super().closeEvent(event)

    def on_config_changed(self) -> None:
        """配置变更回调 - 观察者模式实现（config_manager 调用）"""
        if self.config_manager:
            self.update(self.config_manager.get())

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
        """启动时设置隐藏窗口列表到窗口管理器

        同时清理/更新 config.target_windows 中的旧条目：
        - hwnd 有效：更新标题/进程名等字段
        - hwnd 失效 + 进程退出：从配置中移除
        - hwnd 失效 + 进程仍在：用新窗口信息替换旧条目
        """
        if not self.window_manager or not self.config:
            return
        if not getattr(self.window_manager, "is_running", False):
            logger.warning("窗口管理器未运行，跳过设置隐藏窗口列表")
            return

        target_windows = getattr(self.config, "target_windows", [])
        hidden_windows_info = [
            w for w in target_windows
            if isinstance(w, dict) and w.get("state") == WindowEntryState.HIDDEN.value
        ]

        if not hidden_windows_info:
            return

        if not hasattr(self.window_manager, "set_software_hidden_windows"):
            return

        from deps import WIN32GUI_AVAILABLE, win32gui as _win32gui
        if not WIN32GUI_AVAILABLE or _win32gui is None:
            logger.warning("win32gui 不可用，无法恢复隐藏窗口")
            return

        hwnds = []
        restored_count = 0
        fallback_count = 0
        # 记录需要从配置中移除的旧条目（进程已退出）
        entries_to_remove = []
        # 记录需要更新的旧条目（hwnd失效但进程仍在，回退找到了新窗口）
        entries_to_update = {}

        for window_info in hidden_windows_info:
            saved_hwnd = window_info.get("hwnd")
            process_name = window_info.get("process_name", "")
            title = window_info.get("title", "")

            if self._try_restore_by_hwnd(saved_hwnd, title, process_name, hwnds):
                restored_count += 1
                # hwnd有效，更新配置中的标题/进程名（可能已变化）
                self._update_config_entry(window_info, saved_hwnd)
                continue

            if process_name and PSUTIL_AVAILABLE and psutil is not None:
                # 检查进程是否仍在运行
                process_alive = self._is_process_running(process_name)
                if process_alive:
                    # 进程仍在，尝试按进程名回退查找
                    old_hwnd = saved_hwnd
                    found = self._try_restore_by_process(
                        process_name, title, hwnds, _win32gui,
                    )
                    fallback_count += found
                    if found and old_hwnd:
                        # 回退成功，记录旧条目需要更新
                        entries_to_update[old_hwnd] = window_info
                    elif not found:
                        # 同一PID的窗口已被前一个条目占用，当前条目是重复的
                        entries_to_remove.append(window_info)
                        logger.info(
                            "启动清理: 进程 '%s' 的窗口已被其他条目占用，移除重复条目 hwnd=%d title='%s'",
                            process_name, saved_hwnd or 0, title,
                        )
                else:
                    # 进程已退出，标记旧条目待移除
                    entries_to_remove.append(window_info)
                    logger.info(
                        "启动清理: 进程 '%s' 已退出，移除旧条目 hwnd=%d title='%s'",
                        process_name, saved_hwnd or 0, title,
                    )
            else:
                # hwnd无效且无法回退查找（无进程名或psutil不可用），移除条目
                entries_to_remove.append(window_info)
                logger.info(
                    "启动清理: 无法回退查找，移除条目 hwnd=%d title='%s' process='%s'",
                    saved_hwnd or 0, title, process_name,
                )

        if hwnds:
            self.window_manager.set_software_hidden_windows(hwnds)
            # 将恢复的隐藏窗口加入 _selected_windows，确保热键/按钮能操作
            with self._lock:
                for hwnd in hwnds:
                    self._selected_windows.add(hwnd)
            logger.info("已将 %d 个隐藏窗口加入选中集合", len(hwnds))

        # 清理无效条目并持久化
        config_changed = False
        if entries_to_remove:
            remove_set = set(id(e) for e in entries_to_remove)
            self.config.target_windows = [
                w for w in self.config.target_windows
                if id(w) not in remove_set
            ]
            config_changed = True
            logger.info("启动清理: 移除 %d 个已退出进程的旧条目", len(entries_to_remove))

        if entries_to_update:
            # 回退找到新窗口后，旧hwnd对应的条目需要更新为新hwnd
            # 新窗口信息已在 _try_restore_by_process 中添加到 hwnds
            # 这里更新配置条目的hwnd
            for old_hwnd, entry in entries_to_update.items():
                # 查找新添加的hwnd（同一进程名）
                new_hwnd = self._find_new_hwnd_for_process(
                    entry.get("process_name", ""), hwnds
                )
                if new_hwnd and new_hwnd != old_hwnd:
                    entry["hwnd"] = new_hwnd
                    new_title = SafeWindowsAPI.get_window_text(new_hwnd).strip()
                    if new_title:
                        entry["title"] = new_title
                    config_changed = True
                    logger.info(
                        "启动更新: hwnd %d → %d (process='%s', title='%s')",
                        old_hwnd, new_hwnd, entry.get("process_name", ""), new_title,
                    )

        if config_changed and self.config_manager:
            self.config_manager.save(self.config, immediate=True)

    def _update_config_entry(self, entry: dict, hwnd: int) -> None:
        """更新配置条目中的标题和进程名（hwnd有效时调用）"""
        try:
            curr_title = SafeWindowsAPI.get_window_text(hwnd).strip()
            _, curr_pid = SafeWindowsAPI.get_window_thread_process_id(hwnd)
            curr_process_name = SafeWindowsAPI.get_process_name(curr_pid) if curr_pid else ""

            updated = False
            if curr_title and curr_title != entry.get("title", ""):
                entry["title"] = curr_title
                updated = True
            if curr_process_name and curr_process_name != entry.get("process_name", ""):
                entry["process_name"] = curr_process_name
                updated = True
            if updated:
                logger.debug(
                    "启动更新: hwnd=%d 配置信息已刷新 (title='%s', process='%s')",
                    hwnd, curr_title, curr_process_name,
                )
        except Exception:
            pass

    def _is_process_running(self, process_name: str) -> bool:
        """检查指定进程名的进程是否仍在运行"""
        if not PSUTIL_AVAILABLE or psutil is None:
            return True
        try:
            for proc in psutil.process_iter(["name"]):
                try:
                    if proc.info["name"] and proc.info["name"].lower() == process_name.lower():
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            return True
        return False

    def _find_new_hwnd_for_process(self, process_name: str, hwnds: list) -> int:
        """从hwnd列表中查找属于指定进程的窗口句柄"""
        if not process_name:
            return 0
        for hwnd in hwnds:
            try:
                _, pid = SafeWindowsAPI.get_window_thread_process_id(hwnd)
                curr_name = SafeWindowsAPI.get_process_name(pid) if pid else ""
                if curr_name.lower() == process_name.lower():
                    return hwnd
            except Exception:
                continue
        return 0

    def _try_restore_by_hwnd(
        self, saved_hwnd, title: str, process_name: str, hwnds: list = None
    ) -> bool:
        """尝试通过保存的 HWND 恢复隐藏窗口

        核心逻辑：hwnd 是唯一标识，标题/进程名仅用于日志辨识。
        1. hwnd 无效（IsWindow=False）→ 窗口已销毁，跳过
        2. hwnd 有效 + 进程存活 → 恢复到 _hidden_windows
        3. hwnd 有效但进程不存在 → 进程已退出，跳过（后续清理移除）

        不做标题严格匹配，因为窗口被隐藏后标题可能变化（如浏览器切换标签页），
        但 hwnd 仍指向同一个窗口。
        """
        if not saved_hwnd or not SafeWindowsAPI.is_window(saved_hwnd):
            logger.debug("hwnd=%d 无效（窗口已销毁），跳过", saved_hwnd or 0)
            return False

        try:
            # 获取当前窗口信息（仅用于日志和更新辨识参数）
            curr_title = SafeWindowsAPI.get_window_text(saved_hwnd).strip()
            _, curr_pid = SafeWindowsAPI.get_window_thread_process_id(saved_hwnd)
            curr_process_name = SafeWindowsAPI.get_process_name(curr_pid) if curr_pid else ""

            # 进程存活检查：进程不在则窗口无意义
            if curr_pid and PSUTIL_AVAILABLE and psutil is not None:
                if not psutil.pid_exists(curr_pid):
                    logger.debug(
                        "hwnd=%d 进程已退出 (pid=%d, process=%s)，跳过恢复",
                        saved_hwnd, curr_pid, curr_process_name or process_name,
                    )
                    return False

            # 防御性检查：验证 hwnd 在超级窗口字典中存在
            # 超级窗口字典是唯一数据源，不管窗口可见还是隐藏，始终在字典中
            super_dict = getattr(self, "_super_windows_by_process", {})
            hwnd_in_super_dict = any(
                sw.hwnd == saved_hwnd for sw in super_dict.values()
            ) if super_dict else SafeWindowsAPI.is_super_window(saved_hwnd)

            if not hwnd_in_super_dict:
                logger.debug(
                    "hwnd=%d 不在超级窗口字典中，跳过 (title=%s)",
                    saved_hwnd, curr_title or title,
                )
                return False

            if hwnds is not None:
                hwnds.append(saved_hwnd)
            # 用当前实际标题更新辨识信息，标题可能已变
            self._add_hidden_window_info(
                saved_hwnd, curr_title or title, curr_process_name or process_name, curr_pid
            )

            logger.info(
                "恢复隐藏窗口: hwnd=%d, title='%s' → '%s', process=%s",
                saved_hwnd, title, curr_title, curr_process_name or process_name,
            )
            return True
        except Exception:
            return False

    def _try_restore_by_process(
        self, process_name: str, title: str, hwnds: list, win32gui
    ) -> int:
        """通过进程名枚举窗口来恢复隐藏窗口（hwnd 路径失败时的回退）

        当保存的 hwnd 已失效（窗口被关闭/进程重启），但同名进程仍在运行时，
        枚举该进程的窗口并恢复到 _hidden_windows。

        标题参数仅用于日志辨识，不作为严格匹配条件（因为标题可能已变化）。
        每个 PID 只取一个 VW 窗口（one-VW-per-PID）。
        """
        found = 0
        found_pids: set = set()

        # 优先从超级窗口字典查找（唯一数据源）
        super_dict = getattr(self, "_super_windows_by_process", {})
        proc_key = process_name.lower()
        super_win = super_dict.get(proc_key) if super_dict else None

        if super_win:
            hwnd = super_win.hwnd
            pid = super_win.pid
            if pid not in found_pids:
                found_pids.add(pid)
                if hwnd not in hwnds:
                    hwnds.append(hwnd)
                    self._add_hidden_window_info(
                        hwnd, super_win.title or title or "", process_name, pid,
                    )
                    found += 1
            return found

        # 字典为空时回退到枚举（首次启动字典尚未构建的情况）
        try:
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    if proc.info["name"].lower() != process_name.lower():
                        continue

                    pid = proc.info["pid"]
                    windows = self._enum_all_windows_by_pid(pid, win32gui)
                    for hwnd in windows:
                        if not SafeWindowsAPI.is_super_window(hwnd):
                            logger.debug(
                                "启动恢复: 跳过非超级窗口: hwnd=%d, process=%s",
                                hwnd, process_name,
                            )
                            continue

                        _, curr_pid = SafeWindowsAPI.get_window_thread_process_id(hwnd)
                        if curr_pid in found_pids:
                            continue
                        found_pids.add(curr_pid)

                        if hwnd not in hwnds:
                            hwnds.append(hwnd)
                            self._add_hidden_window_info(hwnd, title or "", process_name, pid)
                            found += 1
                except Exception:
                    continue
        except Exception:
            pass
        return found

    def _enum_all_windows_by_pid(self, pid: int, win32gui) -> list:
        """枚举属于指定进程的所有顶层用户窗口（不检查标题，用于title为空时的恢复）"""
        result = []

        def callback(hwnd, acc):
            try:
                if not SafeWindowsAPI.is_window(hwnd):
                    return True
                _, curr_pid = SafeWindowsAPI.get_window_thread_process_id(hwnd)
                if curr_pid != pid:
                    return True
                # 只保留顶层窗口（无父窗口）
                if SafeWindowsAPI.get_parent(hwnd) != 0:
                    return True
                # 过滤无标题窗口
                title = SafeWindowsAPI.get_window_text(hwnd).strip()
                if not title:
                    return True
                # 过滤系统类名窗口
                class_name = SafeWindowsAPI.get_window_class(hwnd)
                if any(class_name.startswith(p) for p in WindowConstants.NON_USER_CLASS_PREFIXES):
                    return True
                # 过滤工具窗口（WS_EX_TOOLWINDOW）
                try:
                    ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                    if ex_style & win32con.WS_EX_TOOLWINDOW:
                        return True
                except Exception:
                    pass
                acc.append(hwnd)
            except Exception:
                pass
            return True

        win32gui.EnumWindows(callback, result)
        return result

    def _add_hidden_window_info(
        self, hwnd, title: str, process_name: str, pid=None
    ) -> None:
        """将窗口信息添加到隐藏窗口字典

        防御性检查：仅接受超级窗口字典中存在的窗口，避免子窗口、菜单窗口等污染隐藏列表
        使用超级窗口字典作为唯一数据源，不管窗口可见还是隐藏，始终在字典中。
        """
        # 防御：跳过非超级窗口（字典为空时回退到 is_super_window）
        super_dict = getattr(self, "_super_windows_by_process", {})
        if hwnd > 0 and super_dict:
            hwnd_in_dict = any(sw.hwnd == hwnd for sw in super_dict.values())
            if not hwnd_in_dict:
                logger.debug(
                    "_add_hidden_window_info: 跳过非超级窗口: hwnd=%d, title=%s",
                    hwnd, title,
                )
                return

        win_info = self.window_manager.get_window(hwnd)
        if not win_info:
            if pid is None:
                _, pid = SafeWindowsAPI.get_window_thread_process_id(hwnd)
            win_info = WindowInfo.create_hidden(
                hwnd=hwnd, title=title, process_name=process_name, pid=pid,
            )
        else:
            win_info.state = WindowState.HIDDEN
            win_info.is_visible = False
        self.window_manager.add_hidden_window(hwnd, win_info)

    def _on_window_double_clicked(self, hwnd: int) -> None:
        """处理窗口双击事件"""
        if self.window_manager:
            try:
                self.window_manager.show_window(hwnd)
            except Exception as e:
                logger.error("显示窗口 %d 失败: %s", hwnd, str(e))

    def _safe_stop_old_refresh_thread(self) -> None:
        """安全停止并释放旧的刷新线程，防止 QThread 销毁警告

        使用非阻塞方式停止线程：请求中断 + 断开信号 + deleteLater，
        不在主线程中 wait()，避免阻塞 UI 导致界面卡死。
        """
        old_thread = self._refresh_thread
        if old_thread is None:
            return

        # 立即清除引用，防止重复操作
        self._refresh_thread = None

        # 断开旧线程的信号连接，防止旧线程跑完后回调到已销毁的对象
        try:
            old_thread.refresh_finished.disconnect()
            old_thread.auto_selected.disconnect()
            old_thread.hwnd_updated.disconnect()
        except Exception:
            pass

        # 请求中断（非阻塞）
        old_thread.requestInterruption()
        old_thread.quit()

        # 非阻塞等待：只等极短时间（100ms），避免卡死 UI
        if old_thread.isRunning():
            if not old_thread.wait(UIMainConstants.THREAD_SHORT_WAIT_TIMEOUT):
                # 线程未在 100ms 内退出，安排延迟清理
                logger.debug("刷新线程未立即退出，安排延迟清理")
                self._schedule_thread_cleanup(old_thread)
                return

        # 线程已退出，安全删除
        try:
            old_thread.deleteLater()
        except Exception as e:
            logger.debug("删除刷新线程时出错: %s", str(e))

    def _schedule_thread_cleanup(self, thread) -> None:
        """安排延迟清理线程（非阻塞方式）

        使用 QTimer 定期检查线程是否已退出，退出后自动清理。
        如果超时仍未退出，则强制终止。
        """
        max_checks = UIMainConstants.THREAD_CLEANUP_MAX_CHECKS
        check_interval = UIMainConstants.THREAD_CLEANUP_INTERVAL

        def _check_and_cleanup(remaining: int):
            if not thread.isRunning():
                try:
                    thread.deleteLater()
                    logger.debug("延迟清理：线程已安全退出")
                except Exception:
                    pass
                return

            if remaining <= 0:
                logger.warning("延迟清理超时，强制终止线程")
                thread.terminate()
                try:
                    thread.deleteLater()
                except Exception:
                    pass
                return

            # 继续等待
            QTimer.singleShot(check_interval, lambda: _check_and_cleanup(remaining - 1))

        _check_and_cleanup(max_checks)

    def refresh_windows(self) -> None:
        """刷新窗口列表 - 三栏布局版本"""
        logger.debug("refresh_windows: 开始执行")
        if not self.window_manager:
            logger.warning("refresh_windows: window_manager 为空，返回")
            return

        if not self._selected_windows_loaded_from_config:
            logger.debug("refresh_windows: 加载配置中的选中窗口...")
            self._load_selected_windows_from_config()
            self._selected_windows_loaded_from_config = True
            logger.debug("refresh_windows: 配置加载完成")

        with self._lock:
            self._ignored_windows.clear()

        # 先安全停止旧线程，防止 QThread Destroyed 警告
        logger.debug("refresh_windows: 停止旧刷新线程...")
        self._safe_stop_old_refresh_thread()
        logger.debug("refresh_windows: 旧线程已停止")

        keywords = getattr(self.config.filter, "keywords", []) if self.config else []

        # 从配置读取隐藏窗口信息，用于传给刷新线程
        hidden_process_names = set()
        hidden_windows_info = []
        if self.config:
            target_windows = getattr(self.config, "target_windows", [])
            for w in target_windows:
                if isinstance(w, dict) and w.get("state") == WindowEntryState.HIDDEN.value:
                    hidden_process_names.add(w.get("process_name", "").lower())
                    hidden_windows_info.append(w)

        self._refresh_thread = WindowRefreshThread(
            window_manager=self.window_manager,
            selected_windows=self._selected_windows,
            ignored_windows=self._ignored_windows,
            keywords=keywords,
            config=self.config,
            hidden_process_names=hidden_process_names,
            hidden_windows_info=hidden_windows_info,
            shared_lock=self._lock,
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
