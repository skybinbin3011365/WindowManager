# windowmanager/hotkey_manager.py
"""
全局热键管理器（使用Windows API）
"""

import threading
import time
import ctypes
from ctypes import wintypes
from typing import Optional, Callable, Any, List, Dict
import logging

# 支持开发和打包环境的导入方式
try:
    from .constants import (
        HOTKEY_TIME_WINDOW, HOTKEY_POLLING_INTERVAL, HOTKEY_RECORDING_INTERVAL,
        HOTKEY_ERROR_SLEEP, DEFAULT_HOTKEY_TIMEOUT
    )
except ImportError:
    from constants import (
        HOTKEY_TIME_WINDOW, HOTKEY_POLLING_INTERVAL, HOTKEY_RECORDING_INTERVAL,
        HOTKEY_ERROR_SLEEP, DEFAULT_HOTKEY_TIMEOUT
    )

# 尝试导入tkinter，用于检测窗口是否存在
try:
    import tkinter as tk
    TK_AVAILABLE = True
except ImportError:
    TK_AVAILABLE = False
    tk = None

logger = logging.getLogger(__name__)

# Windows API 常量
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_SHIFT = 0x10
VK_LWIN = 0x5B
VK_RWIN = 0x5C
WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
HC_ACTION = 0
WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
WM_LBUTTONDOWN = 0x0201
WM_RBUTTONDOWN = 0x0204
WM_MBUTTONDOWN = 0x0207
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
WM_KEYUP = 0x0101
WM_SYSKEYUP = 0x0105

# 定义Windows API函数
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# 定义回调函数类型
HOOKPROC = ctypes.CFUNCTYPE(
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.POINTER(ctypes.c_ulong)
)

# 定义KBDLLHOOKSTRUCT结构体
class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", ctypes.c_ulong),
        ("scanCode", ctypes.c_ulong),
        ("flags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
    ]

# 定义MSLLHOOKSTRUCT结构体
class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", wintypes.POINT),
        ("mouseData", ctypes.c_ulong),
        ("flags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
    ]


