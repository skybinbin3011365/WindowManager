# windowmanager/process_detector.py
"""
进程检测模块

负责进程检测、前台窗口检测、后台进程检测等功能
"""

import logging
import threading
from typing import Dict, List, Set, Tuple

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False

try:
    import win32gui
    WIN32GUI_AVAILABLE = True
except ImportError:
    win32gui = None
    WIN32GUI_AVAILABLE = False
import win32process
import core
from config import ConfigManager
from window_base import WindowState, WindowInfo
from constants import WindowConstants

SafeWindowsAPI = core.SafeWindowsAPI
logger = logging.getLogger(__name__)


class ProcessDetector:
    """进程检测器类
    
    负责进程检测、前台窗口检测、后台进程检测等功能
    """
    
    def __init__(self):
        """初始化进程检测器"""
        self._lock = threading.RLock()
        self._blacklist_processes: Set[str] = set()
        self._foreground_cache: Dict[str, List[WindowInfo]] = {}
        self._last_all_pids: Set[int] = set()
        self._keyword_process_map: Dict[str, Set[str]] = {}
        self._process_keyword_map: Dict[str, Set[str]] = {}
        self._hidden_windows: Dict[int, WindowInfo] = {}
    
    def set_data_stores(
        self,
        blacklist_processes: Set[str],
        foreground_cache: Dict[str, List[WindowInfo]],
        hidden_windows: Dict[int, WindowInfo]
    ) -> None:
        """设置数据存储引用
        
        Args:
            blacklist_processes: 黑名单进程集合
            foreground_cache: 前台缓存字典
            hidden_windows: 隐藏窗口字典
        """
        self._blacklist_processes = blacklist_processes
        self._foreground_cache = foreground_cache
        self._hidden_windows = hidden_windows
    
    def check_background_processes(self, keywords: List[str]) -> List[WindowInfo]:
        """检查后台运行的特定进程，只检测与关键字相关的进程
        
        Args:
            keywords: 关键字列表
        
        Returns:
            List[WindowInfo]: 匹配的后台进程占位窗口列表
        """
        if not keywords:
            return []
        
        background_windows = []
        try:
            existing_pids = self._get_existing_pids()
            target_process_names = self._resolve_keywords_to_process_names(keywords)
            
            if not target_process_names:
                return []
            
            all_processes = self._get_all_process_info()
            background_windows = self._find_matching_background_processes(
                all_processes, target_process_names, existing_pids, keywords
            )
        
        except Exception as e:
            logger.warning("检查后台进程失败: %s", str(e))
        
        return background_windows
    
    def _get_existing_pids(self) -> Set[int]:
        """获取当前所有窗口的PID集合，用于排除已有窗口的进程
        
        Returns:
            Set[int]: 现有窗口的PID集合
        """
        existing_pids = set()
        for window in list(self._hidden_windows.values()):
            if window.pid > 0:
                existing_pids.add(window.pid)
        return existing_pids
    
    def _resolve_keywords_to_process_names(self, keywords: List[str]) -> List[str]:
        """根据关键字推断要检测的进程名

        Args:
            keywords: 关键字列表

        Returns:
            List[str]: 目标进程名列表（关键字→进程名 + auto_select_processes）
        """
        try:
            config_manager = ConfigManager.get_instance()
            config = config_manager.load()
            auto_select = config.auto_select_processes if config else []
        except Exception:
            auto_select = []

        target_process_names = list(auto_select)
        for keyword in keywords:
            target_process_names.append(f"{keyword.lower()}.exe")

        return list(set(target_process_names))
    
    def _get_all_process_info(self) -> Dict[int, dict]:
        """获取所有运行中的进程信息
        
        Returns:
            Dict[int, dict]: PID到进程信息的映射字典
        """
        all_processes = {}
        if PSUTIL_AVAILABLE and psutil is not None:
            for process in psutil.process_iter(["pid", "name"]):
                try:
                    all_processes[process.info["pid"]] = process.info
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        return all_processes
    
    def _find_matching_background_processes(
        self,
        all_processes: Dict[int, dict],
        target_process_names: List[str],
        existing_pids: Set[int],
        keywords: List[str] = None
    ) -> List[WindowInfo]:
        """在所有进程中查找匹配的后台进程，直接使用真实窗口句柄
        
        Args:
            all_processes: 所有进程信息
            target_process_names: 目标进程名列表
            existing_pids: 已有窗口的PID集合
            keywords: 关键字列表（用于标题筛选）
        
        Returns:
            List[WindowInfo]: 匹配的后台进程窗口列表（包含真实句柄）
        """
        background_windows = []
        
        for pid, process_info in all_processes.items():
            process_name = process_info["name"].lower()
            is_target = self._is_process_target(process_name, target_process_names)
            
            if is_target:
                # 直接枚举该进程的所有真实窗口句柄
                process_windows = self._find_windows_by_pid(pid)
                
                if process_windows:
                    # 使用真实窗口句柄
                    for hwnd, title in process_windows:
                        # 检查标题是否包含关键字
                        if keywords and not self._is_title_matching_keywords(title, keywords):
                            logger.debug(
                                "窗口标题 '%s' 不包含关键字，跳过: HWND=%d",
                                title,
                                hwnd,
                            )
                            # 如果该窗口已在隐藏列表中，移除它
                            if hwnd in self._hidden_windows:
                                del self._hidden_windows[hwnd]
                                logger.debug("已从隐藏列表移除不匹配的窗口: %d - %s", hwnd, title)
                            continue
                            
                        if hwnd not in self._hidden_windows:
                            window_info = SafeWindowsAPI.create_window_info(
                                hwnd,
                                title=title,
                                pid=pid,
                                state=WindowState.HIDDEN,
                                is_visible=False,
                                process_name=process_info["name"],
                                is_foreground=False,
                                is_taskbar=False,
                            )
                            self._hidden_windows[hwnd] = window_info
                            background_windows.append(window_info)
                            logger.debug(
                                "检测到后台运行的目标进程窗口: %d - %s (PID: %d)",
                                hwnd,
                                title,
                                pid,
                            )
                elif pid not in existing_pids:
                    # 如果没有找到真实窗口，创建占位窗口作为后备
                    window_info = self._create_background_process_window(
                        process_info, len(background_windows)
                    )
                    self._hidden_windows[window_info.hwnd] = window_info
                    background_windows.append(window_info)
                    logger.debug(
                        "检测到后台运行的目标进程(无窗口): %s (PID: %d)",
                        process_info["name"],
                        process_info["pid"],
                    )
        
        return background_windows
    
    def _find_windows_by_pid(self, pid: int) -> List[tuple]:
        """根据PID查找所有真实窗口句柄
        
        Args:
            pid: 进程ID
        
        Returns:
            List[tuple]: (hwnd, title) 列表
        """
        result = []
        
        def callback(hwnd, extra):
            try:
                if not SafeWindowsAPI.is_window(hwnd):
                    return True
                
                _, curr_pid = SafeWindowsAPI.get_window_thread_process_id(hwnd)
                if curr_pid != pid:
                    return True
                
                title = SafeWindowsAPI.get_window_text(hwnd).strip()
                if title:
                    result.append((hwnd, title))
            except Exception:
                pass
            return True
        
        if WIN32GUI_AVAILABLE and win32gui is not None:
            win32gui.EnumWindows(callback, None)
        
        return result
    
    def _is_process_target(self, process_name: str, target_process_names: List[str]) -> bool:
        """检查进程是否是目标进程
        
        Args:
            process_name: 进程名
            target_process_names: 目标进程名列表
        
        Returns:
            bool: 是否是目标进程
        """
        for target_name in target_process_names:
            if target_name.lower() in process_name:
                return True
        return False
    
    def _is_title_matching_keywords(self, title: str, keywords: List[str]) -> bool:
        """检查窗口标题是否包含任何关键字
        
        Args:
            title: 窗口标题
            keywords: 关键字列表
        
        Returns:
            bool: 标题是否包含任何关键字
        """
        if not title or not keywords:
            return False
        
        title_lower = title.lower()
        for keyword in keywords:
            if keyword.lower() in title_lower:
                return True
        return False
    
    def _create_background_process_window(self, process_info: dict, index: int) -> WindowInfo:
        """创建后台进程的占位窗口信息
        
        Args:
            process_info: 进程信息
            index: 窗口索引（用于生成占位句柄）
        
        Returns:
            WindowInfo: 窗口信息对象
        """
        hwnd = self._generate_placeholder_hwnd(index)
        process_name = process_info["name"].lower()
        title = f"[后台] {process_info['name']}"
        
        return SafeWindowsAPI.create_window_info(
            hwnd,
            title=title,
            class_name="BACKGROUND_PROCESS",
            pid=process_info["pid"],
            state=WindowState.HIDDEN,
            is_visible=False,
            process_name=process_info["name"],
            is_foreground=False,
        )
    
    def _generate_placeholder_hwnd(self, index: int) -> int:
        """生成后台进程占位窗口的句柄（负数表示占位符）
        
        Args:
            index: 索引值
        
        Returns:
            int: 占位窗口句柄
        """
        return WindowConstants.BACKGROUND_PROCESS_HWND_OFFSET * (index + 1)
    
    def is_process_foreground(
        self, pid: int, process_name: str
    ) -> Tuple[bool, List[int]]:
        """检测单个进程的所有可见窗口（前台应用）
        比全量枚举快 10~100 倍
        
        Args:
            pid: 进程ID
            process_name: 进程名
        
        Returns:
            Tuple[bool, List[int]]:
                - 第一个元素：是否找到该进程的可见窗口
                - 第二个元素：找到的窗口句柄列表
        """
        result = []
        
        def callback(hwnd, _):
            try:
                if not SafeWindowsAPI.is_window(hwnd):
                    return True
                
                try:
                    _, curr_pid = SafeWindowsAPI.get_window_thread_process_id(hwnd)
                    if curr_pid != pid:
                        return True
                except Exception:
                    return True
                
                try:
                    title = SafeWindowsAPI.get_window_text(hwnd).strip()
                    if not title:
                        return True
                except Exception:
                    return True
                
                try:
                    if SafeWindowsAPI.window_has_visible_style(hwnd):
                        result.append(hwnd)
                except Exception:
                    pass
            except Exception:
                pass
            return True
        
        try:
            win32gui.EnumWindows(callback, None)
            return (len(result) > 0, result)
        except Exception:
            return (False, [])
    
    def find_visible_windows_by_process_name(self, process_name: str) -> List[int]:
        """通过进程名查找有可见窗口的句柄（只返回有实际窗口内容的句柄）

        过滤掉没有可见内容的窗口句柄，比如：
        - 子窗口（非顶级窗口）
        - 窗口大小为0的窗口
        - IsWindowVisible返回False的窗口

        Args:
            process_name: 进程名

        Returns:
            List[int]: 有可见窗口的句柄列表
        """
        return self._enumerate_windows_by_process_name(process_name, visible_only=True)

    def find_all_windows_by_process_name(self, process_name: str) -> List[int]:
        """通过进程名查找所有窗口句柄（包括隐藏窗口）

        Args:
            process_name: 进程名

        Returns:
            List[int]: 窗口句柄列表
        """
        return self._enumerate_windows_by_process_name(process_name, visible_only=False)

    def _enumerate_windows_by_process_name(
        self, process_name: str, visible_only: bool = False
    ) -> List[int]:
        """通过进程名枚举窗口句柄（公共实现）

        Args:
            process_name: 进程名
            visible_only: 是否只返回可见窗口

        Returns:
            List[int]: 窗口句柄列表
        """
        hwnds = []
        if not PSUTIL_AVAILABLE or psutil is None:
            return hwnds

        target_pid = None
        for process in psutil.process_iter(["pid", "name"]):
            try:
                if process.info["name"].lower() == process_name.lower():
                    target_pid = process.info["pid"]
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if not target_pid:
            return hwnds

        def callback(hwnd, extra):
            try:
                if win32gui.GetParent(hwnd) != 0:
                    return True

                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid != target_pid:
                    return True

                if visible_only and not win32gui.IsWindowVisible(hwnd):
                    return True

                rect = win32gui.GetWindowRect(hwnd)
                width = rect[2] - rect[0]
                height = rect[3] - rect[1]
                if width <= 0 or height <= 0:
                    return True

                title = win32gui.GetWindowText(hwnd)
                if not title:
                    return True

                hwnds.append(hwnd)
            except Exception:
                pass
            return True

        win32gui.EnumWindows(callback, None)
        return hwnds
    
    def get_windows_by_process_name_with_screen_info(
        self, process_name: str
    ) -> List[dict]:
        """根据进程名获取窗口信息，包括是否在主显示器
        
        Args:
            process_name: 进程名
        
        Returns:
            List[dict]: 每项包含 hwnd, title, is_primary
        """
        result = []
        if not PSUTIL_AVAILABLE or psutil is None:
            return result
        
        pid_set = set()
        
        for proc in psutil.process_iter(["name", "pid"]):
            try:
                if (
                    proc.info["name"]
                    and proc.info["name"].lower() == process_name.lower()
                ):
                    pid_set.add(proc.info["pid"])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        def enum_windows_callback(hwnd, _):
            try:
                pid = win32process.GetWindowThreadProcessId(hwnd)[1]
                if pid in pid_set and win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    is_primary = SafeWindowsAPI.is_hwnd_on_primary_screen(hwnd)
                    result.append(
                        {"hwnd": hwnd, "title": title, "is_primary": is_primary}
                    )
            except Exception:
                pass
            return True
        
        win32gui.EnumWindows(enum_windows_callback, None)
        return result
