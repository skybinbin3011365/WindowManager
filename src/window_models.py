#!/usr/bin/env python3
"""
窗口管理相关数据模型
重构后的窗口管理数据结构，符合用户文档要求
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, List

# 导入 WindowInfo 类型
from window_base import WindowInfo


class WindowEntryState(Enum):
    """窗口条目状态枚举 - 用于配置管理"""

    VISIBLE = "visible"  # 可见状态
    HIDDEN = "hidden"  # 隐藏状态
    INVALID = "invalid"  # 无效状态（进程不存在）


@dataclass
class WindowEntry:
    """设定窗口条目 - 符合用户文档要求"""

    process_name: str  # 进程名
    title: str  # 窗口标题
    hwnd: Optional[int] = None  # 窗口句柄（可能为None）
    state: WindowEntryState = WindowEntryState.INVALID  # 窗口状态
    source: str = "manual"  # 来源："keyword"（关键字匹配）或"manual"（手动添加）

    def to_dict(self) -> Dict:
        """转换为字典格式，用于JSON序列化"""
        return {
            "process_name": self.process_name,
            "title": self.title,
            "hwnd": self.hwnd,
            "state": self.state.value,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "WindowEntry":
        """从字典创建WindowEntry实例"""
        return cls(
            process_name=data.get("process_name", ""),
            title=data.get("title", ""),
            hwnd=data.get("hwnd"),
            state=WindowEntryState(data.get("state", "invalid")),
            source=data.get("source", "manual"),
        )


@dataclass
class SimpleWindowInfo:
    """简化窗口信息类 - 用于窗口分类器"""

    hwnd: int
    title: str
    class_name: str
    pid: int
    process_name: str
    is_visible: bool
    is_taskbar: bool = False

    def is_taskmanager_app(self) -> bool:
        """判断是否为任务管理器认定的应用窗口"""
        # 基础条件：可见且有标题
        if not self.is_visible or not self.title.strip():
            return False
        return True


class ClassifiedWindows:
    """分类后的窗口列表"""

    def __init__(self):
        self.apps: List[WindowInfo] = []  # 应用窗口（符合任务管理器标准）
        self.background: List[WindowInfo] = []  # 后台进程
        self.target: List[WindowEntry] = []  # 设定窗口（带状态）


class ProcessMonitorConfig:
    """进程监听配置"""

    def __init__(self):
        self.target_processes: set = set()  # 需要监听的进程名集合
        self.enabled: bool = True  # 是否启用监听
        self.check_interval: float = 1.0  # 检查间隔（秒）