class HotkeyManager:
    """全局热键管理器（使用Windows API）

    提供全局热键注册、监听和录制功能，支持键盘和鼠标按键组合
    支持两种模式：钩子模式和轮询模式
    """

    def __init__(self):
        self._running = False
        self._lock = threading.RLock()
        self._key_sequence_lock = threading.RLock()  # 专门用于保护 _key_sequence

        # 热键配置
        self._hotkeys = []

        # 按键序列检测
        self._key_sequence = []
        self._last_key_time = 0
        self._time_window = HOTKEY_TIME_WINDOW  # 使用常量

        # 钩子相关
        self._keyboard_hook = None
        self._mouse_hook = None
        self._hook_thread = None
        self._stop_event = threading.Event()
        self._use_hook = True  # 是否使用钩子模式

        # 钩子回调函数
        self._keyboard_hook_proc = None
        self._mouse_hook_proc = None

        # 回调函数
        self._hide_callback = None
        self._show_callback = None

        # 热键序列
        self._hide_hotkey_sequence = "Middle+Right"
        self._show_hotkey_sequence = "Shift+Right"

        # 录制相关 - 添加录制锁保护竞态条件
        self._recording = False
        self._recording_lock = threading.Lock()
        self._recording_start_time = 0.0
        self._recording_timeout = DEFAULT_HOTKEY_TIMEOUT  # 使用常量
        self._recorded_keys = []
        self._recording_callback = None
        self._realtime_update_callback = None

    def _add_to_key_sequence(self, item):
        """线程安全地添加按键到序列"""
        with self._key_sequence_lock:
            self._key_sequence.append(item)

    def _clear_key_sequence(self):
        """线程安全地清空按键序列"""
        with self._key_sequence_lock:
            self._key_sequence.clear()

    def _get_key_sequence_copy(self):
        """线程安全地获取按键序列副本"""
        with self._key_sequence_lock:
            return self._key_sequence.copy()

    def _get_key_sequence_length(self):
        """线程安全地获取按键序列长度"""
        with self._key_sequence_lock:
            return len(self._key_sequence)

    def register_hotkey(self,
                       hotkey_config: Dict[str, Any],
                       callback: Callable[[], None] = None,
                       name: str = "unnamed") -> bool:
        """注册全局热键

        Args:
            hotkey_config: 热键配置，包含按键序列和时间窗口
            callback: 热键触发时的回调函数
            name: 热键名称

        Returns:
            bool: 是否成功注册
        """
        if not callable(callback):
            logger.error("Hotkey callback must be callable")
            return False

        with self._lock:
            self._hotkeys.append({
                'config': hotkey_config,
                'callback': callback,
                'name': name
            })
            logger.info("Registered hotkey: %s", name)
            return True

    def register_hide_hotkey(self, callback: Callable[[], None], hotkey_sequence: str = "Middle+Right"):
        """注册隐藏窗口热键回调

        Args:
            callback: 热键触发时的回调函数
            hotkey_sequence: 热键序列字符串，默认为"Middle+Right"
        """
        self._hide_callback = callback
        self._hide_hotkey_sequence = hotkey_sequence

    def register_show_hotkey(self, callback: Callable[[], None], hotkey_sequence: str = "Shift+Right"):
        """注册显示窗口热键回调

        Args:
            callback: 热键触发时的回调函数
            hotkey_sequence: 热键序列字符串，默认为"Shift+Right"
        """
        self._show_callback = callback
        self._show_hotkey_sequence = hotkey_sequence

    def start(self) -> bool:
        """启动热键监听"""
        if self._running:
            logger.warning("Hotkey manager already running")
            return True

        try:
            self._running = True
            self._stop_event.clear()

            # 根据配置选择启动模式
            if self._use_hook:
                # 使用钩子模式
                if not self._set_hooks():
                    logger.error("Failed to set hooks")
                    self._cleanup()
                    return False

                # 启动钩子消息循环
                self._hook_thread = threading.Thread(
                    target=self._hook_message_loop,
                    name="HotkeyHookLoop",
                    daemon=True
                )
                self._hook_thread.start()
                logger.info("Hotkey manager started with hook mode")
            else:
                # 使用轮询模式
                self._poll_thread = threading.Thread(
                    target=self._polling_loop,
                    name="HotkeyPollingLoop",
                    daemon=True
                )
                self._poll_thread.start()
                logger.info("Hotkey manager started with polling mode")

            return True
        except Exception as e:
            logger.error("Failed to start hotkey manager: %s", str(e))
            self._cleanup()
            return False

    def _polling_loop(self):
        """轮询模式下的热键检测"""
        logger.info("Starting hotkey polling loop")

        # 按键状态跟踪
        key_states = {}
        mouse_states = {}
        last_check_time = 0
        check_interval = HOTKEY_POLLING_INTERVAL  # 使用常量

        # 虚拟键码到名称的映射
        vk_to_name = {
            # 修饰键
            VK_CONTROL: "ctrl",
            VK_MENU: "alt",
            VK_SHIFT: "shift",
            VK_LWIN: "win",
            VK_RWIN: "win",
        }

        # 鼠标按键到名称的映射
        mouse_buttons = {
            0x01: "Left",  # 鼠标左键
            0x02: "Right",  # 鼠标右键
            0x04: "Middle",  # 鼠标中键
        }

        while self._running and not self._stop_event.is_set():
            try:
                current_time = time.time()
                elapsed = current_time - last_check_time

                if elapsed < check_interval:
                    # 计算实际需要睡眠的时间
                    sleep_time = check_interval - elapsed
                    time.sleep(sleep_time)
                    continue

                last_check_time = current_time

                # 检查时间窗口（使用线程安全方法）
                if current_time - self._last_key_time > self._time_window:
                    self._clear_key_sequence()

                # 检测键盘按键
                for vk_code, key_name in vk_to_name.items():
                    if ctypes.windll.user32.GetAsyncKeyState(vk_code) & 0x8000:
                        # 只在按键按下时记录
                        if not key_states.get(vk_code, False):
                            key_states[vk_code] = True
                            self._add_to_key_sequence(('key', key_name))
                            self._last_key_time = current_time
                            self._check_key_sequences()
                    else:
                        key_states[vk_code] = False

                # 检测鼠标按键
                for mouse_code, mouse_name in mouse_buttons.items():
                    if ctypes.windll.user32.GetAsyncKeyState(mouse_code) & 0x8000:
                        # 只在按键按下时记录
                        if not mouse_states.get(mouse_code, False):
                            mouse_states[mouse_code] = True
                            # 使用小写鼠标按键名称，确保与预期热键匹配
                            self._add_to_key_sequence(('mouse', mouse_name.lower()))
                            self._last_key_time = current_time
                            self._check_key_sequences()
                    else:
                        mouse_states[mouse_code] = False

            except Exception as e:
                logger.warning("Error in hotkey polling loop: %s", str(e))
                time.sleep(HOTKEY_ERROR_SLEEP)

    def _get_key_name(self, key_code):
        """获取按键名称"""
        key_map = {
            VK_CONTROL: "ctrl",
            VK_MENU: "alt",
            VK_SHIFT: "shift",
            VK_LWIN: "win",
            VK_RWIN: "win",
            0x20: "space",
            0x0D: "enter",
            0x1B: "esc",
            0x08: "backspace",
            0x09: "tab",
        }

        # 功能键
        if 0x70 <= key_code <= 0x7B:
            return f"f{key_code - 0x6F}"

        # 字母键
        if 0x41 <= key_code <= 0x5A:
            return chr(key_code).lower()

        # 数字键
        if 0x30 <= key_code <= 0x39:
            return chr(key_code)

        return key_map.get(key_code, None)

    def _get_mouse_button_name(self, wParam):
        """获取鼠标按键名称"""
        mouse_map = {
            WM_LBUTTONDOWN: "left",
            WM_RBUTTONDOWN: "right",
            WM_MBUTTONDOWN: "middle"
        }
        return mouse_map.get(wParam, None)

    def _standardize_key_sequence(self, key_sequence: list) -> list:
        """标准化按键序列

        Args:
            key_sequence: 原始按键序列

        Returns:
            标准化后的按键序列
        """
        current_sequence = []
        for item in key_sequence:
            if item[0] == 'key':
                current_sequence.append(item[1])
            elif item[0] == 'mouse':
                current_sequence.append(item[1])
        return current_sequence

    def _standardize_hotkey_part(self, part: str) -> str:
        """标准化热键部分

        Args:
            part: 热键部分

        Returns:
            标准化后的热键部分
        """
        expected_norm = part.lower()
        # 标准化鼠标按键名称
        if expected_norm in ['lbutton', 'left']:
            expected_norm = 'left'
        elif expected_norm in ['rbutton', 'right']:
            expected_norm = 'right'
        elif expected_norm in ['mbutton', 'middle']:
            expected_norm = 'middle'
        return expected_norm

    def _is_sequence_match(self, current_sequence: list, expected_sequence: list) -> bool:
        """检查按键序列是否匹配

        Args:
            current_sequence: 当前按键序列
            expected_sequence: 期望的按键序列

        Returns:
            bool: 是否匹配
        """
        if len(current_sequence) != len(expected_sequence):
            return False

        for i, expected in enumerate(expected_sequence):
            expected_norm = self._standardize_hotkey_part(expected)
            if current_sequence[i] != expected_norm:
                return False

        return True

    def _execute_callback_safely(self, callback: Callable, callback_name: str):
        """安全执行回调函数

        Args:
            callback: 回调函数
            callback_name: 回调名称（用于日志）
        """
        # 在单独的线程中执行回调，避免阻塞热键检测
        def execute_callback():
            # 尝试使用线程安全的方式调用回调
            try:
                # 检查回调是否仍然有效
                if not callable(callback):
                    logger.warning("Callback %s is no longer callable", callback_name)
                    return

                # 检查是否有after方法（Tkinter widget）
                if hasattr(callback, 'after'):
                    # 检查窗口是否仍然存在
                    try:
                        callback.winfo_exists()
                    except Exception:
                        # TclError或其他异常，窗口可能已不存在
                        logger.warning("Window for callback %s no longer exists", callback_name)
                        return
                    callback.after(0, callback)
                else:
                    # 直接调用
                    callback()
            except Exception as e:
                logger.error("Error calling %s callback: %s", callback_name, str(e), exc_info=True)

        threading.Thread(
            target=execute_callback,
            daemon=True
        ).start()

    def _check_hide_hotkey(self, current_sequence: list) -> bool:
        """检查隐藏窗口热键

        Args:
            current_sequence: 当前按键序列

        Returns:
            bool: 是否触发了热键
        """
        if hasattr(self, '_hide_hotkey_sequence') and self._hide_callback:
            expected_hide = self._hide_hotkey_sequence.split('+')
            if self._is_sequence_match(current_sequence, expected_hide):
                logger.debug("Hide hotkey triggered: %s", self._hide_hotkey_sequence)
                self._execute_callback_safely(self._hide_callback, "hide")
                self._clear_key_sequence()
                return True
        return False

    def _check_show_hotkey(self, current_sequence: list) -> bool:
        """检查显示窗口热键

        Args:
            current_sequence: 当前按键序列

        Returns:
            bool: 是否触发了热键
        """
        if hasattr(self, '_show_hotkey_sequence') and self._show_callback:
            expected_show = self._show_hotkey_sequence.split('+')
            if self._is_sequence_match(current_sequence, expected_show):
                logger.debug("Show hotkey triggered: %s", self._show_hotkey_sequence)
                self._execute_callback_safely(self._show_callback, "show")
                self._clear_key_sequence()
                return True
        return False

    def _check_custom_hotkeys(self, current_sequence: list) -> bool:
        """检查自定义热键

        Args:
            current_sequence: 标准化后的按键序列

        Returns:
            bool: 是否触发了热键
        """
        # 检查隐藏窗口热键
        if hasattr(self, '_hide_hotkey_sequence'):
            if self._check_hide_hotkey(current_sequence):
                return True

        # 检查显示窗口热键
        if hasattr(self, '_show_hotkey_sequence'):
            if self._check_show_hotkey(current_sequence):
                return True

        return False

    def _check_default_hotkeys(self) -> bool:
        """检查默认热键

        Returns:
            bool: 是否触发了热键
        """
        key_seq = self._get_key_sequence_copy()
        
        # 确保按键序列长度为2
        if len(key_seq) != 2:
            return False

        # 默认隐藏窗口热键：鼠标中键 + 鼠标右键
        if (key_seq[0] == ('mouse', 'middle') and
            key_seq[1] == ('mouse', 'right')):
            if self._hide_callback:
                logger.debug("Default hide hotkey triggered: Middle+Right")
                self._execute_callback_safely(self._hide_callback, "hide")
                self._clear_key_sequence()
                return True

        # 默认显示窗口热键：Shift + 鼠标右键
        elif (key_seq[0] == ('key', 'shift') and
              key_seq[1] == ('mouse', 'right')):
            if self._show_callback:
                logger.debug("Default show hotkey triggered: Shift+Right")
                self._execute_callback_safely(self._show_callback, "show")
                self._clear_key_sequence()
                return True
        return False

    def _check_key_sequences(self) -> bool:
        """检查按键序列

        检查当前按键序列是否匹配隐藏窗口热键、显示窗口热键或默认热键
        当热键匹配时，执行相应的回调函数

        Returns:
            bool: 是否触发了热键
        """
        # 只检查两个按键的组合
        if self._get_key_sequence_length() != 2:
            return False

        # 标准化当前按键序列
        current_sequence = self._standardize_key_sequence(self._get_key_sequence_copy())

        # 检查自定义热键
        if self._check_custom_hotkeys(current_sequence):
            return True

        # 检查默认热键
        return self._check_default_hotkeys()

    def stop(self):
        """安全停止热键监听"""
        if not self._running:
            return

        logger.info("Stopping hotkey manager...")
        self._running = False
        self._stop_event.set()

        # 等待轮询线程结束
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=2.0)

        # 等待钩子线程结束
        if self._hook_thread and self._hook_thread.is_alive():
            self._hook_thread.join(timeout=2.0)

        self._cleanup()
        logger.info("Hotkey manager stopped")

    def _cleanup(self):
        """清理资源"""
        with self._lock:
            self._hotkeys.clear()
        self._running = False
        self._clear_key_sequence()
        self._poll_thread = None
        self._hook_thread = None

        # 清理钩子资源
        self._unset_hooks()

    def check_hotkey_conflict(self, hotkey_sequence: str) -> bool:
        """检查热键是否与其他进程冲突

        Args:
            hotkey_sequence: 热键序列字符串，如"Shift+Right"

        Returns:
            bool: True表示热键已被占用，False表示热键可用
        """
        try:
            # 解析热键序列
            parts = hotkey_sequence.split('+')
            if len(parts) < 2:
                return True  # 热键序列至少需要两个键

            # 检查是否包含鼠标按键
            mouse_buttons = {"left", "right", "middle", "lbutton", "rbutton", "mbutton"}
            has_mouse_button = False
            for part in parts:
                if part.lower() in mouse_buttons:
                    has_mouse_button = True
                    break

            # 如果包含鼠标按键，直接返回False（鼠标按键组合不会与系统热键冲突）
            if has_mouse_button:
                logger.debug("Hotkey contains mouse button, assuming no conflict: %s", hotkey_sequence)
                return False

            # 检查修饰键
            valid_modifiers = {"ctrl", "alt", "shift", "win"}
            has_modifier = False
            for part in parts:
                if part.lower() in valid_modifiers:
                    has_modifier = True
                    break

            if not has_modifier:
                return True  # 热键序列必须包含至少一个修饰键

            # 检查按键码
            key_code = 0
            for part in parts:
                if part.lower() not in valid_modifiers:
                    key_code = self._get_virtual_key_code(part)
                    break

            if key_code == 0:
                return True  # 无法获取有效的按键码

            # 计算修饰键标志
            mod_flags = 0
            for part in parts:
                part_lower = part.lower()
                if part_lower == "ctrl":
                    mod_flags |= MOD_CONTROL
                elif part_lower == "alt":
                    mod_flags |= MOD_ALT
                elif part_lower == "shift":
                    mod_flags |= MOD_SHIFT
                elif part_lower == "win":
                    mod_flags |= MOD_WIN

            # 使用Windows API尝试注册热键来检测冲突
            # 临时注册热键，然后立即注销
            temp_hotkey_id = 9999  # 临时ID
            try:
                # 尝试注册热键
                success = ctypes.windll.user32.RegisterHotKey(0, temp_hotkey_id, mod_flags, key_code)
                if success:
                    # 注册成功，说明热键未被占用
                    # 立即注销热键
                    ctypes.windll.user32.UnregisterHotKey(0, temp_hotkey_id)
                    return False
                else:
                    # 注册失败，说明热键已被占用
                    return True
            except Exception:
                # 如果Windows API调用失败，回退到简单检查
                return False
        except Exception as e:
            logger.error("Error checking hotkey conflict: %s", str(e))
            return False

    def _get_virtual_key_code(self, key_name: str) -> int:
        """获取虚拟按键码

        Args:
            key_name: 按键名称

        Returns:
            int: 虚拟按键码
        """
        key_map = {
            "backspace": 0x08,
            "tab": 0x09,
            "enter": 0x0D,
            "shift": 0x10,
            "ctrl": 0x11,
            "alt": 0x12,
            "space": 0x20,
            "left": 0x25,
            "up": 0x26,
            "right": 0x27,
            "down": 0x28,
            "delete": 0x2E,
            "f1": 0x70,
            "f2": 0x71,
            "f3": 0x72,
            "f4": 0x73,
            "f5": 0x74,
            "f6": 0x75,
            "f7": 0x76,
            "f8": 0x77,
            "f9": 0x78,
            "f10": 0x79,
            "f11": 0x7A,
            "f12": 0x7B
        }

        # 检查是否是字母键
        if len(key_name) == 1 and key_name.isalpha():
            return ord(key_name.upper())

        # 检查是否是数字键
        if len(key_name) == 1 and key_name.isdigit():
            return ord(key_name)

        return key_map.get(key_name.lower(), 0)

    def start_recording(self, callback: Callable[[Optional[str]], None], realtime_update_callback: Optional[Callable[[str], None]] = None) -> bool:
        """开始录制快捷键

        Args:
            callback: 录制完成后的回调函数，参数为录制的快捷键字符串或None（如果超时）
            realtime_update_callback: 录制过程中的实时更新回调函数，参数为当前录制的快捷键字符串

        Returns:
            bool: 是否成功开始录制
        """
        with self._recording_lock:
            if self._recording:
                logger.warning("Recording already in progress, please wait for current recording to complete")
                return False

            try:
                # 清理之前的回调引用，避免内存泄漏
                self._recording_callback = None
                self._realtime_update_callback = None

                # 重置录制状态
                self._recording = True
                self._recording_start_time = time.time()
                self._recorded_keys = []
                self._recording_callback = callback
                self._realtime_update_callback = realtime_update_callback

                logger.info("Started recording hotkey...")
            except Exception as e:
                logger.error("Failed to initialize recording: %s", str(e))
                self._recording = False
                self._recording_callback = None
                self._realtime_update_callback = None
                return False

        # 在锁外启动线程，避免死锁
        try:
            # 启动录制超时线程
            threading.Thread(
                target=self._recording_timeout_handler,
                daemon=True
            ).start()

            # 启动轮询录制
            threading.Thread(
                target=self._polling_recording,
                daemon=True
            ).start()

            return True
        except Exception as e:
            logger.error("Failed to start recording threads: %s", str(e))
            with self._recording_lock:
                self._recording = False
                self._recording_callback = None
                self._realtime_update_callback = None
            return False

    def stop_recording(self) -> Optional[str]:
        """停止录制快捷键

        Returns:
            Optional[str]: 录制的快捷键字符串或None（如果没有录制到）
        """
        with self._recording_lock:
            if not self._recording:
                return None

            self._recording = False
            recorded_keys = self._recorded_keys.copy()

        if recorded_keys:
            formatted_keys = [self._format_hotkey_key_name(key) for key in self._recorded_keys]
            hotkey_str = "+".join(formatted_keys)
            logger.info("Stopped recording, got: %s", hotkey_str)
            return hotkey_str
        else:
            logger.info("Stopped recording, no keys recorded")
            return None

    def _format_hotkey_key_name(self, key: str) -> str:
        """格式化热键按键名称为Windows标准格式

        Args:
            key: 按键名称

        Returns:
            str: 格式化后的按键名称
        """
        if key == "ctrl":
            return "Ctrl"
        elif key == "alt":
            return "Alt"
        elif key == "shift":
            return "Shift"
        elif key == "win":
            return "Win"
        elif key == "Left":
            return "LButton"
        elif key == "Right":
            return "RButton"
        elif key == "Middle":
            return "MButton"
        else:
            return key

    def _format_recorded_keys(self) -> Optional[str]:
        """格式化录制的按键序列

        Returns:
            Optional[str]: 格式化后的热键字符串或None
        """
        if not self._recorded_keys:
            return None

        formatted_keys = [self._format_hotkey_key_name(key) for key in self._recorded_keys]
        return "+".join(formatted_keys)

    def _recording_timeout_handler(self):
        """录制超时处理"""
        try:
            while True:
                with self._recording_lock:
                    if not self._recording:
                        break
                    elapsed = time.time() - self._recording_start_time
                    if elapsed >= self._recording_timeout:
                        logger.info("Hotkey recording timed out (1 second)")
                        self._recording = False
                        callback = self._recording_callback
                        break
                time.sleep(0.1)
            else:
                return

            # 在锁外执行回调
            if callback:
                try:
                    hotkey_str = self._format_recorded_keys()
                    callback(hotkey_str)
                except Exception as e:
                    logger.error("Error calling recording callback: %s", str(e))
        except Exception as e:
            logger.error("Error in recording timeout handler: %s", str(e))
        finally:
            # 清理回调引用，避免内存泄漏
            with self._recording_lock:
                self._recording_callback = None
                self._realtime_update_callback = None
            logger.info("Recording timeout handler completed")

    def _polling_recording(self):
        """轮询模式下的热键录制"""
        logger.info("Starting polling-based hotkey recording")

        # 记录开始时间，用于检测超时
        start_time = time.time()

        try:
            # 按键状态跟踪
            key_states = {}
            mouse_states = {}
            last_check_time = 0
            check_interval = HOTKEY_RECORDING_INTERVAL  # 使用常量

            # 虚拟键码到名称的映射
            vk_to_name = {
                # 修饰键
                VK_CONTROL: "ctrl",
                VK_MENU: "alt",
                VK_SHIFT: "shift",
                VK_LWIN: "win",
                VK_RWIN: "win",
                # 功能键
                0x70: "f1", 0x71: "f2", 0x72: "f3", 0x73: "f4",
                0x74: "f5", 0x75: "f6", 0x76: "f7", 0x77: "f8",
                0x78: "f9", 0x79: "f10", 0x7A: "f11", 0x7B: "f12",
                # 其他常用键
                0x20: "space", 0x0D: "enter", 0x1B: "esc",
                0x08: "backspace", 0x09: "tab",
                # 方向键
                0x25: "left", 0x26: "up", 0x27: "right", 0x28: "down"
            }

            # 鼠标按键到名称的映射
            mouse_buttons = {
                0x01: "Left",  # 鼠标左键
                0x02: "Right",  # 鼠标右键
                0x04: "Middle",  # 鼠标中键
            }

            # 字母键
            for i in range(0x41, 0x5B):
                vk_to_name[i] = chr(i).lower()

            # 数字键
            for i in range(0x30, 0x3A):
                vk_to_name[i] = chr(i)

            while True:
                # 使用锁检查录制状态
                with self._recording_lock:
                    if not self._recording or self._stop_event.is_set():
                        break

                try:
                    # 检查是否超时
                    if time.time() - start_time > self._recording_timeout:
                        logger.info("Polling recording timed out")
                        break

                    current_time = time.time()
                    if current_time - last_check_time < check_interval:
                        time.sleep(check_interval)
                        continue
                    last_check_time = current_time

                    # 检测所有可能的键
                    for vk_code, key_name in vk_to_name.items():
                        # 使用锁检查录制状态
                        with self._recording_lock:
                            if not self._recording:
                                break
                        if ctypes.windll.user32.GetAsyncKeyState(vk_code) & 0x8000:
                            # 只在按键按下时记录
                            if not key_states.get(vk_code, False):
                                key_states[vk_code] = True

                                # 记录按键
                                if key_name not in self._recorded_keys:
                                    self._recorded_keys.append(key_name)
                                    logger.debug("Recorded key: %s", key_name)

                                    # 实时更新回调
                                    if self._realtime_update_callback:
                                        try:
                                            formatted_keys = [self._format_hotkey_key_name(key) for key in self._recorded_keys]
                                            current_hotkey = "+".join(formatted_keys)
                                            self._realtime_update_callback(current_hotkey)
                                        except Exception as e:
                                            logger.debug("Error in real-time update callback: %s", str(e))

                    # 检测鼠标按键
                    with self._recording_lock:
                        is_recording = self._recording
                    if not is_recording:
                        break
                    for mouse_code, mouse_name in mouse_buttons.items():
                        if ctypes.windll.user32.GetAsyncKeyState(mouse_code) & 0x8000:
                            # 只在按键按下时记录
                            if not mouse_states.get(mouse_code, False):
                                mouse_states[mouse_code] = True

                                # 记录鼠标按键
                                if mouse_name not in self._recorded_keys:
                                    self._recorded_keys.append(mouse_name)
                                    logger.debug("Recorded mouse button: %s", mouse_name)

                                    # 实时更新回调
                                    if self._realtime_update_callback:
                                        try:
                                            formatted_keys = [self._format_hotkey_key_name(key) for key in self._recorded_keys]
                                            current_hotkey = "+".join(formatted_keys)
                                            self._realtime_update_callback(current_hotkey)
                                        except Exception as e:
                                            logger.debug("Error in real-time update callback: %s", str(e))

                    # 重置未按下的键状态
                    for vk_code in list(key_states.keys()):
                        with self._recording_lock:
                            is_recording = self._recording
                        if not is_recording:
                            break
                        if not (ctypes.windll.user32.GetAsyncKeyState(vk_code) & 0x8000):
                            key_states[vk_code] = False

                    # 重置未按下的鼠标按键状态
                    for mouse_code in list(mouse_states.keys()):
                        with self._recording_lock:
                            is_recording = self._recording
                        if not is_recording:
                            break
                        if not (ctypes.windll.user32.GetAsyncKeyState(mouse_code) & 0x8000):
                            mouse_states[mouse_code] = False

                except Exception as e:
                    logger.warning("Error in polling recording: %s", str(e))
                    time.sleep(HOTKEY_ERROR_SLEEP)
                    # 即使出错也继续循环，确保录制能够正常结束
                    with self._recording_lock:
                        is_recording = self._recording
                    if not is_recording:
                        break
        except Exception as e:
            logger.error("Critical error in polling recording: %s", str(e))
        finally:
            # 确保录制状态被重置
            with self._recording_lock:
                if self._recording:
                    self._recording = False
                    logger.info("Force reset recording state in finally block")
                # 清理回调引用，避免内存泄漏
                self._recording_callback = None
                self._realtime_update_callback = None

    def _keyboard_hook_callback(self, nCode, wParam, lParam):
        """键盘钩子回调函数"""
        try:
            if nCode >= 0:
                # 只处理按键按下事件
                if wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    kb_struct = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                    vk_code = kb_struct.vkCode

                    # 获取按键名称
                    key_name = self._get_key_name(vk_code)
                    if key_name:
                        current_time = time.time()

                        # 检查时间窗口
                        if current_time - self._last_key_time > self._time_window:
                            self._clear_key_sequence()

                        # 添加按键到序列
                        self._add_to_key_sequence(('key', key_name))
                        self._last_key_time = current_time

                        # 检查热键序列
                        self._check_key_sequences()

            # 传递给下一个钩子
            return user32.CallNextHookEx(self._keyboard_hook, nCode, wParam, lParam)
        except Exception as e:
            logger.error("Error in keyboard hook callback: %s", str(e))
            return user32.CallNextHookEx(self._keyboard_hook, nCode, wParam, lParam)

    def _mouse_hook_callback(self, nCode, wParam, lParam):
        """鼠标钩子回调函数"""
        try:
            if nCode >= 0:
                current_time = time.time()
                
                # 检查时间窗口
                if current_time - self._last_key_time > self._time_window:
                    self._clear_key_sequence()

                # 只处理鼠标按下事件
                if wParam == WM_LBUTTONDOWN:
                    mouse_name = "left"
                elif wParam == WM_RBUTTONDOWN:
                    mouse_name = "right"
                elif wParam == WM_MBUTTONDOWN:
                    mouse_name = "middle"
                else:
                    return user32.CallNextHookEx(self._mouse_hook, nCode, wParam, lParam)

                # 添加按键到序列
                self._add_to_key_sequence(('mouse', mouse_name))
                self._last_key_time = current_time

                # 检查热键序列
                self._check_key_sequences()

            # 传递给下一个钩子
            return user32.CallNextHookEx(self._mouse_hook, nCode, wParam, lParam)
        except Exception as e:
            logger.error("Error in mouse hook callback: %s", str(e))
            return user32.CallNextHookEx(self._mouse_hook, nCode, wParam, lParam)

    def _set_hooks(self):
        """设置键盘和鼠标钩子"""
        keyboard_hook = None
        mouse_hook = None

        try:
            # 创建钩子回调函数
            self._keyboard_hook_proc = HOOKPROC(self._keyboard_hook_callback)
            self._mouse_hook_proc = HOOKPROC(self._mouse_hook_callback)

            # 设置键盘钩子
            keyboard_hook = user32.SetWindowsHookExW(
                WH_KEYBOARD_LL,
                self._keyboard_hook_proc,
                kernel32.GetModuleHandleW(None),
                0
            )

            if not keyboard_hook:
                logger.error("Failed to set keyboard hook")
                return False

            # 设置鼠标钩子
            mouse_hook = user32.SetWindowsHookExW(
                WH_MOUSE_LL,
                self._mouse_hook_proc,
                kernel32.GetModuleHandleW(None),
                0
            )

            if not mouse_hook:
                logger.error("Failed to set mouse hook")
                # 清理已设置的键盘钩子
                try:
                    user32.UnhookWindowsHookEx(keyboard_hook)
                except Exception:
                    pass
                return False

            # 只有在两个钩子都成功设置后才保存引用
            self._keyboard_hook = keyboard_hook
            self._mouse_hook = mouse_hook

            logger.info("Keyboard and mouse hooks set successfully")
            return True
        except Exception as e:
            logger.error("Error setting hooks: %s", str(e))
            # 清理可能已设置的钩子
            if keyboard_hook:
                try:
                    user32.UnhookWindowsHookEx(keyboard_hook)
                except Exception:
                    pass
            if mouse_hook:
                try:
                    user32.UnhookWindowsHookEx(mouse_hook)
                except Exception:
                    pass
            return False

    def _unset_hooks(self):
        """移除键盘和鼠标钩子"""
        try:
            if self._keyboard_hook:
                user32.UnhookWindowsHookEx(self._keyboard_hook)
                self._keyboard_hook = None

            if self._mouse_hook:
                user32.UnhookWindowsHookEx(self._mouse_hook)
                self._mouse_hook = None

            # 释放回调引用，避免内存泄漏
            self._keyboard_hook_proc = None
            self._mouse_hook_proc = None

            logger.info("Hooks removed successfully")
        except Exception as e:
            logger.error("Error removing hooks: %s", str(e))

    def _hook_message_loop(self):
        """钩子消息循环"""
        try:
            msg = wintypes.MSG()
            while self._running and not self._stop_event.is_set():
                # 获取消息，超时100ms
                result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if result == 0:  # WM_QUIT
                    break
                elif result == -1:  # 错误
                    logger.error("Error in message loop")
                    break
                else:
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
        except Exception as e:
            logger.error("Error in hook message loop: %s", str(e))
            logger.info("Polling-based hotkey recording stopped")
