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
from dataclasses import dataclass, field, asdict
from typing import List, Optional

import logging
logger = logging.getLogger(__name__)


@dataclass
class Config:
    """配置数据类

    包含所有应用程序配置项，提供默认值和类型提示
    """
    # 版本信息
    version: str = "2.0.0"

    # 热键配置
    hide_hotkey: str = "Middle+Right"
    show_hotkey: str = "Shift+Right"

    # 日志配置
    log_level: str = "INFO"
    log_window_operations: bool = True  # 隐藏/显示窗口操作是否记录日志
    log_time_calibration: bool = True  # 时间校准、检测是否记录日志

    # 自动启动配置
    auto_start: bool = False
    auto_refresh_interval: float = 5.0

    # 窗口管理配置
    keywords: List[str] = field(default_factory=list)
    process_whitelist: List[str] = field(default_factory=list)
    selected_windows: List[int] = field(default_factory=list)

    # 时间同步配置
    ntp_auto_calibrate: bool = False
    ntp_check_interval: int = 3600  # 秒
    ntp_error_threshold: int = 5  # 秒
    ntp_servers: List[str] = field(default_factory=lambda: [
        "ntp.aliyun.com",
        "ntp.tencent.com",
        "time.windows.com",
        "cn.ntp.org.cn"
    ])

    # UI配置
    ui: dict = field(default_factory=lambda: {
        "width": 1000,
        "height": 700,
        "theme": "light"
    })


class ConfigManager:
    """统一的配置管理器

    负责配置文件的读取、写入、版本管理和延迟保存
    """
    # 延迟保存的时间间隔（秒）
    SAVE_DELAY = 2.0

    def __init__(self, config_dir: Optional[str] = None):
        """初始化配置管理器

        Args:
            config_dir: 配置目录路径，如果为None则使用默认目录
        """
        if config_dir is None:
            config_dir = pathlib.Path.home() / ".window_manager"

        self.config_dir = pathlib.Path(config_dir)
        self.config_file = self.config_dir / "config.json"
        self._config: Optional[Config] = None

        # 延迟保存相关
        self._dirty = False
        self._save_timer: Optional[threading.Timer] = None
        self._save_lock = threading.Lock()

        self._ensure_config_dir()

    def _ensure_config_dir(self):
        """确保配置目录存在"""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            # 设置目录权限为仅所有者可访问
            try:
                os.chmod(self.config_dir, stat.S_IRWXU)
            except (OSError, AttributeError):
                pass

            logs_dir = self.config_dir / "logs"
            logs_dir.mkdir(exist_ok=True)
        except Exception as e:
            logger.error("Failed to ensure config directory: %s", str(e))

    def load(self) -> Config:
        """加载配置

        Returns:
            Config: 配置对象
        """
        if self._config is None:
            self._config = Config()

            if self.config_file.exists():
                try:
                    with open(self.config_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    # 安全地合并配置，确保所有字段都有值
                    config_dict = asdict(self._config)
                    config_dict.update(data)

                    self._config = Config(**config_dict)
                    logger.info("Config loaded from %s", self.config_file)
                except json.JSONDecodeError as e:
                    logger.warning("Failed to parse config file, using defaults: %s", str(e))
                    self._backup_corrupted_config()
                except PermissionError as e:
                    logger.warning("Permission denied when reading config: %s", str(e))
                except (OSError, IOError) as e:
                    logger.warning("Failed to load config file, using defaults: %s", str(e))
                except TypeError as e:
                    logger.warning("Invalid config type, using defaults: %s", str(e))
                except Exception as e:
                    logger.warning("Unexpected error loading config, using defaults: %s", str(e))

        return self._config

    def _backup_corrupted_config(self):
        """备份损坏的配置文件"""
        if self.config_file.exists():
            try:
                backup_file = self.config_file.with_suffix('.json.bak')
                shutil.copy(self.config_file, backup_file)
                logger.info("Damaged config backed up to %s", backup_file)
            except (OSError, IOError) as e:
                logger.error("Failed to backup config file: %s", str(e))

    def save(self, config: Config, immediate: bool = True) -> bool:
        """保存配置

        Args:
            config: 配置对象
            immediate: 是否立即保存，默认为True

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
        with self._save_lock:
            if self._dirty:
                self._dirty = False
                self._save_timer = None

        if not self._dirty:
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

    def _do_save(self) -> bool:
        """执行实际的保存操作

        Returns:
            bool: 是否保存成功
        """
        if self._config is None:
            return False

        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(self._config), f, ensure_ascii=False, indent=4)

            # 设置配置文件权限为仅所有者可读写
            try:
                os.chmod(self.config_file, stat.S_IRUSR | stat.S_IWUSR)
            except (OSError, AttributeError):
                pass

            logger.info("Config saved successfully: %s", self.config_file)
            return True
        except PermissionError as e:
            logger.error("Permission denied when saving config: %s", str(e))
            return False
        except (OSError, IOError) as e:
            logger.error("Failed to save config file: %s", str(e))
            return False
        except (TypeError, ValueError) as e:
            logger.error("Failed to serialize config: %s", str(e))
            return False
        except Exception as e:
            logger.error("Unexpected error saving config: %s", str(e))
            return False

    def get(self) -> Config:
        """获取配置（别名方法）

        Returns:
            Config: 配置对象
        """
        return self.load()


__all__ = ['Config', 'ConfigManager']
