"""
窗口管理器 - 主题模块单元测试
测试 theme 模块中的 ModernTheme 类

注意: 这些测试需要 PySide6 支持,如果 PySide6 不可用,大部分测试会被跳过
"""

import unittest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 检查 PySide6 是否可用
try:
    from PySide6.QtGui import QColor
    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False


# 如果 PySide6 不可用,跳过整个模块的测试
@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 not available, skipping theme tests")
class TestModernThemeColors(unittest.TestCase):
    """测试 ModernTheme 颜色常量"""

    def test_primary_colors(self):
        """测试主色调"""
        from src.theme import ModernTheme
        self.assertEqual(ModernTheme.PRIMARY, "#6366F1")
        self.assertEqual(ModernTheme.PRIMARY_LIGHT, "#818CF8")
        self.assertEqual(ModernTheme.PRIMARY_DARK, "#4F46E5")

    def test_accent_colors(self):
        """测试强调色"""
        from src.theme import ModernTheme
        self.assertEqual(ModernTheme.ACCENT, "#8B5CF6")
        self.assertEqual(ModernTheme.ACCENT_LIGHT, "#A78BFA")
        self.assertEqual(ModernTheme.ACCENT_DARK, "#7C3AED")

    def test_function_colors(self):
        """测试功能色"""
        from src.theme import ModernTheme
        self.assertEqual(ModernTheme.SUCCESS, "#10B981")
        self.assertEqual(ModernTheme.WARNING, "#F59E0B")
        self.assertEqual(ModernTheme.DANGER, "#EF4444")

    def test_background_colors(self):
        """测试背景色"""
        from src.theme import ModernTheme
        self.assertEqual(ModernTheme.BACKGROUND, "#0F172A")
        self.assertEqual(ModernTheme.SURFACE, "#1E293B")

    def test_text_colors(self):
        """测试文字色"""
        from src.theme import ModernTheme
        self.assertEqual(ModernTheme.TEXT_PRIMARY, "#F8FAFC")
        self.assertEqual(ModernTheme.TEXT_SECONDARY, "#94A3B8")

    def test_font_settings(self):
        """测试字体设置"""
        from src.theme import ModernTheme
        self.assertTrue(len(ModernTheme.FONT_FAMILY) > 0)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 not available, skipping theme tests")
class TestModernThemeGetters(unittest.TestCase):
    """测试 ModernTheme 获取器方法"""

    def test_get_primary(self):
        """测试获取主色调"""
        from src.theme import ModernTheme
        self.assertEqual(ModernTheme.get_primary(), ModernTheme.PRIMARY)

    def test_get_success(self):
        """测试获取成功色"""
        from src.theme import ModernTheme
        self.assertEqual(ModernTheme.get_success(), ModernTheme.SUCCESS)

    def test_get_warning(self):
        """测试获取警告色"""
        from src.theme import ModernTheme
        self.assertEqual(ModernTheme.get_warning(), ModernTheme.WARNING)

    def test_get_danger(self):
        """测试获取危险色"""
        from src.theme import ModernTheme
        self.assertEqual(ModernTheme.get_danger(), ModernTheme.DANGER)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 not available, skipping theme tests")
class TestModernThemeStylesheet(unittest.TestCase):
    """测试 ModernTheme 样式表方法"""

    def test_get_temp_message_stylesheet(self):
        """测试获取临时消息样式表"""
        from src.theme import ModernTheme
        stylesheet = ModernTheme.get_temp_message_stylesheet()
        self.assertIsInstance(stylesheet, str)
        self.assertGreater(len(stylesheet), 0)

    def test_get_global_stylesheet(self):
        """测试获取全局样式表"""
        from src.theme import ModernTheme
        stylesheet = ModernTheme.get_global_stylesheet()
        self.assertIsInstance(stylesheet, str)
        self.assertGreater(len(stylesheet), 100)


@unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 not available, skipping theme tests")
class TestThemeInstance(unittest.TestCase):
    """测试 theme 全局实例"""

    def test_theme_instance_exists(self):
        """测试 theme 全局实例存在"""
        from src.theme import theme
        self.assertIsNotNone(theme)

    def test_theme_instance_type(self):
        """测试 theme 全局实例类型"""
        from src.theme import theme, ModernTheme
        self.assertIsInstance(theme, ModernTheme)


if __name__ == "__main__":
    unittest.main(verbosity=2)
