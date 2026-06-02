# -*- coding: utf-8 -*-
# windowmanager/cache_manager.py
"""
缓存管理模块
管理窗口管理器的缓存数据
"""

import logging
import os
import sys
import json
from typing import Dict, Any

logger = logging.getLogger(__name__)


class CacheManager:
    """缓存管理器"""

    def __init__(self, cache_dir: str = None):
        if cache_dir is None:
            if getattr(sys, "frozen", False) or hasattr(sys, "__nuitka_binary__"):
                cache_dir = os.path.join(os.path.dirname(sys.executable), 'cache')
            else:
                cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cache')
        self.cache_dir = cache_dir
        self.cache_file = os.path.join(cache_dir, 'window_cache.json')
        os.makedirs(cache_dir, exist_ok=True)
        self._cache: Dict[str, Any] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        """加载缓存文件"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self._cache = json.load(f)
                logger.info("缓存文件加载成功")
        except Exception as e:
            logger.warning(f"加载缓存文件失败: {e}")
            self._cache = {}

    def load_cache(self) -> None:
        """公开的加载缓存方法"""
        self._load_cache()

    def save_cache(self) -> None:
        """保存缓存文件"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存缓存文件失败: {e}")

    def get(self, key: str, default=None) -> Any:
        """获取缓存值"""
        return self._cache.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """设置缓存值"""
        self._cache[key] = value
        self.save_cache()

    def delete(self, key: str) -> bool:
        """删除缓存值"""
        if key in self._cache:
            del self._cache[key]
            self.save_cache()
            return True
        return False

    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()
        self.save_cache()

    def get_all(self) -> Dict[str, Any]:
        """获取所有缓存"""
        return dict(self._cache)
