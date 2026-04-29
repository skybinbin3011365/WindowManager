"""
窗口管理器 - 配置管理器单元测试
测试 config 模块中的 Config 和 ConfigManager 类
"""

from src.config import Config, ConfigManager
import unittest
import sys
import os
import tempfile
import shutil

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestConfig(unittest.TestCase):
    """测试 Config 数据类"""

    def test_config_defaults(self):
        """测试 Config 默认值"""
        config = Config()
        self.assertEqual(config.version, "2.0")
        self.assertEqual(config.hide_hotkey, "MBUTTON+RBUTTON")
        self.assertEqual(config.show_hotkey, "SHIFT+RBUTTON")
        self.assertEqual(config.log_level, "INFO")
        self.assertFalse(config.auto_start)
        self.assertEqual(config.auto_refresh_interval, 10.0)
        self.assertEqual(config.keywords, [])
        self.assertEqual(config.process_whitelist, [])
        self.assertEqual(config.target_windows, [])

    def test_config_custom_values(self):
        """测试 Config 自定义值"""
        config = Config(
            hide_hotkey="Ctrl+Shift+H",
            show_hotkey="Ctrl+Shift+S",
            auto_start=True,
            auto_refresh_interval=5.0,
            keywords=["keyword1", "keyword2"],
            process_whitelist=["process1.exe", "process2.exe"]
        )
        self.assertEqual(config.hide_hotkey, "Ctrl+Shift+H")
        self.assertEqual(config.show_hotkey, "Ctrl+Shift+S")
        self.assertTrue(config.auto_start)
        self.assertEqual(config.auto_refresh_interval, 5.0)
        self.assertEqual(config.keywords, ["keyword1", "keyword2"])
        self.assertEqual(config.process_whitelist, ["process1.exe", "process2.exe"])

    def test_config_ui_defaults(self):
        """测试 Config UI 配置默认值"""
        config = Config()
        ui_config = config.ui
        self.assertEqual(ui_config["width"], 1000)
        self.assertEqual(ui_config["height"], 700)
        self.assertEqual(ui_config["theme"], "light")
        self.assertEqual(ui_config["hidden_columns"], [])

    def test_config_ntp_defaults(self):
        """测试 Config NTP 配置默认值"""
        config = Config()
        self.assertFalse(config.auto_sync_enabled)  # 注意：默认是 False
        self.assertEqual(config.auto_sync_interval_hours, 1.0)
        self.assertEqual(config.ntp_check_interval, 60)
        self.assertEqual(config.ntp_error_threshold, 5)
        self.assertFalse(config.ntp_auto_calibrate)
        self.assertTrue(config.enable_ntp_log)


class TestConfigManager(unittest.TestCase):
    """测试 ConfigManager 类"""

    def setUp(self):
        """测试前准备 - 创建临时目录"""
        self.test_dir = tempfile.mkdtemp()
        self.config_manager = ConfigManager(config_dir=self.test_dir)

    def tearDown(self):
        """测试后清理 - 删除临时目录"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_config_manager_initialization(self):
        """测试 ConfigManager 初始化"""
        # 使用 pathlib.Path 进行路径比较
        import pathlib
        self.assertEqual(self.config_manager.config_dir, pathlib.Path(self.test_dir))
        self.assertTrue(os.path.exists(self.config_manager.config_dir))
        self.assertEqual(self.config_manager.config_file.name, "config.json")

    def test_load_default_config(self):
        """测试加载默认配置"""
        config = self.config_manager.load()
        self.assertIsInstance(config, Config)
        self.assertEqual(config.version, "2.0")

    def test_save_and_load_config(self):
        """测试保存和加载配置"""
        # 创建自定义配置
        original_config = Config(
            hide_hotkey="Ctrl+Alt+H",
            show_hotkey="Ctrl+Alt+S",
            auto_start=True
        )

        # 保存配置
        save_result = self.config_manager.save(original_config, immediate=True)
        self.assertTrue(save_result)

        # 重新创建 ConfigManager 并加载
        new_manager = ConfigManager(config_dir=self.test_dir)
        loaded_config = new_manager.load()

        # 验证配置是否正确保存和加载
        self.assertEqual(loaded_config.hide_hotkey, "Ctrl+Alt+H")
        self.assertEqual(loaded_config.show_hotkey, "Ctrl+Alt+S")
        self.assertTrue(loaded_config.auto_start)

    def test_observer_registration(self):
        """测试观察者注册"""
        class MockObserver:
            def __init__(self):
                self.update_called = False
                self.received_config = None

            def update(self, config):
                self.update_called = True
                self.received_config = config

        observer = MockObserver()
        self.config_manager.register_observer(observer)

        # 验证观察者已注册
        self.assertIn(observer, self.config_manager._observers)

        # 保存配置触发通知
        config = Config(hide_hotkey="NewHotkey")
        self.config_manager.save(config, immediate=True)

        # 验证观察者的 update 方法被调用
        self.assertTrue(observer.update_called)
        self.assertEqual(observer.received_config.hide_hotkey, "NewHotkey")

    def test_observer_unregistration(self):
        """测试观察者注销"""
        class MockObserver:
            def update(self, config):
                pass

        observer = MockObserver()
        self.config_manager.register_observer(observer)
        self.assertIn(observer, self.config_manager._observers)

        # 注销观察者
        self.config_manager.unregister_observer(observer)
        self.assertNotIn(observer, self.config_manager._observers)

    def test_multiple_observers(self):
        """测试多个观察者"""
        class MockObserver:
            def __init__(self, name):
                self.name = name
                self.update_count = 0

            def update(self, config):
                self.update_count += 1

        observer1 = MockObserver("observer1")
        observer2 = MockObserver("observer2")

        self.config_manager.register_observer(observer1)
        self.config_manager.register_observer(observer2)

        # 保存配置触发通知
        config = Config()
        self.config_manager.save(config, immediate=True)

        # 验证两个观察者都被通知
        self.assertEqual(observer1.update_count, 1)
        self.assertEqual(observer2.update_count, 1)

        # 注销第一个观察者
        self.config_manager.unregister_observer(observer1)

        # 再次保存配置
        self.config_manager.save(config, immediate=True)

        # 验证只有第二个观察者被通知
        self.assertEqual(observer1.update_count, 1)
        self.assertEqual(observer2.update_count, 2)


class TestConfigMigration(unittest.TestCase):
    """测试配置文件迁移"""

    def setUp(self):
        """测试前准备 - 创建临时目录"""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """测试后清理 - 删除临时目录"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_migration_from_old_location(self):
        """测试迁移逻辑的触发条件"""
        import pathlib

        # 模拟迁移场景：旧配置文件存在，新配置文件不存在
        # 注意：这个测试只验证迁移逻辑的触发条件，不验证完整迁移流程
        # 因为迁移逻辑依赖于项目根目录的路径

        # 创建临时配置目录
        temp_config_dir = tempfile.mkdtemp()
        try:
            # 在临时目录创建"旧"配置文件
            old_file = pathlib.Path(temp_config_dir) / "config.json"
            old_file.write_text('{"hide_hotkey": "TestHotkey"}')

            # 创建 ConfigManager，它会检查是否存在旧配置文件
            manager = ConfigManager(config_dir=temp_config_dir)

            # 验证配置可以加载
            config = manager.load()
            self.assertIsInstance(config, Config)

        finally:
            # 清理
            if os.path.exists(temp_config_dir):
                shutil.rmtree(temp_config_dir)


if __name__ == "__main__":
    # 运行测试
    unittest.main(verbosity=2)
