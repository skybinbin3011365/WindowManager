"""
窗口管理 - 基础类型模块
包含公共类型定义，用于消除模块间循环依赖
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


class WindowState(Enum):
    """窗口状态枚举"""

    NORMAL = auto()
    MINIMIZED = auto()
    MAXIMIZED = auto()
    HIDDEN = auto()


@dataclass(slots=True, frozen=False)
class MonitorInfo:
    """显示器信息数据类

    属性:
        monitor_id: int - 显示器ID
        left: int - 显示器左边界
        top: int - 显示器上边界
        right: int - 显示器右边界
        bottom: int - 显示器下边界
        is_primary: bool - 是否为主显示器
    """

    monitor_id: int
    left: int
    top: int
    right: int
    bottom: int
    is_primary: bool = False

    @property
    def width(self) -> int:
        """显示器宽度"""
        return self.right - self.left

    @property
    def height(self) -> int:
        """显示器高度"""
        return self.bottom - self.top


@dataclass(slots=True, frozen=False)
class WindowInfo:
    """窗口信息数据类

    属性:
        hwnd: int - 窗口句柄
        title: str - 窗口标题
        class_name: str - 窗口类名
        pid: int - 进程ID
        state: WindowState - 窗口状态
        is_visible: bool - 窗口是否可见
        process_name: str - 进程名称
        is_foreground: bool - 是否为前台窗口
        monitor_id: Optional[int] - 窗口所在显示器ID
        monitor_name: str - 窗口所在显示器名称
        is_taskbar: Optional[bool] - 是否在任务栏显示（None 表示未分类）
    """

    hwnd: int
    title: str = ""
    class_name: str = ""
    pid: int = 0
    state: WindowState = WindowState.NORMAL
    is_visible: bool = True
    process_name: str = ""
    is_foreground: bool = False
    monitor_id: Optional[int] = None
    monitor_name: str = ""
    is_taskbar: Optional[bool] = None

    def get_display_title(self) -> str:
        """获取显示标题

        返回带有进程名的标题格式，如 "进程名: 窗口标题"

        返回:
            str - 格式化的显示标题
        """
        if self.process_name:
            return f"{self.process_name}: {self.title}"
        return self.title

    def __repr__(self) -> str:
        """便于调试的打印格式"""
        return (
            f"WindowInfo(hwnd={self.hwnd}, pid={self.pid}, process={self.process_name!r}, "
            f"title={self.title!r}, state={self.state.name})"
        )
