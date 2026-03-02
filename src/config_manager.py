"""
配置管理器 - 简化实现，支持加载与保存 config.json

提供：
 - `Config` 数据类（常用字段默认值）
 - `ConfigManager` 类：`load()` 和 `save(config)` 方法

此模块提供最小实现以修复缺失导入问题，并与现有代码的 `config_manager` 调用兼容。
"""
from __future__ import annotations

import json
import os
from typing import List, Any


class Config:
    """Minimal config object — avoid @dataclass to keep imports safe during
    dynamic import used in tests.
    """
    def __init__(self,
                 version: str = "1.0",
                 keywords: List[str] | None = None,
                 selected_windows: List[int] | None = None,
                 process_whitelist: List[str] | None = None,
                 ui: dict | None = None):
        self.version = version
        self.keywords = keywords if keywords is not None else []
        self.selected_windows = selected_windows if selected_windows is not None else []
        self.process_whitelist = process_whitelist if process_whitelist is not None else []
        self.ui = ui if ui is not None else {"width": 800, "height": 600, "theme": "light"}


class ConfigManager:
    def __init__(self, path: str | None = None):
        # 默认 config.json 位于项目根目录（src 的上一级）
        if path:
            self.path = path
        else:
            self.path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config.json'))

    def load(self) -> Config:
        try:
            if not os.path.exists(self.path):
                return Config()
            with open(self.path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            cfg = Config()
            # 仅映射已知字段，保持向后兼容
            if 'version' in data:
                cfg.version = data.get('version')
            if 'keywords' in data and isinstance(data['keywords'], list):
                cfg.keywords = data['keywords']
            if 'selected_windows' in data and isinstance(data['selected_windows'], list):
                cfg.selected_windows = data['selected_windows']
            if 'process_whitelist' in data and isinstance(data['process_whitelist'], list):
                cfg.process_whitelist = data['process_whitelist']
            if 'ui' in data and isinstance(data['ui'], dict):
                cfg.ui = data['ui']
            return cfg
        except Exception:
            # 避免导入时报错，返回默认配置
            return Config()

    def save(self, config: Config) -> bool:
        try:
            dirpath = os.path.dirname(self.path)
            if not os.path.exists(dirpath):
                os.makedirs(dirpath, exist_ok=True)
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump({
                    'version': config.version,
                    'keywords': config.keywords,
                    'selected_windows': config.selected_windows,
                    'process_whitelist': config.process_whitelist,
                    'ui': config.ui
                }, f, ensure_ascii=False, indent=4)
            return True
        except Exception:
            return False


__all__ = ['Config', 'ConfigManager']
