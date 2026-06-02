# -*- coding: utf-8 -*-
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

    @classmethod
    def create_hidden(
        cls,
        hwnd: int,
        title: str = "",
        process_name: str = "",
        pid: int = 0,
        is_taskbar: bool = False,
    ) -> "WindowInfo":
        """创建隐藏状态的窗口信息对象

        用于从配置恢复、占位创建、持久化恢复等场景，
        统一隐藏窗口的构造方式，避免重复代码。

        参数:
            hwnd: 窗口句柄
            title: 窗口标题
            process_name: 进程名称
            pid: 进程ID
            is_taskbar: 是否在任务栏显示

        返回:
            WindowInfo - 隐藏状态的窗口信息
        """
        return cls(
            hwnd=hwnd,
            title=title,
            process_name=process_name,
            pid=pid,
            is_visible=False,
            is_taskbar=is_taskbar,
            state=WindowState.HIDDEN,
        )

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


@dataclass(slots=True, frozen=False)
class WindowInfoParams:
    """WindowInfo 构造参数数据类

    用于简化 create_window_info 方法的参数列表

    属性:
        hwnd: int - 窗口句柄（必填）
        title: Optional[str] - 窗口标题，默认自动获取
        class_name: Optional[str] - 窗口类名，默认自动获取
        pid: Optional[int] - 进程ID，默认自动获取
        state: WindowState - 窗口状态，默认 NORMAL
        is_visible: bool - 窗口是否可见，默认 True
        is_foreground: bool - 是否为前台窗口，默认 False
        monitor_id: Optional[int] - 窗口所在显示器ID
        monitor_name: str - 窗口所在显示器名称
        process_name: Optional[str] - 进程名称，默认自动获取
        is_taskbar: Optional[bool] - 是否在任务栏显示，默认 None（未分类）
    """

    hwnd: int
    title: Optional[str] = None
    class_name: Optional[str] = None
    pid: Optional[int] = None
    state: WindowState = WindowState.NORMAL
    is_visible: bool = True
    is_foreground: bool = False
    monitor_id: Optional[int] = None
    monitor_name: str = ""
    process_name: Optional[str] = None
    is_taskbar: Optional[bool] = None
