# windowmanager/manager.py
import threading
import logging
from typing import Dict, List, Optional
from . import core
SafeWindowsAPI = core.SafeWindowsAPI
WindowInfo = core.WindowInfo
WindowState = core.WindowState

logger = logging.getLogger(__name__)


class WindowManager:
    def __init__(self):
        self._windows: Dict[int, WindowInfo] = {}
        self._lock = threading.RLock()
        self._hidden_windows: Dict[int, WindowInfo] = {}
        self._running = False

    @property
    def is_running(self) -> bool:
        """检查窗口管理器是否正在运行"""
        return self._running

    @property
    def windows(self) -> List[WindowInfo]:
        """获取所有窗口列表（只读）"""
        with self._lock:
            return list(self._windows.values())

    def start(self):
        self._running = True
        logger.info("Window manager started")

    def stop(self):
        self._running = False
        logger.info("Window manager stopped")

    def refresh_windows(self) -> List[WindowInfo]:
        with self._lock:
            hwnds = SafeWindowsAPI.enum_windows()

            # 清除不在枚举列表中的窗口
            windows_to_remove = []
            for hwnd in list(self._windows.keys()):
                if hwnd not in hwnds and hwnd not in self._hidden_windows:
                    windows_to_remove.append(hwnd)

            for hwnd in windows_to_remove:
                if hwnd in self._windows:
                    del self._windows[hwnd]

            # 添加或更新窗口信息
            for hwnd in hwnds:
                if hwnd in self._hidden_windows:
                    # 窗口仍然隐藏，复制信息并确保状态正确
                    win_info = self._hidden_windows[hwnd]
                    # 确保隐藏窗口的状态正确
                    win_info.state = WindowState.HIDDEN
                    win_info.is_visible = False
                    self._windows[hwnd] = win_info
                elif hwnd not in self._windows:
                    # 新窗口
                    title = SafeWindowsAPI.get_window_text(hwnd)
                    class_name = SafeWindowsAPI.get_window_class(hwnd)
                    _, pid = SafeWindowsAPI.get_window_thread_process_id(hwnd)
                    is_visible = SafeWindowsAPI.is_window_visible(hwnd)

                    process_name = SafeWindowsAPI.get_process_name(pid)

                    win_info = WindowInfo(
                        hwnd=hwnd,
                        title=title,
                        class_name=class_name,
                        pid=pid,
                        state=WindowState.NORMAL,
                        is_visible=is_visible,
                        process_name=process_name
                    )

                    self._windows[hwnd] = win_info
                else:
                    # 更新现有窗口信息
                    win_info = self._windows[hwnd]
                    win_info.title = SafeWindowsAPI.get_window_text(hwnd)
                    new_visible = SafeWindowsAPI.is_window_visible(hwnd)

                    # 根据可见性更新状态
                    if new_visible and win_info.state == WindowState.HIDDEN:
                        win_info.state = WindowState.NORMAL
                    elif not new_visible and win_info.state == WindowState.NORMAL:
                        win_info.state = WindowState.HIDDEN

                    win_info.is_visible = new_visible

            logger.info("Refreshed %d windows, %d hidden", len(self._windows), len(self._hidden_windows))
            return list(self._windows.values())

    def get_all_windows(self) -> List[WindowInfo]:
        with self._lock:
            return list(self._windows.values())

    def get_window(self, hwnd: int) -> Optional[WindowInfo]:
        with self._lock:
            return self._windows.get(hwnd)

    def hide_window(self, hwnd: int) -> bool:
        """隐藏窗口

        Args:
            hwnd: 窗口句柄

        Returns:
            bool: 是否成功隐藏
        """
        with self._lock:
            if hwnd not in self._windows:
                logger.warning("Window %d not found in managed windows", hwnd)
                return False

            win_info = self._windows[hwnd]

            # 检查窗口是否仍然有效
            if not SafeWindowsAPI.is_window(hwnd):
                logger.warning("Window %d is no longer valid", hwnd)
                return False

            try:
                if SafeWindowsAPI.show_window(hwnd, 0):
                    win_info.state = WindowState.HIDDEN
                    win_info.is_visible = False
                    self._hidden_windows[hwnd] = win_info
                    logger.info("Hidden window: %d - %s", hwnd, win_info.title)
                    return True
                else:
                    logger.warning("Failed to hide window %d", hwnd)
                    return False
            except (RuntimeError, OSError) as e:
                logger.error("OS error hiding window %d: %s", hwnd, str(e))
                return False
            except Exception as e:
                logger.error("Unexpected error hiding window %d: %s", hwnd, str(e), exc_info=True)
                return False

    def show_window(self, hwnd: int) -> bool:
        """
        显示指定的窗口

        Args:
            hwnd: 窗口句柄

        Returns:
            bool: 显示成功返回True，否则返回False
        """
        with self._lock:
            try:
                # 首先验证窗口是否仍然有效
                if not SafeWindowsAPI.is_window(hwnd):
                    logger.warning("Window %d is no longer valid, cannot show", hwnd)
                    # 清理无效窗口的引用
                    if hwnd in self._hidden_windows:
                        del self._hidden_windows[hwnd]
                    if hwnd in self._windows:
                        del self._windows[hwnd]
                    return False

                # 获取或创建窗口信息
                win_info = self._get_or_create_window_info(hwnd)

                # 执行窗口显示操作
                # 5表示SW_SHOW，显示窗口并激活它
                if SafeWindowsAPI.show_window(hwnd, 5):
                    try:
                        # 尝试将窗口置于前台
                        SafeWindowsAPI.set_foreground_window(hwnd)
                    except (RuntimeError, OSError) as e:
                        logger.warning("Failed to bring window to foreground %d: %s", hwnd, str(e))
                    except Exception as e:
                        logger.error("Unexpected error bringing window to foreground %d: %s", hwnd, str(e))

                    # 更新窗口状态
                    win_info.state = WindowState.NORMAL
                    win_info.is_visible = True
                    logger.info("Successfully shown window: %d - %s", hwnd, win_info.title)
                    return True
                else:
                    logger.warning("Failed to show window: %d - %s", hwnd, win_info.title)
                    return False

            except OSError as e:
                logger.error("OS error showing window %d: %s", hwnd, str(e))
                return False
            except Exception as e:
                logger.error("Unexpected error showing window %d: %s", hwnd, str(e))
                return False

    def show_and_minimize_window(self, hwnd: int) -> bool:
        """
        显示指定的窗口，然后立即最小化到任务栏

        Args:
            hwnd: 窗口句柄

        Returns:
            bool: 操作成功返回True，否则返回False
        """
        with self._lock:
            try:
                # 首先验证窗口是否仍然有效
                if not SafeWindowsAPI.is_window(hwnd):
                    logger.warning("Window %d is no longer valid, cannot show and minimize", hwnd)
                    # 清理无效窗口的引用
                    if hwnd in self._hidden_windows:
                        del self._hidden_windows[hwnd]
                    if hwnd in self._windows:
                        del self._windows[hwnd]
                    return False

                # 获取或创建窗口信息
                win_info = self._get_or_create_window_info(hwnd)

                # 先显示窗口（SW_SHOW = 5）
                if not SafeWindowsAPI.show_window(hwnd, 5):
                    logger.warning("Failed to show window before minimize: %d - %s", hwnd, win_info.title)
                    return False

                # 立即最小化窗口（SW_MINIMIZE = 2）
                if SafeWindowsAPI.show_window(hwnd, 2):
                    # 更新窗口状态
                    win_info.state = WindowState.NORMAL
                    win_info.is_visible = True
                    logger.info("Successfully shown and minimized window: %d - %s", hwnd, win_info.title)
                    return True
                else:
                    logger.warning("Failed to minimize window: %d - %s", hwnd, win_info.title)
                    return False

            except OSError as e:
                logger.error("OS error showing and minimizing window %d: %s", hwnd, str(e))
                return False
            except Exception as e:
                logger.error("Unexpected error showing and minimizing window %d: %s", hwnd, str(e))
                return False

    def _get_or_create_window_info(self, hwnd: int) -> WindowInfo:
        """获取或创建窗口信息"""
        # 检查窗口是否在隐藏列表中
        if hwnd in self._hidden_windows:
            win_info = self._hidden_windows[hwnd]
            # 从隐藏列表中移除
            del self._hidden_windows[hwnd]
            return win_info
        elif hwnd in self._windows:
            return self._windows[hwnd]
        else:
            # 创建新的窗口信息
            return self._create_window_info(hwnd)

    def _create_window_info(self, hwnd: int) -> WindowInfo:
        """创建新的窗口信息"""
        title = SafeWindowsAPI.get_window_text(hwnd)
        class_name = SafeWindowsAPI.get_window_class(hwnd)
        _, pid = SafeWindowsAPI.get_window_thread_process_id(hwnd)
        is_visible = SafeWindowsAPI.is_window_visible(hwnd)
        process_name = SafeWindowsAPI.get_process_name(pid)

        win_info = WindowInfo(
            hwnd=hwnd,
            title=title,
            class_name=class_name,
            pid=pid,
            state=WindowState.NORMAL,
            is_visible=is_visible,
            process_name=process_name
        )
        self._windows[hwnd] = win_info
        return win_info

    def _update_window_state(self, win_info: WindowInfo, state: WindowState, is_visible: bool):
        """更新窗口状态"""
        win_info.state = state
        win_info.is_visible = is_visible

    def hide_windows(self, hwnds: List[int]) -> int:
        count = 0
        for hwnd in hwnds:
            if self.hide_window(hwnd):
                count += 1
        return count

    def show_windows(self, hwnds: List[int]) -> int:
        count = 0
        for hwnd in hwnds:
            if self.show_window(hwnd):
                count += 1
        return count

    def show_all_hidden(self) -> int:
        with self._lock:
            # 获取所有隐藏窗口的句柄
            hwnds = list(self._hidden_windows.keys())

            if not hwnds:
                return 0

            # 显示所有隐藏窗口
            count = 0
            for hwnd in hwnds:
                if self.show_window(hwnd):
                    count += 1

            logger.info("Shown %d hidden windows", count)
            return count

    def get_hidden_windows(self) -> List[WindowInfo]:
        with self._lock:
            return list(self._hidden_windows.values())
