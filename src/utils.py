
# windowmanager/utils.py
"""
工具模块 - 日志设置和辅助函数
"""
import logging
import logging.handlers
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
    """设置日志系统（优化版，避免IO阻塞）

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

    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    # 添加控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level_value)
    console_handler.setFormatter(formatter)
    logging.root.addHandler(console_handler)

    # 添加文件处理器 - 使用轮转日志避免文件过大
    try:
        log_file_path = logs_dir / LOG_FILE_NAME
        # 使用RotatingFileHandler，限制文件大小为10MB，保留3个备份
        file_handler = logging.handlers.RotatingFileHandler(
            log_file_path, 
            encoding='utf-8',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=3,
            delay=True  # 延迟打开文件，避免启动时阻塞
        )
        file_handler.setLevel(log_level_value)
        file_handler.setFormatter(formatter)
        logging.root.addHandler(file_handler)
        logging.info("日志文件已设置: %s", log_file_path)
    except Exception as e:
        logging.warning("无法创建文件日志处理器: %s", str(e))

    return logs_dir
