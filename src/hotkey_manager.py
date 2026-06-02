# -*- coding: utf-8 -*-
# windowmanager/hotkey_manager.py
"""
全局热键管理器（使用pynput库实现钩子模式）
采用状态检测方式，检测按键是否同时按下
"""

import threading
import time
from typing import Optional, Callable, Dict
import logging

from deps import PYNPUT_AVAILABLE, keyboard, mouse
from hotkey_recorder_core import HotkeyRecorder

logger = logging.getLogger(__name__)


class HotkeyManager:
    """全局热键管理器（使用pynput实现钩子模式）

    提供全局热键监听和录制功能，支持键盘和鼠标按键组合
    采用状态检测方式，检测按键是否同时按下
    """

    def __init__(self):
        self._running = False
        self._lock = threading.RLock()

        # 键盘按键状态字典
        self._key_states: Dict[str, bool] = {
            "shift": False,
            "ctrl": False,
            "alt": False,
            "win": False,
        }

        # 鼠标按键状态字典
        self._mouse_states: Dict[str, bool] = {
            "left": False,
            "right": False,
            "middle": False,
        }

        # 按键按下时间记录
        self._key_press_times: Dict[str, float] = {}

        # 状态锁
        self._state_lock = threading.Lock()

        # pynput监听器
        self._keyboard_listener = None
        self._mouse_listener = None

        # 回调函数
        self._hide_callback: Optional[Callable] = None
        self._show_callback: Optional[Callable] = None
        self._switch_callback: Optional[Callable] = None

        # 热键序列
        self._hide_hotkey_sequence = "Middle+Right"
        self._show_hotkey_sequence = "Shift+Right"
        self._switch_hotkey_sequence = "Ctrl+Right"

        # 共享的热键录制器
        self._recorder = HotkeyRecorder()

        # 防重复触发的冷却时间
        self._last_trigger_time = 0
        self._trigger_cooldown = 0.3

        # 组合键时间差阈值（秒）
        self._combo_time_threshold = 0.3

    def register_hide_hotkey(
        self, callback: Callable, hotkey_sequence: str = "Middle+Right"
    ):
        """注册隐藏窗口热键回调

        Args:
            callback: 热键触发时的回调函数
            hotkey_sequence: 热键序列字符串，默认为"Middle+Right"
        """
        self._hide_callback = callback
        self._hide_hotkey_sequence = hotkey_sequence
        logger.info("Registered hide hotkey: %s", hotkey_sequence)

    def unregister_hide_hotkey(self):
        """注销隐藏窗口热键"""
        self._hide_callback = None
        logger.info("Unregistered hide hotkey")

    def register_show_hotkey(
        self, callback: Callable, hotkey_sequence: str = "Shift+Right"
    ):
        """注册显示窗口热键回调

        Args:
            callback: 热键触发时的回调函数
            hotkey_sequence: 热键序列字符串，默认为"Shift+Right"
        """
        self._show_callback = callback
        self._show_hotkey_sequence = hotkey_sequence
        logger.info("Registered show hotkey: %s", hotkey_sequence)

    def unregister_show_hotkey(self):
        """注销显示窗口热键"""
        self._show_callback = None
        logger.info("Unregistered show hotkey")

    def register_switch_hotkey(
        self, callback: Callable, hotkey_sequence: str = "Ctrl+Right"
    ):
        """注册切换窗口热键回调

        Args:
            callback: 热键触发时的回调函数
            hotkey_sequence: 热键序列字符串，默认为"Ctrl+Right"
        """
        self._switch_callback = callback
        self._switch_hotkey_sequence = hotkey_sequence
        logger.info("Registered switch hotkey: %s", hotkey_sequence)

    def unregister_switch_hotkey(self):
        """注销切换窗口热键"""
        self._switch_callback = None
        logger.info("Unregistered switch hotkey")

    def start(self) -> bool:
        """启动热键监听"""
        if self._running:
            logger.warning("Hotkey manager already running")
            return True

        if not PYNPUT_AVAILABLE:
            logger.error("pynput is not available, cannot start hotkey manager")
            return False

        try:
            self._running = True

            # 启动键盘监听器
            self._keyboard_listener = keyboard.Listener(
                on_press=self._on_key_press, on_release=self._on_key_release
            )
            self._keyboard_listener.start()

            # 启动鼠标监听器
            self._mouse_listener = mouse.Listener(on_click=self._on_mouse_click)
            self._mouse_listener.start()

            logger.info("Hotkey manager started (pynput hook mode)")
            return True
        except Exception as e:
            logger.error("Failed to start hotkey manager: %s", str(e))
            self._cleanup()
            return False

    def _on_key_press(self, key):
        """键盘按键按下事件处理"""
        try:
            key_name = self._get_key_name(key)
            if key_name:
                # 如果正在录制，记录按键
                if self._recorder.is_recording():
                    self._record_key(key_name)

                # 更新状态和按下时间
                with self._state_lock:
                    if key_name in self._key_states:
                        self._key_states[key_name] = True
                        self._key_press_times[key_name] = time.time()

                # 检测组合快捷键
                self._check_hotkey_combinations()

        except Exception as e:
            logger.error("Error in key press handler: %s", str(e))

    def _on_key_release(self, key):
        """键盘按键释放事件处理"""
        try:
            key_name = self._get_key_name(key)
            if key_name:
                with self._state_lock:
                    if key_name in self._key_states:
                        self._key_states[key_name] = False
                    # 清理按键时间记录
                    if key_name in self._key_press_times:
                        del self._key_press_times[key_name]

        except Exception as e:
            logger.error("Error in key release handler: %s", str(e))

    def _on_mouse_click(self, _x, _y, button, pressed):
        """鼠标点击事件处理"""
        try:
            mouse_name = self._get_mouse_name(button)
            if mouse_name:
                # 如果正在录制，记录鼠标按键
                if self._recorder.is_recording() and pressed:
                    self._record_key(mouse_name)

                # 更新状态和按下时间
                with self._state_lock:
                    if mouse_name in self._mouse_states:
                        self._mouse_states[mouse_name] = pressed
                        if pressed:
                            self._key_press_times[mouse_name] = time.time()

                # 检测组合快捷键
                if pressed:
                    self._check_hotkey_combinations()

        except Exception as e:
            logger.error("Error in mouse click handler: %s", str(e))

    def _get_key_name(self, key) -> Optional[str]:
        """获取按键名称"""
        try:
            if key in (keyboard.Key.shift_l, keyboard.Key.shift_r):
                return "shift"
            if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                return "ctrl"
            if key in (keyboard.Key.alt_l, keyboard.Key.alt_r):
                return "alt"
            if key in (keyboard.Key.cmd_l, keyboard.Key.cmd_r):
                return "win"
            if hasattr(key, "char") and key.char:
                return key.char.lower()
            if hasattr(key, "name"):
                return key.name.lower()
            return None
        except Exception:
            return None

    def _get_mouse_name(self, button) -> Optional[str]:
        """获取鼠标按键名称"""
        try:
            if button == mouse.Button.left:
                return "left"
            if button == mouse.Button.right:
                return "right"
            if button == mouse.Button.middle:
                return "middle"
            return None
        except Exception:
            return None

    def _check_hotkey_combinations(self):
        """检测所有键鼠组合快捷键"""
        # 检查冷却时间
        current_time = time.time()
        if current_time - self._last_trigger_time < self._trigger_cooldown:
            return

        # 复制当前状态
        with self._state_lock:
            key_states = self._key_states.copy()
            mouse_states = self._mouse_states.copy()

        triggered = False

        # 检测隐藏热键
        hide_parts = [p.strip().lower() for p in self._hide_hotkey_sequence.split("+")]
        if self._check_combination_match(hide_parts, key_states, mouse_states):
            if self._hide_callback:
                logger.debug("Hide hotkey triggered: %s", self._hide_hotkey_sequence)
                self._execute_callback_safely(self._hide_callback, "hide")
                triggered = True
                self._reset_mouse_states(hide_parts)

        # 检测显示热键
        if not triggered:
            show_parts = [
                p.strip().lower() for p in self._show_hotkey_sequence.split("+")
            ]
            if self._check_combination_match(show_parts, key_states, mouse_states):
                if self._show_callback:
                    logger.debug(
                        "Show hotkey triggered: %s", self._show_hotkey_sequence
                    )
                    self._execute_callback_safely(self._show_callback, "show")
                    triggered = True
                    self._reset_mouse_states(show_parts)

        # 检测切换窗口热键
        if not triggered:
            switch_parts = [
                p.strip().lower() for p in self._switch_hotkey_sequence.split("+")
            ]
            if self._check_combination_match(switch_parts, key_states, mouse_states):
                if self._switch_callback:
                    logger.debug(
                        "Switch hotkey triggered: %s", self._switch_hotkey_sequence
                    )
                    self._execute_callback_safely(self._switch_callback, "switch")
                    triggered = True
                    self._reset_mouse_states(switch_parts)

        if triggered:
            self._last_trigger_time = current_time

    def _check_combination_match(
        self, parts: list, key_states: Dict, mouse_states: Dict
    ) -> bool:
        """检查组合键是否匹配（支持时间差）"""
        # 检查所有按键是否都按下了
        pressed_keys = []
        for part in parts:
            part_lower = self._normalize_key_name(part)
            if part_lower in key_states:
                if not key_states[part_lower]:
                    return False
                pressed_keys.append(part_lower)
            elif part_lower in mouse_states:
                if not mouse_states[part_lower]:
                    return False
                pressed_keys.append(part_lower)
            else:
                return False

        # 检查按键按下的时间差是否在阈值以内
        if not pressed_keys:
            return False

        # 获取所有按键的按下时间
        press_times = []
        current_time = time.time()

        for key in pressed_keys:
            if key in self._key_press_times:
                press_time = self._key_press_times[key]
                # 检查按键按下时间是否在当前时间的阈值范围内
                if current_time - press_time <= self._combo_time_threshold:
                    press_times.append(press_time)
                else:
                    return False
            else:
                return False

        # 检查所有按键的时间差是否在阈值以内
        if len(press_times) >= 2:
            press_times.sort()
            time_diff = press_times[-1] - press_times[0]
            if time_diff > self._combo_time_threshold:
                return False

        return True

    def _normalize_key_name(self, name: str) -> str:
        """标准化按键名称"""
        name = name.lower()
        mapping = {
            "lbutton": "left",
            "rbutton": "right",
            "mbutton": "middle",
            "lb": "left",
            "rb": "right",
            "mb": "middle",
        }
        return mapping.get(name, name)

    def _reset_mouse_states(self, parts: list):
        """重置鼠标状态"""
        with self._state_lock:
            for part in parts:
                part_lower = self._normalize_key_name(part)
                if part_lower in self._mouse_states:
                    self._mouse_states[part_lower] = False

    def _execute_callback_safely(self, callback: Callable, callback_name: str):
        """安全执行回调函数"""
        try:
            if not callable(callback):
                logger.warning("Callback %s is not callable", callback_name)
                return

            callback()
            logger.debug("Directly executed %s callback", callback_name)

        except Exception as e:
            logger.error("Error executing %s callback: %s", callback_name, str(e))

    def stop(self):
        """停止热键监听"""
        if not self._running:
            return

        logger.info("Stopping hotkey manager...")
        self._running = False

        if self._keyboard_listener:
            try:
                self._keyboard_listener.stop()
            except Exception as e:
                logger.warning("Error stopping keyboard listener: %s", str(e))

        if self._mouse_listener:
            try:
                self._mouse_listener.stop()
            except Exception as e:
                logger.warning("Error stopping mouse listener: %s", str(e))

        self._cleanup()
        logger.info("Hotkey manager stopped")

    def _cleanup(self):
        """清理资源"""
        self._keyboard_listener = None
        self._mouse_listener = None

        with self._state_lock:
            for key in self._key_states:
                self._key_states[key] = False
            for key in self._mouse_states:
                self._mouse_states[key] = False

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
        return self._recorder.start_recording(callback, realtime_update_callback)

    def stop_recording(self) -> Optional[str]:
        """停止录制快捷键

        Returns:
            Optional[str]: 录制的快捷键字符串
        """
        return self._recorder.stop_recording()

    def check_health(self) -> None:
        """热键健康检查（实际检查监听器线程存活状态）"""
        if not self._running:
            return

        keyboard_alive = self._keyboard_listener.is_alive() if self._keyboard_listener else False
        mouse_alive = self._mouse_listener.is_alive() if self._mouse_listener else False

        if not keyboard_alive or not mouse_alive:
            logger.warning("热键监听器异常 - 键盘存活: %s, 鼠标存活: %s", keyboard_alive, mouse_alive)
            self._restart_listeners()
        else:
            logger.debug("热键管理器健康检查正常")

    def _restart_listeners(self) -> None:
        """重启崩溃的监听器"""
        with self._lock:
            try:
                # 停止残留的监听器
                if self._keyboard_listener:
                    try:
                        self._keyboard_listener.stop()
                    except Exception:
                        pass
                if self._mouse_listener:
                    try:
                        self._mouse_listener.stop()
                    except Exception:
                        pass

                self._cleanup()

                # 重新启动监听器
                if not PYNPUT_AVAILABLE:
                    logger.error("pynput 不可用，无法重启监听器")
                    return

                self._keyboard_listener = keyboard.Listener(
                    on_press=self._on_key_press, on_release=self._on_key_release
                )
                self._keyboard_listener.start()

                self._mouse_listener = mouse.Listener(on_click=self._on_mouse_click)
                self._mouse_listener.start()

                logger.info("热键监听器已重启完成")
            except Exception as e:
                logger.error("重启热键监听器失败: %s", str(e))
                self._running = False

    def _record_key(self, key_name: str):
        """记录按键（录制模式下）"""
        self._recorder.record_key(key_name)
