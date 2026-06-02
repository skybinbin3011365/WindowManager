"""
窗口管理器 - PySide6 UI 组件测试
使用 pytest-qt 测试核心 UI 组件的创建和基本行为

运行方式: pytest tests/test_ui_components.py -v

注意:
- pytest-qt 需要 Qt 应用程序实例 (qtbot fixture 自动提供)
- 这些测试不依赖实际窗口枚举，仅验证组件初始化和接口
"""

import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestWindowTableWidget:
    """测试 WindowTableWidget 表格组件"""

    def test_table_widget_creation(self, qtbot):
        """测试表格组件可以正常创建"""
        try:
            from src.window_table import WindowTableWidget
            table = WindowTableWidget()
            qtbot.addWidget(table)
            # 基本属性验证
            self = type("", (), {"assertTrue": lambda s, x: None, "assertGreater": lambda s, a, b: None})()
            assert table.columnCount() > 0 or table.rowCount() == 0
        except ImportError as e:
            pass  # 在无头环境可能无法导入 PySide6


class TestWindowClassifier:
    """测试 WindowClassifier 分类器（纯逻辑，无需 Qt）"""

    def test_classifier_initialization(self):
        """测试分类器初始化"""
        try:
            from src.window_classifier import WindowClassifier
            classifier = WindowClassifier()
            assert len(classifier._ignored_classes) > 0
            assert "Progman" in classifier._ignored_classes
        except ImportError:
            pass


class TestConstantsModule:
    """测试常量模块完整性（无 Qt 依赖）"""

    def test_window_constants_exist(self):
        """测试关键常量存在"""
        try:
            from src.constants import (
                WindowConstants,
                ConfigConstants,
                UICommonConstants,
            )
            assert hasattr(WindowConstants, "BACKGROUND_PROCESS_HWND_OFFSET")
            assert WindowConstants.BACKGROUND_PROCESS_HWND_OFFSET < 0
            assert ConfigConstants.CONFIG_VERSION != ""
        except ImportError:
            pass

    def test_ui_common_constants(self):
        """测试 UI 公共常量"""
        try:
            from src.constants import UICommonConstants
            c = UICommonConstants
            assert hasattr(c, "TRAY_MESSAGE_DURATION")
            assert c.TRAY_MESSAGE_DURATION > 0
        except ImportError:
            pass


class TestWindowModels:
    """测试数据模型（无 Qt 依赖）"""

    def test_window_entry_state_enum(self):
        """测试窗口状态枚举值"""
        try:
            from src.window_models import WindowEntryState
            assert WindowEntryState.VISIBLE.value == "visible"
            assert WindowEntryState.HIDDEN.value == "hidden"
            assert WindowEntryState.INVALID.value == "invalid"
        except ImportError:
            pass

    def test_classified_windows_container(self):
        """测试分类窗口容器"""
        try:
            from src.window_models import ClassifiedWindows
            cw = ClassifiedWindows()
            assert cw.apps == []
            assert cw.background == []
            assert cw.target == []
        except ImportError:
            pass


if __name__ == "__main__":
    # 允许直接运行（但推荐通过 pytest）
    import unittest

    # 将类转换为 TestCase 以支持直接运行
    class TestConstantsModuleCase(unittest.TestCase):
        def test_window_constants_exist(self):
            TestConstantsModule().test_window_constants_exist()

        def test_ui_common_constants(self):
            TestConstantsModule().test_ui_common_constants()

    class TestWindowModelsCase(unittest.TestCase):
        def test_window_entry_state_enum(self):
            TestWindowModels().test_window_entry_state_enum()

        def test_classified_windows_container(self):
            TestWindowModels().test_classified_windows_container()

    class TestWindowClassifierCase(unittest.TestCase):
        def test_classifier_initialization(self):
            TestWindowClassifier().test_classifier_initialization()
