# -*- coding: utf-8 -*-
# windowmanager/hotkey_recorder_core.py
"""
热键录制核心模块
提供热键录制的公共逻辑，供 HotkeyManager 和 HotkeyRecorderDialog 共用
"""

import threading
import time
import logging
from typing import Optional, Callable, List

from constants import TimeConstants
from deps import PYNPUT_AVAILABLE, keyboard, mouse

logger = logging.getLogger(__name__)

# 默认录制超时时间（秒）
DEFAULT_RECORDING_TIMEOUT = 5.0


class HotkeyRecorder:
    """热键录制核心类

    提供热键录制的公共逻辑：
    - 按键格式化
    - 录制状态管理
    - 超时处理
    """

    def __init__(self, timeout: float = DEFAULT_RECORDING_TIMEOUT):
        self._timeout = timeout

        # 录制状态
        self._recording = False
        self._recording_lock = threading.Lock()
        self._recording_start_time = 0.0
        self._recorded_keys: List[str] = []
        self._recording_callback: Optional[Callable[[
            Optional[str]], None]] = None
        self._realtime_update_callback: Optional[Callable[[str], None]] = None

    def start_recording(
        self,
        callback: Callable[[Optional[str]], None],
        realtime_update_callback: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """开始录制快捷键

        Args:
            callback: 录制完成后的回调函数，参数为录制的快捷键字符串
            realtime_update_callback: 实时更新回调，显示当前按下的按键

        Returns:
            bool: 是否成功开始录制
        """
        with self._recording_lock:
            if self._recording:
                logger.warning("Recording already in progress")
                return False

            self._recording = True
            self._recording_start_time = time.time()
            self._recorded_keys = []
            self._recording_callback = callback
            self._realtime_update_callback = realtime_update_callback

            logger.info("Started recording hotkey...")

        # 启动超时检测线程
        threading.Thread(
            target=self._recording_timeout_handler, daemon=True).start()
        return True

    def stop_recording(self) -> Optional[str]:
        """停止录制快捷键

        Returns:
            Optional[str]: 录制的快捷键字符串
        """
        with self._recording_lock:
            if not self._recording:
                return None

            self._recording = False
            recorded_keys = self._recorded_keys.copy()
            self._recorded_keys = []

        if recorded_keys:
            hotkey_str = self.format_hotkey_string(recorded_keys)
            logger.info("Stopped recording, got: %s", hotkey_str)
            return hotkey_str

        logger.info("Stopped recording, no keys recorded")
        return None

    def record_key(self, key_name: str):
        """记录按键（录制模式下）"""
        with self._recording_lock:
            if not self._recording:
                return

            # 避免重复记录同一个键
            if key_name not in self._recorded_keys:
                self._recorded_keys.append(key_name)
                logger.debug("Recorded key: %s", key_name)

                # 实时更新回调
                if self._realtime_update_callback:
                    try:
                        hotkey_str = self.format_hotkey_string(
                            self._recorded_keys)
                        self._realtime_update_callback(hotkey_str)
                    except Exception as e:
                        logger.warning(
                            "Error in realtime update callback: %s", str(e))

    def is_recording(self) -> bool:
        """检查是否正在录制"""
        return self._recording

    def get_recorded_keys(self) -> List[str]:
        """获取当前录制的按键列表"""
        with self._recording_lock:
            return self._recorded_keys.copy()

    def clear_recorded_keys(self):
        """清空录制的按键"""
        with self._recording_lock:
            self._recorded_keys.clear()

    @staticmethod
    def format_hotkey_string(keys: List[str]) -> str:
        """格式化热键字符串"""
        formatted = [HotkeyRecorder.format_key_name(k) for k in keys]
        return "+".join(formatted)

    @staticmethod
    def format_key_name(key: str) -> str:
        """格式化单个按键名称（统一大写）"""
        mapping = {
            "ctrl": "CTRL",
            "alt": "ALT",
            "shift": "SHIFT",
            "win": "WIN",
            "left": "LBUTTON",
            "right": "RBUTTON",
            "middle": "MBUTTON",
            # 支持大小写变体
            "shift_l": "SHIFT",
            "shift_r": "SHIFT",
            "ctrl_l": "CTRL",
            "ctrl_r": "CTRL",
            "alt_l": "ALT",
            "alt_r": "ALT",
            "cmd_l": "WIN",
            "cmd_r": "WIN",
        }
        key_lower = key.lower()
        if key_lower in mapping:
            return mapping[key_lower]
        # 统一大写显示
        return key.upper()

    @staticmethod
    def get_key_name(key):
        """获取键盘按键名称"""
        try:
            if not PYNPUT_AVAILABLE or keyboard is None:
                return str(key)
            if key in (keyboard.Key.shift_l, keyboard.Key.shift_r):
                return "Shift"
            if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                return "Ctrl"
            if key in (keyboard.Key.alt_l, keyboard.Key.alt_r):
                return "Alt"
            if key in (keyboard.Key.cmd_l, keyboard.Key.cmd_r):
                return "Win"
            if hasattr(key, "char") and key.char:
                return key.char.upper()
            if hasattr(key, "name"):
                return key.name.capitalize()
            return str(key)
        except Exception:
            return str(key)

    @staticmethod
    def get_mouse_name(button):
        """获取鼠标按键名称"""
        try:
            if not PYNPUT_AVAILABLE or mouse is None:
                return str(button)
            if button == mouse.Button.left:
                return "Left Click"
            if button == mouse.Button.right:
                return "Right Click"
            if button == mouse.Button.middle:
                return "Middle Click"
            return str(button)
        except Exception:
            return str(button)

    def _recording_timeout_handler(self):
        """录制超时处理"""
        callback = None
        hotkey_str = None

        while True:
            with self._recording_lock:
                if not self._recording:
                    return

                elapsed = time.time() - self._recording_start_time
                if elapsed >= self._timeout:
                    self._recording = False
                    callback = self._recording_callback
                    hotkey_str = (
                        self.format_hotkey_string(self._recorded_keys)
                        if self._recorded_keys
                        else None
                    )
                    self._recording_callback = None
                    self._realtime_update_callback = None
                    break

            time.sleep(TimeConstants.SHORT_SLEEP_SECONDS)

        if callback:
            try:
                logger.info("Recording timed out, result: %s", hotkey_str)
                # 回调调用放在锁外，避免死锁
                callback(hotkey_str)
            except Exception as e:
                logger.error("Error calling recording callback: %s", str(e))
