# windowmanager/config.py
"""
统一配置管理模块
整合所有配置相关的类和常量
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import stat
import threading
import sys
from dataclasses import dataclass, field, asdict
from typing import Optional

import logging

from constants import ConfigConstants, NTPConstants
from window_models import WindowEntry, WindowEntryState

logger = logging.getLogger(__name__)


@dataclass
class Config:
    """配置数据类

    包含所有应用程序配置项，提供默认值和类型提示
    """

    # 版本信息
    version: str = ConfigConstants.CONFIG_VERSION

    # 热键配置
    hide_hotkey: str = "MBUTTON+RBUTTON"
    show_hotkey: str = "SHIFT+RBUTTON"
    switch_hotkey: str = "CTRL+RBUTTON"  # 切换窗口热键（将指定进程的窗口恢复到前台）

    # 切换窗口配置：进程名列表，热键触发时恢复这些进程的窗口到前台
    switch_processes: list[str] = field(default_factory=list)  # 切换窗口的进程名列表（用户配置，默认为空）

    # 日志配置
    log_level: str = "INFO"
    enable_window_refresh_log: bool = True  # 是否启用窗口刷新日志
    enable_window_operation_log: bool = True  # 是否启用窗口操作日志
    enable_debug_log: bool = False  # 是否在日志面板显示 DEBUG 级别消息

    # 自动启动配置
    auto_start: bool = False
    auto_refresh_interval: float = 10.0

    # 窗口管理配置
    keywords: list[str] = field(default_factory=list)
    process_whitelist: list[str] = field(default_factory=list)
    auto_select_processes: list[str] = field(default_factory=list)  # 自动选中的进程名列表（用户配置，默认为空）

    # 重构：设定窗口列表，包含完整状态信息（符合用户文档要求）
    target_windows: list[dict] = field(default_factory=list)

    # UI 配置
    ui: dict = field(
        default_factory=lambda: {
            "width": 1000,
            "height": 700,
            "theme": "light",
            "hidden_columns": [],
        }
    )

    # 时间校准配置
    ntp_servers: list[str] = field(default_factory=lambda: NTPConstants.DEFAULT_NTP_SERVERS.copy())
    auto_sync_enabled: bool = False
    auto_sync_interval_hours: float = 1.0

    # NTP 时间同步配置
    ntp_check_interval: int = 60  # NTP 检查间隔（秒）
    ntp_error_threshold: int = 5  # NTP 误差阈值（秒）
    ntp_auto_calibrate: bool = False  # 是否启用自动校准
    enable_ntp_log: bool = True  # 是否启用 NTP 获取日志
    enable_timed_calibration: bool = True  # 是否启用定时校准
    calibration_interval: int = 30  # 校准周期（秒）


class ConfigManager:
    """统一的配置管理器

    负责配置文件的读取、写入、版本管理和延迟保存

    使用 get_instance() 类方法作为共享实例入口，
    避免多个模块各自创建独立 ConfigManager 实例导致配置不一致。
    """

    # 共享实例（单例模式）
    _shared_instance: Optional["ConfigManager"] = None
    _shared_instance_lock = threading.Lock()

    # 延迟保存的时间间隔（秒）
    SAVE_DELAY = 2.0

    @classmethod
    def get_instance(cls, config_dir: Optional[str] = None) -> "ConfigManager":
        """获取全局共享的 ConfigManager 实例（单例工厂）

        所有模块应通过此方法获取 ConfigManager 实例，
        而非直接调用 ConfigManager()，以确保观察者注册、
        配置缓存及延迟保存等状态全局一致。

        Args:
            config_dir: 可选的自定义配置目录（仅在首次创建时生效）

        Returns:
            ConfigManager: 共享的配置管理器实例
        """
        if cls._shared_instance is None:
            with cls._shared_instance_lock:
                if cls._shared_instance is None:
                    cls._shared_instance = cls(config_dir=config_dir)
        return cls._shared_instance

    def __init__(self, config_dir: Optional[str] = None):
        """初始化配置管理器

        Args:
            config_dir: 配置目录路径，如果为None则使用默认目录
        """
        # 优先使用 exe 同目录的配置文件
        if config_dir is None:
            if getattr(sys, "frozen", False):
                # 打包环境：使用 exe 同目录
                config_dir = pathlib.Path(sys.executable).parent
                self.config_dir = config_dir
                self.config_file = self.config_dir / "config.json"
            else:
                # 开发环境：使用项目根目录（src 的上级）
                config_dir = pathlib.Path(__file__).parent.parent
                self.config_dir = pathlib.Path(config_dir)
                self.config_file = self.config_dir / "config.json"
        else:
            # 自定义配置目录
            self.config_dir = pathlib.Path(config_dir)
            self.config_file = self.config_dir / "config.json"

        self._config: Optional[Config] = None

        # 延迟保存相关
        self._dirty = False
        self._save_timer: Optional[threading.Timer] = None
        self._save_lock = threading.Lock()

        # 观察者模式相关
        self._observers = []
        self._observer_lock = threading.Lock()

        self._ensure_config_dir()

    def _ensure_config_dir(self):
        """确保配置目录存在"""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            # 设置目录权限为仅所有者可访问
            try:
                os.chmod(self.config_dir, stat.S_IRWXU)
            except (OSError, AttributeError):
                # 某些系统不支持 chmod，忽略权限设置
                pass
        except Exception as e:
            logger.error("创建配置目录失败: %s", str(e))

    def load(self) -> Config:
        """加载配置

        Returns:
            Config: 配置对象
        """
        if self._config is None:
            self._config = Config()

            # 尝试加载配置文件
            logger.debug("尝试加载配置文件: %s", self.config_file)
            if self.config_file.exists():
                try:
                    with open(self.config_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    logger.debug("配置文件内容: %s", data)

                    # 安全地合并配置，确保所有字段都有值
                    config_dict = asdict(self._config)
                    # 过滤掉旧版本中已废弃的字段
                    valid_fields = set(config_dict.keys())
                    filtered_data = {k: v for k, v in data.items() if k in valid_fields}

                    # 验证配置数据的有效性
                    filtered_data = self._validate_config_data(filtered_data)

                    # 清理旧格式配置，防止数据冗余
                    filtered_data = self._cleanup_legacy_config(filtered_data)

                    config_dict.update(filtered_data)

                    self._config = Config(**config_dict)
                    logger.info("配置加载成功: %s", self.config_file)
                    logger.debug("加载后的配置: %s", asdict(self._config))
                except json.JSONDecodeError as e:
                    logger.warning("解析配置文件失败，使用默认配置: %s", str(e))
                    self._backup_corrupted_config()
                except PermissionError as e:
                    logger.warning("读取配置时权限不足: %s", str(e))
                except (OSError, IOError) as e:
                    logger.warning("加载配置文件失败，使用默认配置: %s", str(e))
                except TypeError as e:
                    logger.warning("配置类型无效，使用默认配置: %s", str(e))
                except Exception as e:
                    logger.warning("加载配置时发生未知错误，使用默认配置: %s", str(e))
            else:
                logger.debug("配置文件不存在: %s", self.config_file)

        logger.debug("最终配置: %s", asdict(self._config))
        return self._config

    def _validate_config_data(self, data: dict) -> dict:
        """验证配置数据的有效性

        Args:
            data: 原始配置数据

        Returns:
            dict: 验证后的配置数据
        """
        # 验证热键格式
        if "hide_hotkey" in data:
            if not self._validate_hotkey_format(data["hide_hotkey"]):
                logger.warning("隐藏热键格式无效: %s，使用默认值", data["hide_hotkey"])
                del data["hide_hotkey"]

        if "show_hotkey" in data:
            if not self._validate_hotkey_format(data["show_hotkey"]):
                logger.warning("显示热键格式无效: %s，使用默认值", data["show_hotkey"])
                del data["show_hotkey"]

        # 验证自动刷新间隔
        if "auto_refresh_interval" in data:
            if (
                not isinstance(data["auto_refresh_interval"], (int, float))
                or data["auto_refresh_interval"] < 0
            ):
                logger.warning("自动刷新间隔无效: %s，使用默认值", data["auto_refresh_interval"])
                del data["auto_refresh_interval"]

        # 验证 NTP 服务器列表
        if "ntp_servers" in data:
            if not isinstance(data["ntp_servers"], list) or not all(
                isinstance(s, str) for s in data["ntp_servers"]
            ):
                logger.warning("NTP服务器列表格式无效，使用默认值")
                del data["ntp_servers"]

        # 处理配置迁移和向后兼容性
        data = self._handle_config_migration(data)

        return data

    def _handle_config_migration(self, data: dict) -> dict:
        """处理配置迁移和向后兼容性

        将旧的 selected_windows 和 hidden_windows 迁移到新的 target_windows 格式
        同时保持向后兼容性

        Args:
            data: 原始配置数据

        Returns:
            dict: 迁移后的配置数据
        """
        # 检查是否需要迁移
        has_old_format = "selected_windows" in data or "hidden_windows" in data
        has_new_format = "target_windows" in data

        if has_old_format and not has_new_format:
            # 需要从旧格式迁移到新格式
            logger.info("检测到旧格式配置，开始迁移到新格式...")

            target_windows = []

            # 迁移选中窗口
            selected_windows = data.get("selected_windows", [])
            for window_info in selected_windows:
                if isinstance(window_info, dict):
                    process_name = window_info.get("process_name", "")
                    title = window_info.get("title", "")

                    if process_name and title:
                        entry = WindowEntry(
                            process_name=process_name,
                            title=title,
                            state=WindowEntryState.VISIBLE,
                            source="manual",
                        )
                        target_windows.append(entry.to_dict())
                        logger.debug("迁移选中窗口: %s - %s", process_name, title)

            # 迁移隐藏窗口
            hidden_windows = data.get("hidden_windows", [])
            for window_info in hidden_windows:
                if isinstance(window_info, dict):
                    process_name = window_info.get("process_name", "")
                    title = window_info.get("title", "")

                    if process_name and title:
                        # 检查是否已存在（避免重复）
                        exists = any(
                            w.get("process_name") == process_name and w.get("title") == title
                            for w in target_windows
                        )

                        if not exists:
                            entry = WindowEntry(
                                process_name=process_name,
                                title=title,
                                state=WindowEntryState.HIDDEN,
                                source="manual",
                            )
                            target_windows.append(entry.to_dict())
                            logger.debug("迁移隐藏窗口: %s - %s", process_name, title)

            # 更新数据
            data["target_windows"] = target_windows
            logger.info("配置迁移完成: %d 个窗口条目", len(target_windows))

        # 验证 target_windows 格式
        if "target_windows" in data:
            target_windows = data["target_windows"]
            if isinstance(target_windows, list):
                # 验证每个条目的格式
                valid_entries = []
                for entry in target_windows:
                    if isinstance(entry, dict) and all(
                        key in entry for key in ["process_name", "title", "state", "source"]
                    ):
                        valid_entries.append(entry)
                    else:
                        logger.warning("忽略无效的窗口条目: %s", entry)

                data["target_windows"] = valid_entries
            else:
                logger.warning("target_windows 格式无效，使用默认值")
                del data["target_windows"]

        # 迁移旧字段名到新字段名
        if "log_window_operations" in data and "enable_window_operation_log" not in data:
            data["enable_window_operation_log"] = data.pop("log_window_operations")

        return data

    def _cleanup_legacy_config(self, data: dict) -> dict:
        """清理旧格式配置，防止数据冗余

        Args:
            data: 配置数据

        Returns:
            dict: 清理后的配置数据
        """
        # 检查是否同时存在新旧格式配置
        has_old_format = "selected_windows" in data or "hidden_windows" in data
        has_new_format = "target_windows" in data and data["target_windows"]

        if has_old_format and has_new_format:
            # 记录清理操作
            old_selected_count = len(data.get("selected_windows", []))
            old_hidden_count = len(data.get("hidden_windows", []))
            new_count = len(data["target_windows"])

            logger.info(
                "清理旧格式配置: 选中窗口 %d -> 目标窗口 %d",
                old_selected_count + old_hidden_count,
                new_count,
            )

            # 移除旧格式配置
            data.pop("selected_windows", None)
            data.pop("hidden_windows", None)

        return data

    def _validate_hotkey_format(self, hotkey: str) -> bool:
        """验证热键格式是否有效

        Args:
            hotkey: 热键字符串

        Returns:
            bool: 是否有效
        """
        if not hotkey or not isinstance(hotkey, str):
            return False

        # 热键应该由 + 连接的多个部分组成
        parts = hotkey.split("+")
        if not parts:
            return False

        # 有效的按键名称
        valid_keys = {
            "shift",
            "ctrl",
            "alt",
            "win",
            "left",
            "right",
            "middle",
            "lbutton",
            "rbutton",
            "mbutton",
            "f1",
            "f2",
            "f3",
            "f4",
            "f5",
            "f6",
            "f7",
            "f8",
            "f9",
            "f10",
            "f11",
            "f12",
            "0",
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            "a",
            "b",
            "c",
            "d",
            "e",
            "f",
            "g",
            "h",
            "i",
            "j",
            "k",
            "l",
            "m",
            "n",
            "o",
            "p",
            "q",
            "r",
            "s",
            "t",
            "u",
            "v",
            "w",
            "x",
            "y",
            "z",
        }

        # 检查每个部分是否有效
        for part in parts:
            part_lower = part.strip().lower()
            if part_lower not in valid_keys:
                return False

        return True

    def _backup_corrupted_config(self):
        """备份损坏的配置文件"""
        if self.config_file.exists():
            try:
                backup_file = self.config_file.with_suffix(".json.bak")
                shutil.copy(self.config_file, backup_file)
                logger.info("损坏的配置已备份到: %s", backup_file)
            except (OSError, IOError) as e:
                logger.error("备份配置文件失败: %s", str(e))

    def save(self, config: Config, immediate: bool = False) -> bool:
        """保存配置

        Args:
            config: 配置对象
            immediate: 是否立即保存，默认为False（使用防抖机制）

        Returns:
            bool: 是否保存成功
        """
        self._config = config

        if immediate:
            return self._do_save()
        else:
            self._schedule_save()
            return True

    def _schedule_save(self):
        """安排延迟保存配置"""
        with self._save_lock:
            self._dirty = True

            if self._save_timer is not None:
                self._save_timer.cancel()

            self._save_timer = threading.Timer(self.SAVE_DELAY, self._delayed_save)
            self._save_timer.daemon = True
            self._save_timer.start()

    def _delayed_save(self):
        """延迟保存回调"""
        should_save = False
        with self._save_lock:
            if self._dirty:
                self._dirty = False
                self._save_timer = None
                should_save = True

        if should_save:
            self._do_save()

    def flush(self) -> bool:
        """强制保存所有未保存的配置

        Returns:
            bool: 是否保存成功
        """
        with self._save_lock:
            if self._save_timer is not None:
                self._save_timer.cancel()
                self._save_timer = None

            dirty = self._dirty
            self._dirty = False

        if dirty:
            return self._do_save()
        return True

    def close(self) -> None:
        """关闭配置管理器，取消延迟保存并尽量落盘

        用于应用退出时的资源收敛，避免 Timer 在线程中继续触发写入。
        """
        with self._save_lock:
            if self._save_timer is not None:
                try:
                    self._save_timer.cancel()
                except Exception:
                    pass
                self._save_timer = None

            dirty = self._dirty
            self._dirty = False

        if dirty:
            try:
                self._do_save()
            except Exception:
                # 退出阶段不抛异常，避免影响应用关闭流程
                pass

    def _do_save(self) -> bool:
        """执行实际的保存操作（改进权限处理和原子写入）

        Returns:
            bool: 是否保存成功
        """
        if self._config is None:
            return False

        try:
            # 序列化配置数据为明文 JSON
            config_data = json.dumps(asdict(self._config), ensure_ascii=False, indent=4)

            # 原子写入：先写入临时文件，然后重命名
            temp_file = self.config_file.with_suffix(".json.tmp")

            # 写入临时文件
            try:
                with open(temp_file, "w", encoding="utf-8") as f:
                    f.write(config_data)
            except Exception as write_error:
                logger.error("写入临时文件失败: %s", str(write_error))
                if temp_file.exists():
                    try:
                        temp_file.unlink()
                    except Exception:
                        pass
                raise

            # 尝试设置临时文件权限
            try:
                os.chmod(temp_file, stat.S_IRUSR | stat.S_IWUSR)
            except (OSError, AttributeError):
                # 某些系统不支持 chmod，忽略权限设置
                pass

            # 原子操作：重命名临时文件为目标文件
            try:
                # 在 Windows 上，需要先删除目标文件
                if self.config_file.exists():
                    try:
                        self.config_file.unlink()
                    except Exception as unlink_error:
                        logger.warning("删除旧配置文件失败: %s", str(unlink_error))
                        # 如果删除失败，尝试直接重命名（Windows 可能不允许）

                # 重命名临时文件
                temp_file.rename(self.config_file)
            except Exception as rename_error:
                logger.error("重命名文件失败: %s", str(rename_error))
                if temp_file.exists():
                    try:
                        temp_file.unlink()
                    except Exception:
                        pass
                raise

            logger.info("配置保存成功: %s", self.config_file)
            self._notify_observers()
            return True
        except PermissionError as e:
            logger.error("保存配置时权限不足: %s", str(e))
            logger.error("请确保您有足够的权限写入配置目录: %s", self.config_dir)
            logger.error("尝试以管理员身份运行应用程序，或选择一个具有写入权限的配置目录")
            return False
        except (OSError, IOError) as e:
            logger.error("保存配置文件失败: %s", str(e))
            logger.error("请检查配置目录是否存在且可写: %s", self.config_dir)
            return False
        except (TypeError, ValueError) as e:
            logger.error("序列化配置失败: %s", str(e))
            return False
        except Exception as e:
            logger.error("保存配置时发生未知错误: %s", str(e))
            return False

    def get(self) -> Config:
        """获取配置（别名方法）

        Returns:
            Config: 配置对象
        """
        return self.load()

    def register_observer(self, observer):
        """注册观察者

        Args:
            observer: 观察者对象，需实现 on_config_changed 方法
        """
        with self._observer_lock:
            if observer not in self._observers:
                self._observers.append(observer)

    def unregister_observer(self, observer):
        """注销观察者

        Args:
            observer: 要注销的观察者对象
        """
        with self._observer_lock:
            if observer in self._observers:
                self._observers.remove(observer)

    def _notify_observers(self):
        """通知所有观察者配置已更改"""
        with self._observer_lock:
            for observer in list(self._observers):
                try:
                    observer.on_config_changed()
                except Exception as e:
                    logger.error("通知观察者失败: %s", str(e))


__all__ = ["Config", "ConfigManager"]
