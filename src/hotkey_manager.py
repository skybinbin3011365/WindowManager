# windowmanager/hotkey_manager.py
"""
全局热键管理器（使用pynput库实现钩子模式）
采用状态检测方式，检测按键是否同时按下
"""

import threading
import time
from typing import Optional, Callable, Dict
import logging

# 尝试导入pynput
try:
    from pynput import keyboard, mouse
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    keyboard = None
    mouse = None

logger = logging.getLogger(__name__)

# 默认录制超时时间（秒）
DEFAULT_RECORDING_TIMEOUT = 5.0


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
            'shift': False,
            'ctrl': False,
            'alt': False,
            'win': False
        }

        # 鼠标按键状态字典
        self._mouse_states: Dict[str, bool] = {
            'left': False,
            'right': False,
            'middle': False
        }

        # 状态锁
        self._state_lock = threading.Lock()

        # pynput监听器
        self._keyboard_listener = None
        self._mouse_listener = None

        # 回调函数
        self._hide_callback: Optional[Callable] = None
        self._show_callback: Optional[Callable] = None

        # 热键序列
        self._hide_hotkey_sequence = "Middle+Right"
        self._show_hotkey_sequence = "Shift+Right"

        # 录制相关
        self._recording = False
        self._recording_lock = threading.Lock()
        self._recording_start_time = 0.0
        self._recording_timeout = DEFAULT_RECORDING_TIMEOUT
        self._recorded_keys: list = []
        self._recording_callback: Optional[Callable] = None
        self._realtime_update_callback: Optional[Callable] = None

        # 防重复触发的冷却时间
        self._last_trigger_time = 0
        self._trigger_cooldown = 0.3

    def register_hide_hotkey(self, callback: Callable, hotkey_sequence: str = "Middle+Right"):
        """注册隐藏窗口热键回调

        Args:
            callback: 热键触发时的回调函数
            hotkey_sequence: 热键序列字符串，默认为"Middle+Right"
        """
        self._hide_callback = callback
        self._hide_hotkey_sequence = hotkey_sequence
        logger.info("Registered hide hotkey: %s", hotkey_sequence)

    def register_show_hotkey(self, callback: Callable, hotkey_sequence: str = "Shift+Right"):
        """注册显示窗口热键回调

        Args:
            callback: 热键触发时的回调函数
            hotkey_sequence: 热键序列字符串，默认为"Shift+Right"
        """
        self._show_callback = callback
        self._show_hotkey_sequence = hotkey_sequence
        logger.info("Registered show hotkey: %s", hotkey_sequence)

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
                on_press=self._on_key_press,
                on_release=self._on_key_release
            )
            self._keyboard_listener.start()

            # 启动鼠标监听器
            self._mouse_listener = mouse.Listener(
                on_click=self._on_mouse_click
            )
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
                if self._recording:
                    self._record_key(key_name)

                # 更新状态
                with self._state_lock:
                    if key_name in self._key_states:
                        self._key_states[key_name] = True

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

        except Exception as e:
            logger.error("Error in key release handler: %s", str(e))

    def _on_mouse_click(self, x, y, button, pressed):
        """鼠标点击事件处理"""
        try:
            mouse_name = self._get_mouse_name(button)
            if mouse_name:
                # 如果正在录制，记录鼠标按键
                if self._recording and pressed:
                    self._record_key(mouse_name)

                # 更新状态
                with self._state_lock:
                    if mouse_name in self._mouse_states:
                        self._mouse_states[mouse_name] = pressed

                # 检测组合快捷键
                if pressed:
                    self._check_hotkey_combinations()

        except Exception as e:
            logger.error("Error in mouse click handler: %s", str(e))

    def _get_key_name(self, key) -> Optional[str]:
        """获取按键名称"""
        try:
            # 处理修饰键
            if key in (keyboard.Key.shift_l, keyboard.Key.shift_r):
                return 'shift'
            elif key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                return 'ctrl'
            elif key in (keyboard.Key.alt_l, keyboard.Key.alt_r):
                return 'alt'
            elif key in (keyboard.Key.cmd_l, keyboard.Key.cmd_r):
                return 'win'
            # 处理普通字符键
            elif hasattr(key, 'char') and key.char:
                return key.char.lower()
            # 处理特殊键
            elif hasattr(key, 'name'):
                return key.name.lower()
            return None
        except Exception:
            return None

    def _get_mouse_name(self, button) -> Optional[str]:
        """获取鼠标按键名称"""
        try:
            if button == mouse.Button.left:
                return 'left'
            elif button == mouse.Button.right:
                return 'right'
            elif button == mouse.Button.middle:
                return 'middle'
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
        hide_parts = [p.strip().lower() for p in self._hide_hotkey_sequence.split('+')]
        if self._check_combination_match(hide_parts, key_states, mouse_states):
            if self._hide_callback:
                logger.debug("Hide hotkey triggered: %s", self._hide_hotkey_sequence)
                self._execute_callback_safely(self._hide_callback, "hide")
                triggered = True
                self._reset_mouse_states(hide_parts)

        # 检测显示热键
        if not triggered:
            show_parts = [p.strip().lower() for p in self._show_hotkey_sequence.split('+')]
            if self._check_combination_match(show_parts, key_states, mouse_states):
                if self._show_callback:
                    logger.debug("Show hotkey triggered: %s", self._show_hotkey_sequence)
                    self._execute_callback_safely(self._show_callback, "show")
                    triggered = True
                    self._reset_mouse_states(show_parts)

        if triggered:
            self._last_trigger_time = current_time

    def _check_combination_match(self, parts: list, key_states: Dict, mouse_states: Dict) -> bool:
        """检查组合键是否匹配"""
        for part in parts:
            part_lower = self._normalize_key_name(part)
            if part_lower in key_states:
                if not key_states[part_lower]:
                    return False
            elif part_lower in mouse_states:
                if not mouse_states[part_lower]:
                    return False
            else:
                return False
        return True

    def _normalize_key_name(self, name: str) -> str:
        """标准化按键名称"""
        name = name.lower()
        mapping = {
            'lbutton': 'left',
            'rbutton': 'right',
            'mbutton': 'middle'
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

            # 尝试获取Tkinter root对象
            root = self._get_tkinter_root(callback)

            if root and hasattr(root, 'after'):
                try:
                    if self._is_root_valid(root):
                        root.after(0, callback)
                        logger.debug("Scheduled %s callback via Tkinter after", callback_name)
                        return
                except Exception as e:
                    logger.warning("Failed to use Tkinter after: %s", str(e))

            # 降级：直接执行
            callback()
            logger.debug("Directly executed %s callback", callback_name)

        except Exception as e:
            logger.error("Error executing %s callback: %s", callback_name, str(e))

    def _get_tkinter_root(self, callback: Callable):
        """获取Tkinter root对象"""
        if hasattr(callback, '__self__'):
            obj = callback.__self__
            for attr in ('root', '_root', 'master'):
                if hasattr(obj, attr):
                    return getattr(obj, attr)
            if hasattr(obj, 'winfo_exists'):
                return obj
        return None

    def _is_root_valid(self, root) -> bool:
        """检查root窗口是否有效"""
        if hasattr(root, 'winfo_exists'):
            try:
                return root.winfo_exists()
            except Exception:
                pass
        return True

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

    # ==================== 热键录制功能 ====================

    def start_recording(self, callback: Callable[[Optional[str]], None],
                       realtime_update_callback: Optional[Callable[[str], None]] = None) -> bool:
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
        threading.Thread(target=self._recording_timeout_handler, daemon=True).start()
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
            hotkey_str = self._format_hotkey_string(recorded_keys)
            logger.info("Stopped recording, got: %s", hotkey_str)
            return hotkey_str

        logger.info("Stopped recording, no keys recorded")
        return None

    def _record_key(self, key_name: str):
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
                        hotkey_str = self._format_hotkey_string(self._recorded_keys)
                        self._realtime_update_callback(hotkey_str)
                    except Exception as e:
                        logger.warning("Error in realtime update callback: %s", str(e))

    def _format_hotkey_string(self, keys: list) -> str:
        """格式化热键字符串"""
        formatted = [self._format_key_name(k) for k in keys]
        return "+".join(formatted)

    def _format_key_name(self, key: str) -> str:
        """格式化单个按键名称"""
        mapping = {
            'ctrl': 'Ctrl',
            'alt': 'Alt',
            'shift': 'Shift',
            'win': 'Win',
            'left': 'LButton',
            'right': 'RButton',
            'middle': 'MButton'
        }
        if key in mapping:
            return mapping[key]
        return key.capitalize() if len(key) == 1 else key

    def _recording_timeout_handler(self):
        """录制超时处理"""
        callback = None
        hotkey_str = None

        while True:
            with self._recording_lock:
                if not self._recording:
                    return

                elapsed = time.time() - self._recording_start_time
                if elapsed >= self._recording_timeout:
                    self._recording = False
                    callback = self._recording_callback
                    hotkey_str = self._format_hotkey_string(self._recorded_keys) if self._recorded_keys else None
                    self._recording_callback = None
                    self._realtime_update_callback = None
                    break

            time.sleep(0.1)

        if callback:
            try:
                logger.info("Recording timed out, result: %s", hotkey_str)
                callback(hotkey_str)
            except Exception as e:
                logger.error("Error calling recording callback: %s", str(e))
