#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
窗口管理相关数据模型
重构后的窗口管理数据结构，符合用户文档要求
"""

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Optional


class WindowEntryState(Enum):
    """窗口条目状态枚举 - 用于配置管理"""

    VISIBLE = "visible"  # 可见状态
    HIDDEN = "hidden"  # 隐藏状态
    INVALID = "invalid"  # 无效状态（进程不存在）


@dataclass
class WindowEntry:
    """设定窗口条目 - 符合用户文档要求"""

    SOURCE_MANUAL = "manual"
    SOURCE_KEYWORD = "keyword"

    process_name: str
    title: str
    hwnd: Optional[int] = None
    state: WindowEntryState = WindowEntryState.INVALID
    source: str = SOURCE_MANUAL

    def to_dict(self) -> dict:
        """将窗口条目转换为字典（用于配置序列化）"""
        result = asdict(self)
        result["state"] = self.state.value
        return result


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
