
# windowmanager/utils.py
"""
工具模块 - 日志设置和辅助函数
"""
import logging
import os
import pathlib
import tempfile
from typing import Optional

from .constants import LOG_DIR_NAME, LOG_FILE_NAME, LOG_FORMAT, LOG_DATE_FORMAT, CONFIG_DIR_NAME


class NullHandler(logging.Handler):
    """空日志处理器，完全避免任何日志输出"""
    def emit(self, record):
        pass


def setup_logging(config_dir: Optional[str] = None, log_level: str = "INFO"):
    """设置日志系统

    Args:
        config_dir: 配置目录
        log_level: 日志级别
    """
    if config_dir is None:
        config_dir = pathlib.Path.home() / CONFIG_DIR_NAME

    config_dir = pathlib.Path(config_dir)
    logs_dir = config_dir / LOG_DIR_NAME
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
    except (OSError, IOError):
        logs_dir = pathlib.Path(tempfile.gettempdir()) / "window_manager_logs"
        try:
            logs_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    logging.root.handlers = []
    logging.root.propagate = True
    
    # 设置日志级别
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    log_level_value = level_map.get(log_level, logging.INFO)
    logging.root.setLevel(log_level_value)

    # 添加控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level_value)
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
    console_handler.setFormatter(formatter)
    logging.root.addHandler(console_handler)

    return logs_dir
