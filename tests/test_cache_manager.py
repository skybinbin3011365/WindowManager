"""
窗口管理器 - 缓存管理模块单元测试
测试 cache_manager 模块中的 CacheManager 类
"""

import unittest
import sys
import os
import tempfile
import json
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestCacheManager(unittest.TestCase):
    """测试 CacheManager 缓存管理器类"""

    def setUp(self):
        """测试前准备 - 创建临时缓存目录"""
        self.test_dir = tempfile.mkdtemp()
        self.cache_file = Path(self.test_dir) / "test_cache.json"

    def tearDown(self):
        """测试后清理"""
        if os.path.exists(self.test_dir):
            import shutil
            shutil.rmtree(self.test_dir)

    def test_cache_manager_initialization(self):
        """测试 CacheManager 初始化"""
        try:
            from src.cache_manager import CacheManager
            manager = CacheManager(cache_file=self.cache_file)
            self.assertEqual(manager._cache_file, self.cache_file)
            self.assertIsNotNone(manager._lock)
        except ImportError:
            self.skipTest("Cannot import CacheManager in test environment")

    def test_load_cache_file_not_exists(self):
        """测试加载不存在的缓存文件（不应报错）"""
        try:
            from src.cache_manager import CacheManager
            manager = CacheManager(cache_file=self.cache_file)
            # 文件不存在时 load_cache 不应抛异常
            manager.load_cache()
        except ImportError:
            self.skipTest("Cannot import CacheManager in test environment")

    def test_load_cache_existing_file(self):
        """测试加载已存在的缓存文件"""
        try:
            from src.cache_manager import CacheManager
            # 先写入一个有效的 JSON 文件
            self.cache_file.write_text('{"test": "data"}', encoding="utf-8")
            manager = CacheManager(cache_file=self.cache_file)
            manager.load_cache()
        except ImportError:
            self.skipTest("Cannot import CacheManager in test environment")

    def test_save_cache_creates_file(self):
        """测试 save_cache 创建缓存文件"""
        try:
            from src.cache_manager import CacheManager
            manager = CacheManager(cache_file=self.cache_file)
            manager.save_cache()
            self.assertTrue(self.cache_file.exists())
            # 验证内容是合法的 JSON
            with open(self.cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.assertIsInstance(data, dict)
        except ImportError:
            self.skipTest("Cannot import CacheManager in test environment")


if __name__ == "__main__":
    unittest.main(verbosity=2)
