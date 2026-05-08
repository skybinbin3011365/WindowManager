# windowmanager/manager.py
"""
窗口管理器模块

协调窗口操作、进程检测和缓存管理功能
"""

import threading
import logging
from typing import Dict, List, Optional, Set

from window_base import WindowState, WindowInfo
from window_operations import WindowOperator
from process_detector import ProcessDetector
from cache_manager import CacheManager

logger = logging.getLogger(__name__)


class WindowManager:
    """窗口管理器类
    
    协调窗口操作、进程检测和缓存管理功能
    """
    
    def __init__(self):
        """初始化窗口管理器"""
        self._lock = threading.RLock()
        
        self._windows: Dict[int, WindowInfo] = {}
        self._hidden_windows: Dict[int, WindowInfo] = {}
        self._software_hidden_windows: Set[int] = set()
        self._running: bool = False
        
        self._cache_manager = CacheManager()
        self._window_operator = WindowOperator()
        self._process_detector = ProcessDetector()
        
        self._setup_data_references()
        
        self._cache_manager.load_cache()
        self._cache_manager.init_blacklist()
    
    def _setup_data_references(self) -> None:
        """设置数据引用，让子模块共享数据存储"""
        self._window_operator.set_data_stores(
            self._windows,
            self._hidden_windows,
            self._software_hidden_windows
        )
        self._process_detector.set_data_stores(
            self._cache_manager.get_blacklist(),
            {},
            self._hidden_windows
        )
    
    @property
    def is_running(self) -> bool:
        """检查窗口管理器是否正在运行
        
        Returns:
            bool: 运行状态
        """
        return self._running
    
    @property
    def windows(self) -> List[WindowInfo]:
        """获取所有窗口列表（只读）
        
        Returns:
            List[WindowInfo]: 窗口信息列表
        """
        with self._lock:
            return list(self._windows.values())
    
    def init_cache(self) -> None:
        """初始化缓存（向后兼容方法）"""
        self._cache_manager.init_cache(self._windows)
    
    def start(self) -> None:
        """启动窗口管理器"""
        self._running = True
        self.init_cache()
        self.refresh_windows()
        logger.info("窗口管理器已启动")
    
    def stop(self) -> None:
        """停止窗口管理器"""
        self._running = False
        logger.info("窗口管理器已停止")
    
    def refresh_windows(self) -> List[WindowInfo]:
        """刷新窗口列表

        Returns:
            List[WindowInfo]: 窗口信息列表
        """
        from core import SafeWindowsAPI
        
        with self._lock:
            foreground_windows = self.incremental_detect()
            foreground_hwnd = SafeWindowsAPI.get_foreground_window()
            
            foreground_hwnds = {win.hwnd for win in foreground_windows}
            previous_hwnds = set(self._windows.keys()) | set(self._hidden_windows.keys())
            
            added_hwnds = foreground_hwnds - previous_hwnds
            removed_hwnds = previous_hwnds - foreground_hwnds
            
            for hwnd in removed_hwnds:
                # 对于被软件隐藏的窗口，保留其信息
                if hwnd in self._software_hidden_windows:
                    window = self._hidden_windows.get(hwnd)
                    if window and window.pid:
                        try:
                            import psutil
                            if psutil.pid_exists(window.pid):
                                # 进程仍在运行，保留窗口信息
                                continue
                        except Exception:
                            pass
                    # 进程不存在，移除被软件隐藏的窗口
                    logger.debug("进程不存在，移除被软件隐藏的窗口: %d", hwnd)
                    if hwnd in self._software_hidden_windows:
                        self._software_hidden_windows.remove(hwnd)
                    if hwnd in self._hidden_windows:
                        del self._hidden_windows[hwnd]
                else:
                    # 不是被软件隐藏的窗口，正常删除
                    if hwnd in self._windows:
                        del self._windows[hwnd]
                    if hwnd in self._hidden_windows:
                        del self._hidden_windows[hwnd]
            
            for win in foreground_windows:
                if win.hwnd in added_hwnds:
                    self._add_new_window(win.hwnd, foreground_hwnd)
                else:
                    self._window_operator.update_window_state(win.hwnd, foreground_hwnd)
            
            logger.info(
                "已刷新 %d 个窗口, %d 个隐藏",
                len(self._windows),
                len(self._hidden_windows),
            )
            return list(self._windows.values())
    
    def _add_new_window(self, hwnd: int, foreground_hwnd: int) -> None:
        """添加新窗口
        
        Args:
            hwnd: 窗口句柄
            foreground_hwnd: 前台窗口句柄
        """
        from core import SafeWindowsAPI
        from window_base import WindowState
        
        try:
            title = SafeWindowsAPI.get_window_text(hwnd)
            class_name = SafeWindowsAPI.get_window_class(hwnd)
            is_visible = SafeWindowsAPI.window_has_visible_style(hwnd)
            
            _, pid = SafeWindowsAPI.get_window_thread_process_id(hwnd)
            process_name = SafeWindowsAPI.get_process_name(pid)
            
            if is_visible:
                state = WindowState.NORMAL
                placement = SafeWindowsAPI.get_window_placement(hwnd)
                from core import win32con
                if placement and placement[0] == win32con.SW_SHOWMINIMIZED:
                    state = WindowState.MINIMIZED
                
                monitor = SafeWindowsAPI.get_window_monitor(hwnd)
                monitor_id = monitor.monitor_id if monitor else None
                if monitor:
                    monitor_name = "主显" if monitor.is_primary else "副显"
                else:
                    monitor_name = "未知显示器"
                
                win_info = SafeWindowsAPI.create_window_info(
                    hwnd,
                    title=title,
                    class_name=class_name,
                    pid=pid,
                    state=state,
                    is_visible=True,
                    process_name=process_name,
                    is_foreground=(hwnd == foreground_hwnd),
                    monitor_id=monitor_id,
                    monitor_name=monitor_name,
                )
                self._windows[hwnd] = win_info
            else:
                win_info = SafeWindowsAPI.create_window_info(
                    hwnd,
                    title=title,
                    class_name=class_name,
                    pid=pid,
                    state=WindowState.HIDDEN,
                    is_visible=False,
                    process_name=process_name,
                    is_foreground=False,
                    monitor_id=None,
                    monitor_name="未知显示器",
                )
                self._hidden_windows[hwnd] = win_info
        except Exception as e:
            logger.debug("获取窗口 %d 信息失败: %s", hwnd, str(e))
    
    def incremental_detect(self) -> List[WindowInfo]:
        """增量检测：只检测新增/变化的进程，避免全量扫描

        Win32 API 调用（EnumWindows）在锁外执行，避免长时间持锁阻塞其他线程。

        Returns:
            List[WindowInfo]: 前台窗口列表
        """
        import psutil

        foreground_windows: List[WindowInfo] = []

        try:
            all_procs = list(psutil.process_iter(["pid", "name"]))
            current_pids: Set[int] = {p.info["pid"] for p in all_procs}
        except Exception as e:
            logger.warning("获取进程列表失败：%s", e)
            return foreground_windows

        new_pids = current_pids - self._cache_manager._last_all_pids
        blacklist = self._cache_manager.get_blacklist()
        hidden_hwnds = set(self._hidden_windows.keys())

        for proc in all_procs:
            try:
                pname = proc.info["name"].lower()
                pid = proc.info["pid"]

                if pid not in new_pids and pname in blacklist:
                    continue

                is_fore, hwnds = self._process_detector.is_process_foreground(pid, pname)

                if not is_fore:
                    continue

                for hwnd in hwnds:
                    if hwnd in hidden_hwnds:
                        continue

                    existing = self._windows.get(hwnd)
                    if existing and existing.process_name.lower() == pname:
                        foreground_windows.append(existing)
                        continue

                    try:
                        win_info = self._create_window_info(hwnd, pid, proc.info["name"])
                        foreground_windows.append(win_info)
                    except Exception as e:
                        logger.debug("创建窗口信息失败: %s", e)

            except Exception:
                continue

        # 只在锁内更新缓存状态（极快操作）
        with self._lock:
            self._cache_manager._last_all_pids = current_pids

        return foreground_windows
    
    def _create_window_info(self, hwnd: int, pid: int, name: str) -> "WindowInfo":
        """创建窗口信息对象

        Args:
            hwnd: 窗口句柄
            pid: 进程ID
            name: 进程名

        Returns:
            WindowInfo: 窗口信息对象
        """
        from core import SafeWindowsAPI
        
        title = SafeWindowsAPI.get_window_text(hwnd)
        class_name = SafeWindowsAPI.get_window_class(hwnd)
        return SafeWindowsAPI.create_window_info(
            hwnd,
            title=title,
            class_name=class_name,
            pid=pid,
            state=WindowState.NORMAL,
            is_visible=True,
            process_name=name,
            is_foreground=False,
        )
    
    def get_all_windows(self) -> List[WindowInfo]:
        """获取所有窗口列表
        
        Returns:
            List[WindowInfo]: 窗口信息列表（包括可见和隐藏的窗口）
        """
        with self._lock:
            all_windows = list(self._windows.values()) + list(self._hidden_windows.values())
            return all_windows
    
    def get_window(self, hwnd: int) -> Optional[WindowInfo]:
        """获取指定窗口信息
        
        Args:
            hwnd: 窗口句柄
        
        Returns:
            Optional[WindowInfo]: 窗口信息对象或None
        """
        with self._lock:
            return self._windows.get(hwnd) or self._hidden_windows.get(hwnd)
    
    def get_hidden_windows(self) -> List[WindowInfo]:
        """获取被软件隐藏的窗口列表
        
        Returns:
            List[WindowInfo]: 隐藏窗口列表
        """
        with self._lock:
            return [
                self._hidden_windows[hwnd]
                for hwnd in self._software_hidden_windows
                if hwnd in self._hidden_windows
            ]
    
    def set_software_hidden_windows(self, hwnds: List[int]) -> None:
        """设置被软件隐藏的窗口列表
        
        Args:
            hwnds: 窗口句柄列表
        """
        with self._lock:
            self._software_hidden_windows = set(hwnds)
    
    def get_software_hidden_windows(self) -> List[int]:
        """获取被软件隐藏的窗口列表
        
        Returns:
            List[int]: 窗口句柄列表
        """
        with self._lock:
            return list(self._software_hidden_windows)
    
    def hide_window(self, hwnd: int) -> bool:
        """隐藏指定的窗口
        
        Args:
            hwnd: 窗口句柄
        
        Returns:
            bool: 隐藏成功返回True，否则返回False
        """
        return self._window_operator.hide_window(hwnd)
    
    def show_window(self, hwnd: int) -> bool:
        """显示指定的窗口
        
        Args:
            hwnd: 窗口句柄
        
        Returns:
            bool: 显示成功返回True，否则返回False
        """
        return self._window_operator.show_window(hwnd)
    
    def show_and_minimize_window(self, hwnd: int) -> bool:
        """显示并最小化指定窗口
        
        Args:
            hwnd: 窗口句柄
        
        Returns:
            bool: 操作成功返回True，否则返回False
        """
        return self._window_operator.show_and_minimize_window(hwnd)
    
    def show_all_hidden_windows(self) -> int:
        """显示所有被软件隐藏的窗口
        
        Returns:
            int: 成功显示的窗口数量
        """
        return self._window_operator.show_all_hidden_windows()
    
    def show_selected_hidden_windows(self, hwnds: List[int]) -> int:
        """显示选中的隐藏窗口
        
        Args:
            hwnds: 要显示的窗口句柄列表
        
        Returns:
            int: 成功显示的窗口数量
        """
        return self._window_operator.show_selected_hidden_windows(hwnds)
    
    def show_and_minimize_selected_hidden_windows(self, hwnds: List[int]) -> int:
        """显示并最小化选中的隐藏窗口
        
        Args:
            hwnds: 要显示的窗口句柄列表
        
        Returns:
            int: 成功显示的窗口数量
        """
        return self._window_operator.show_and_minimize_selected_hidden_windows(hwnds)
    
    def restore_windows_by_process(self, process_name: str) -> List[int]:
        """恢复指定进程的所有隐藏窗口
        
        Args:
            process_name: 进程名，如 "book.exe"
        
        Returns:
            List[int]: 成功恢复的窗口句柄列表
        """
        with self._lock:
            restored_hwnds = []
            
            for hwnd in list(self._software_hidden_windows):
                window = self._hidden_windows.get(hwnd)
                if window and window.process_name == process_name:
                    try:
                        self.show_window(hwnd)
                        restored_hwnds.append(hwnd)
                        logger.info(
                            "恢复进程 %s 的窗口：%d - %s",
                            process_name,
                            hwnd,
                            window.title,
                        )
                    except Exception as e:
                        logger.error("恢复窗口失败 %d: %s", hwnd, str(e))
            
            return restored_hwnds
    
    def check_background_processes(self, keywords: List[str]) -> List[WindowInfo]:
        """检查后台运行的特定进程
        
        Args:
            keywords: 关键字列表
        
        Returns:
            List[WindowInfo]: 匹配的后台进程占位窗口列表
        """
        return self._process_detector.check_background_processes(keywords)
    
    def recover_hidden_windows(self, keywords: List[str]) -> List[WindowInfo]:
        """检测并恢复被隐藏的窗口（向后兼容方法）
        
        Args:
            keywords: 关键字列表
        
        Returns:
            List[WindowInfo]: 匹配的隐藏窗口列表
        """
        return self._process_detector.check_background_processes(keywords)
    
    def is_process_foreground(self, pid: int, process_name: str) -> tuple[bool, list[int]]:
        """检测单个进程的所有可见窗口
        
        Args:
            pid: 进程ID
            process_name: 进程名
        
        Returns:
            tuple[bool, list[int]]:
                - 第一个元素：是否找到该进程的可见窗口
                - 第二个元素：找到的窗口句柄列表
        """
        return self._process_detector.is_process_foreground(pid, process_name)
    
    def find_visible_windows_by_process_name(self, process_name: str) -> List[int]:
        """通过进程名查找有可见窗口的句柄
        
        Args:
            process_name: 进程名
        
        Returns:
            List[int]: 有可见窗口的句柄列表
        """
        return self._process_detector.find_visible_windows_by_process_name(process_name)
    
    def find_all_windows_by_process_name(self, process_name: str) -> List[int]:
        """通过进程名查找所有窗口句柄（包括隐藏窗口）

        Args:
            process_name: 进程名

        Returns:
            List[int]: 窗口句柄列表
        """
        return self._process_detector.find_all_windows_by_process_name(process_name)

    def show_windows_by_process_name(self, process_name: str) -> int:
        """根据进程名显示并最小化所有窗口

        Args:
            process_name: 进程名

        Returns:
            int: 成功显示的窗口数量
        """
        hwnds = self.find_all_windows_by_process_name(process_name)
        if not hwnds:
            return 0

        count = 0
        for hwnd in hwnds:
            if self.show_and_minimize_window(hwnd):
                count += 1
        return count

    def get_windows_by_process_name_with_screen_info(
        self, process_name: str
    ) -> List[dict]:
        """根据进程名获取窗口信息，包括是否在主显示器
        
        Args:
            process_name: 进程名
        
        Returns:
            List[dict]: 每项包含 hwnd, title, is_primary
        """
        return self._process_detector.get_windows_by_process_name_with_screen_info(process_name)
    
    def save_cache(self) -> None:
        """保存缓存"""
        self._cache_manager.save_cache()
    
    def get_blacklist(self) -> Set[str]:
        """获取黑名单（向后兼容方法）
        
        Returns:
            Set[str]: 黑名单进程名集合
        """
        return self._cache_manager.get_blacklist()
    
    def get_whitelist(self) -> list:
        """获取白名单（向后兼容方法）
        
        Returns:
            list: 白名单进程列表
        """
        from config import ConfigManager
        config_manager = ConfigManager.get_instance()
        config = config_manager.load()
        if config:
            return config.process_whitelist
        return []
    
    def add_to_blacklist(self, process_name: str) -> None:
        """添加进程到黑名单
        
        Args:
            process_name: 进程名
        """
        self._cache_manager.add_to_blacklist(process_name)
    
    def remove_from_blacklist(self, process_name: str) -> bool:
        """从黑名单移除进程
        
        Args:
            process_name: 进程名
        
        Returns:
            bool: 是否成功移除
        """
        return self._cache_manager.remove_from_blacklist(process_name)
    
    def is_blacklisted(self, process_name: str) -> bool:
        """检查进程是否在黑名单中
        
        Args:
            process_name: 进程名
        
        Returns:
            bool: 是否在黑名单中
        """
        return self._cache_manager.is_blacklisted(process_name)
