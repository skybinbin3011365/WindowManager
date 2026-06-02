# -*- coding: utf-8 -*-
# windowmanager/process_detector.py
"""
进程检测模块

负责进程检测、前台窗口检测、后台进程检测等功能
"""

import logging
from typing import Dict, List, Optional, Set, Tuple

from deps import PSUTIL_AVAILABLE, psutil, WIN32GUI_AVAILABLE, win32gui, win32con, win32process
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

    # 非用户窗口类名前缀（从 WindowConstants 引入，保持向后兼容）
    _NON_USER_CLASS_PREFIXES = WindowConstants.NON_USER_CLASS_PREFIXES

    def __init__(self):
        """初始化进程检测器"""
        self._hidden_windows: Dict[int, WindowInfo] = {}

    def set_data_stores(
        self, _windows: Optional[Dict] = None, hidden_windows: Optional[Dict[int, WindowInfo]] = None
    ) -> None:
        """设置数据存储引用（由 WindowManager 调用）

        Args:
            windows: 可见窗口字典（未使用但保留接口兼容）
            hidden_windows: 隐藏窗口字典
        """
        if hidden_windows is not None:
            self._hidden_windows = hidden_windows

    def detect_target_windows(self, keywords: List[str]) -> List[WindowInfo]:
        """检测与关键字相关的目标进程窗口

        Args:
            keywords: 关键字列表

        Returns:
            List[WindowInfo]: 匹配的目标进程窗口列表
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
            background_windows = self._detect_and_register_background_processes(
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
            auto_select = config.filter.auto_select_processes if config else []
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

    def _detect_and_register_background_processes(
        self,
        all_processes: Dict[int, dict],
        target_process_names: List[str],
        existing_pids: Set[int],
        keywords: Optional[List[str]] = None
    ) -> List[WindowInfo]:
        """在所有进程中查找匹配的后台进程

        Args:
            all_processes: 所有进程信息
            target_process_names: 目标进程名列表
            existing_pids: 已有窗口的 PID 集合
            keywords: 关键字列表（用于标题筛选）

        Returns:
            List[WindowInfo]: 匹配的后台进程窗口列表
        """
        # 单次枚举完成所有过滤
        background_windows, hit_pids = self._detect_and_track_target_windows_once(
            all_processes, target_process_names, keywords
        )

        # 对没有窗口但进程存在的目标 PID，补充占位窗口
        for pid, process_info in all_processes.items():
            if pid in hit_pids:
                continue
            if not self._is_process_target(process_info["name"].lower(), target_process_names):
                continue
            if pid not in existing_pids:
                window_info = self._create_background_process_window(
                    process_info, len(background_windows)
                )
                self._hidden_windows[window_info.hwnd] = window_info
                background_windows.append(window_info)
                logger.debug(
                    "检测到后台运行的目标进程(无窗口): %s (PID: %d)",
                    process_info["name"],
                    pid,
                )

        return background_windows

    def _detect_and_track_target_windows_once(
        self,
        all_processes: Dict[int, dict],
        target_process_names: List[str],
        keywords: Optional[List[str]] = None
    ) -> Tuple[List[WindowInfo], Set[int]]:
        """单次枚举所有目标窗口（一次 EnumWindows 完成所有过滤）

        过滤链：
        1. 子窗口（有父窗口的 HWND）
        2. 无标题窗口
        3. 非用户窗口（窗口类名以特定前缀开头）
        4. 工具窗口（WS_EX_TOOLWINDOW）
        5. 极小窗口（宽或高 < 30px）
        6. PID 不在目标进程列表
        7. 标题不含关键字

        Args:
            all_processes: 所有进程信息 {pid: {name, ...}}
            target_process_names: 目标进程名列表
            keywords: 关键字列表（用于标题筛选）

        Returns:
            Tuple[List[WindowInfo], Set[int]]:
                - 匹配的后台进程窗口列表
                - 本次枚举中命中目标 PID 的集合（用于后续判断无窗口进程）
        """
        background_windows: List[WindowInfo] = []
        hit_pids: Set[int] = set()
        # 记录每个PID已找到的VW句柄（规划要求：每个进程只取一个VW）
        found_hwnd_per_pid: Dict[int, int] = {}
        # P0-8 修复: 回调中收集待删除的 hwnd，回调外统一处理
        # 不再在回调中直接 pop _hidden_windows（避免迭代异常和误删其他来源数据）
        hwnds_to_remove: Set[int] = set()

        # 构建 {pid: process_info} 映射（只包含目标进程）
        target_pid_map: Dict[int, dict] = {}
        for pid, process_info in all_processes.items():
            if self._is_process_target(process_info["name"].lower(), target_process_names):
                target_pid_map[pid] = process_info

        if not target_pid_map:
            return [], set()

        def callback(hwnd, _extra):
            try:
                # 1. 必须是顶级窗口（无父窗口）
                if win32gui.GetParent(hwnd) != 0:
                    return True

                # 2. 窗口必须有效
                if not SafeWindowsAPI.is_window(hwnd):
                    return True

                # 3. 必须有标题
                title = SafeWindowsAPI.get_window_text(hwnd).strip()
                if not title:
                    return True

                # 4. 过滤非用户窗口
                try:
                    class_name = win32gui.GetClassName(hwnd)
                    if any(class_name.startswith(prefix) for prefix in self._NON_USER_CLASS_PREFIXES):
                        return True
                except Exception:
                    pass

                # 5. 过滤工具窗口
                try:
                    exstyle = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                    if exstyle & win32con.WS_EX_TOOLWINDOW:
                        return True
                except Exception:
                    pass

                # 6. 过滤极小窗口
                try:
                    rect = win32gui.GetWindowRect(hwnd)
                    width = rect[2] - rect[0]
                    height = rect[3] - rect[1]
                    if width < 30 or height < 30:
                        return True
                except Exception:
                    pass

                # 7. PID 必须在目标列表中
                _, curr_pid = SafeWindowsAPI.get_window_thread_process_id(hwnd)
                if curr_pid not in target_pid_map:
                    return True

                process_info = target_pid_map[curr_pid]
                hit_pids.add(curr_pid)

                # 8. 标题关键字过滤
                if keywords and not self._is_title_matching_keywords(title, keywords):
                    logger.debug(
                        "窗口标题 '%s' 不包含关键字，跳过: HWND=%d",
                        title,
                        hwnd,
                    )
                    hwnds_to_remove.add(hwnd)
                    return True

                # 9. 检查：仅操作超级窗口（不检查 IsWindowVisible，兼容 SW_HIDE 隐藏窗口）
                if not SafeWindowsAPI.is_super_window(hwnd):
                    logger.debug(
                        "窗口不是超级窗口，跳过: %d - %s",
                        hwnd, title,
                    )
                    hwnds_to_remove.add(hwnd)
                    return True

                # 10. 规划要求：每个进程（PID）只取唯一的VW窗口
                if curr_pid in found_hwnd_per_pid:
                    logger.debug(
                        "进程 PID=%d 已有VW (HWND=%d)，跳过重复窗口: %d - %s",
                        curr_pid, found_hwnd_per_pid[curr_pid], hwnd, title,
                    )
                    return True
                found_hwnd_per_pid[curr_pid] = hwnd

                if hwnd not in self._hidden_windows:
                    window_info = SafeWindowsAPI.create_window_info(
                        hwnd,
                        title=title,
                        pid=curr_pid,
                        state=WindowState.HIDDEN,
                        is_visible=False,
                        process_name=process_info["name"],
                        is_foreground=False,
                        is_taskbar=SafeWindowsAPI.is_taskbar_window(hwnd),
                    )
                    self._hidden_windows[hwnd] = window_info
                    background_windows.append(window_info)
                    logger.info(
                        "找到 VW: HWND=%d, 标题='%s', PID=%d, 进程=%s",
                        hwnd, title, curr_pid, process_info["name"],
                    )
            except Exception:
                pass
            return True

        if WIN32GUI_AVAILABLE and win32gui is not None:
            win32gui.EnumWindows(callback, None)

        # P0-8 修复: 回调外统一处理待删除的 hwnd（避免回调中修改共享字典）
        for hwnd in hwnds_to_remove:
            self._hidden_windows.pop(hwnd, None)

        return background_windows, hit_pids

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

    def get_process_visible_hwnds(
        self, pid: int, _process_name: str
    ) -> Tuple[bool, List[int]]:
        """获取单个进程的所有可见窗口句柄（前台应用）
        比全量枚举快 10~100 倍

        Args:
            pid: 进程ID
            process_name: 进程名

        Returns:
            Tuple[bool, List[int]]:
                - 第一个元素：是否找到该进程的可见窗口
                - 第二个元素：找到的窗口句柄列表
        """
        result: List[int] = []

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

        if not WIN32GUI_AVAILABLE or win32gui is None:
            return (False, [])

        try:
            win32gui.EnumWindows(callback, None)
            return (len(result) > 0, result)
        except Exception:
            return (False, [])

    def find_visible_hwnds_by_process_name(self, process_name: str) -> List[int]:
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
        return self._enumerate_hwnds_by_process_name(process_name, visible_only=True)

    def find_all_hwnds_by_process_name(self, process_name: str) -> List[int]:
        """通过进程名查找所有窗口句柄（包括隐藏窗口）

        Args:
            process_name: 进程名

        Returns:
            List[int]: 窗口句柄列表
        """
        return self._enumerate_hwnds_by_process_name(process_name, visible_only=False)

    def _enumerate_hwnds_by_process_name(
        self, process_name: str, visible_only: bool = False
    ) -> List[int]:
        """通过进程名枚举窗口句柄（公共实现）

        Args:
            process_name: 进程名
            visible_only: 是否只返回可见窗口

        Returns:
            List[int]: 窗口句柄列表
        """
        hwnds: List[int] = []
        if not PSUTIL_AVAILABLE or psutil is None:
            return hwnds
        if not WIN32GUI_AVAILABLE or win32gui is None:
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

        def callback(hwnd, _extra):
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
        result: List[dict] = []
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

        if not WIN32GUI_AVAILABLE or win32gui is None:
            return result

        win32gui.EnumWindows(enum_windows_callback, None)
        return result
