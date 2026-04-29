#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
热键录制模块
提供可视化热键录制功能
"""

import logging
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout
from PySide6.QtCore import Qt, QTimer, Signal

# 尝试导入pynput
try:
    from pynput import keyboard, mouse

    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    keyboard = None
    mouse = None

# 导入共享的热键录制器
from hotkey_recorder_core import HotkeyRecorder

# 配置日志
logger = logging.getLogger(__name__)


class HotkeyRecorderDialog(QDialog):
    """热键录制对话框"""

    recording_finished = Signal(object, object)  # (hotkey_str, None)

    def __init__(self, parent=None, timeout=3):
        super().__init__(parent)
        self.timeout = timeout
        self.start_time = None

        # 共享的热键录制器
        self._recorder = HotkeyRecorder(timeout=timeout)

        # pynput监听器
        self.keyboard_listener = None
        self.mouse_listener = None

        self.init_ui()
        self.init_timer()

    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("热键录制")
        self.setFixedSize(350, 120)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Dialog)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        self.label = QLabel("请按下想要录制的组合键...")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)

        self.time_label = QLabel(f"剩余时间: {self.timeout}秒")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.time_label)

        self.setLayout(layout)

    def init_timer(self):
        """初始化定时器"""
        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self.check_keys)
        self.check_timer.start(20)  # 20ms 检查一次

        self.timeout_timer = QTimer()
        self.timeout_timer.timeout.connect(self.update_timeout)
        self.timeout_timer.start(1000)  # 1秒更新一次

    def showEvent(self, event):
        """窗口显示事件"""
        super().showEvent(event)
        self.start_time = __import__("time").time()

        # 启动pynput监听器
        if PYNPUT_AVAILABLE:
            # 启动键盘监听器
            self.keyboard_listener = keyboard.Listener(
                on_press=self._on_key_press, on_release=self._on_key_release
            )
            self.keyboard_listener.start()

            # 启动鼠标监听器
            self.mouse_listener = mouse.Listener(on_click=self._on_mouse_click)
            self.mouse_listener.start()
        else:
            self.label.setText("错误: pynput 不可用")
            self.finish_recording()

    def _get_key_name(self, key):
        """获取键盘按键名称"""
        return HotkeyRecorder.get_key_name(key)

    def _get_mouse_name(self, button):
        """获取鼠标按键名称"""
        return HotkeyRecorder.get_mouse_name(button)

    def _on_key_press(self, key):
        """键盘按键按下事件"""
        try:
            key_name = self._get_key_name(key)
            if key_name:
                # 使用录制器记录按键
                self._recorder.record_key(key_name)
                # 显示按键组合
                key_str = self._recorder.format_hotkey_string(
                    self._recorder.get_recorded_keys())
                self.label.setText(f"已捕获: {key_str}，请松开...")
        except Exception as e:
            logger.error("键盘按键处理错误: %s", str(e))

    def _on_key_release(self, key):
        """键盘按键释放事件"""
        try:
            key_name = self._get_key_name(key)
            # 使用公共方法获取录制的按键
            recorded_keys = self._recorder.get_recorded_keys()
            if key_name and key_name in recorded_keys:
                # 清空并重新记录（简化处理）
                self._recorder.clear_recorded_keys()

            # 所有按键都松开时完成录制
            if not self._recorder.get_recorded_keys() and self._recorder.is_recording():
                self.finish_recording()
        except Exception as e:
            logger.error("键盘按键释放处理错误: %s", str(e))

    def _on_mouse_click(self, x, y, button, pressed):
        """鼠标点击事件"""
        try:
            mouse_name = self._get_mouse_name(button)
            if mouse_name:
                if pressed:
                    # 使用录制器记录按键
                    self._recorder.record_key(mouse_name)
                    # 显示按键组合
                    key_str = self._recorder.format_hotkey_string(
                        self._recorder.get_recorded_keys()
                    )
                    self.label.setText(f"已捕获: {key_str}，请松开...")
                else:
                    # 使用公共方法获取录制的按键
                    recorded_keys = self._recorder.get_recorded_keys()
                    if mouse_name and mouse_name in recorded_keys:
                        # 清空并重新记录（简化处理）
                        self._recorder.clear_recorded_keys()

                    # 所有按键都松开时完成录制
                    if not self._recorder.get_recorded_keys() and self._recorder.is_recording():
                        self.finish_recording()
        except Exception as e:
            logger.error("鼠标按键处理错误: %s", str(e))

    def check_keys(self):
        """检查按键状态（只处理超时）"""
        if not self.start_time:
            return

        import time

        current_time = time.time()

        # 检查是否超时
        if current_time - self.start_time >= self.timeout:
            self.finish_recording()
            return

    def update_timeout(self):
        """更新超时显示"""
        if not self.start_time:
            return

        remaining = max(
            0, int(self.timeout - (__import__("time").time() - self.start_time)))
        self.time_label.setText(f"剩余时间: {remaining}秒")

    def finish_recording(self):
        """完成录制"""
        # 停止定时器
        self.check_timer.stop()
        self.timeout_timer.stop()

        # 停止pynput监听器
        if self.keyboard_listener:
            try:
                self.keyboard_listener.stop()
            except Exception as e:
                logger.warning("停止键盘监听器时出错: %s", str(e))
        if self.mouse_listener:
            try:
                self.mouse_listener.stop()
            except Exception as e:
                logger.warning("停止鼠标监听器时出错: %s", str(e))

        # 停止录制器
        self._recorder.stop_recording()

        # 生成热键字符串
        hotkey_str = (
            self._recorder.format_hotkey_string(
                self._recorder.get_recorded_keys())
            if self._recorder.get_recorded_keys()
            else None
        )
        if hotkey_str:
            logger.info("录制成功：%s", hotkey_str)
        else:
            logger.warning("录制超时或未检测到有效组合键")

        # 发射信号，传递热键字符串
        self.recording_finished.emit(hotkey_str, None)
        self.accept()

    def closeEvent(self, event):
        """窗口关闭事件处理"""
        # 清理资源
        self.check_timer.stop()
        self.timeout_timer.stop()

        # 停止pynput监听器
        if self.keyboard_listener:
            try:
                self.keyboard_listener.stop()
            except Exception as e:
                logger.warning("停止键盘监听器时出错: %s", str(e))
        if self.mouse_listener:
            try:
                self.mouse_listener.stop()
            except Exception as e:
                logger.warning("停止鼠标监听器时出错: %s", str(e))

        # 停止录制器
        self._recorder.stop_recording()

        event.accept()


def record_hotkey(timeout=10):
    """
    录制热键（同步调用）

    Args:
        timeout: 超时时间（秒）

    Returns:
        str: 录制的热键字符串，或 None
    """
    logger.info("开始录制热键，请按下想要录制的组合键...")

    # 导入 PySide6 并创建 QApplication（如果尚未创建）
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    # 创建对话框
    dialog = HotkeyRecorderDialog(timeout=timeout)

    # 存储结果
    result = [None]

    def on_recording_finished(hotkey_str, _):
        result[0] = hotkey_str

    dialog.recording_finished.connect(on_recording_finished)
    dialog.exec()

    return result[0]
