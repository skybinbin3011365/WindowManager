"""
窗口管理器 - 日志工具模块
提供高效的日志处理功能，包括日志缓冲、格式化、和性能优化
"""

import logging
import threading
import queue
import time
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass, field
from enum import Enum


class LogLevel(Enum):
    """日志级别枚举"""
    DEBUG = 1
    INFO = 2
    WARNING = 3
    ERROR = 4
    CRITICAL = 5


@dataclass
class LogEntry:
    """日志条目数据类

    用于存储单条日志的所有信息，包括时间戳、级别、消息、模块名等。
    使用数据类可以提高日志处理的性能和可读性。

    属性:
        timestamp: 日志时间戳
        level: 日志级别
        logger_name: 日志记录器名称
        message: 日志消息
        exception_info: 异常信息（如果有）
    """
    timestamp: datetime
    level: str
    logger_name: str
    message: str
    exception_info: Optional[str] = None


class BufferedLogHandler(logging.Handler):
    """缓冲日志处理器

    缓冲日志消息，定期批量写入，避免频繁的IO操作。
    使用队列进行线程安全的缓冲，适合高并发场景。

    主要特点：
    - 线程安全：使用队列进行缓冲
    - 批量处理：减少IO次数，提高性能
    - 可配置：支持自定义缓冲大小和刷新间隔
    """

    def __init__(self, capacity: int = 100, flush_interval: float = 1.0):
        """初始化缓冲日志处理器

        Args:
            capacity: 缓冲区容量，达到此数量时触发强制刷新
            flush_interval: 刷新间隔（秒），定期将缓冲区的日志写入
        """
        super().__init__()
        self._log_queue: queue.Queue = queue.Queue(maxsize=capacity)
        self._flush_interval = flush_interval
        self._last_flush_time = time.time()
        self._formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    def emit(self, record: logging.LogRecord) -> None:
        """发送日志记录到缓冲区

        当缓冲区满时，会自动将最早的日志条目移除，确保不会阻塞主线程。

        Args:
            record: 日志记录对象
        """
        try:
            # 将日志记录转换为 LogEntry 对象
            log_entry = self._record_to_entry(record)

            # 非阻塞方式放入队列，队列满时丢弃最旧的日志
            try:
                self._log_queue.put_nowait(log_entry)
            except queue.Full:
                # 队列满时，移除最旧的条目，然后放入新条目
                try:
                    self._log_queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self._log_queue.put_nowait(log_entry)
                except queue.Full:
                    pass

            # 检查是否需要强制刷新
            if self._log_queue.qsize() >= 100 or \
               time.time() - self._last_flush_time >= self._flush_interval:
                self.flush()

        except Exception:
            self.handleError(record)

    def flush(self) -> None:
        """刷新缓冲区，将所有缓冲的日志写出

        这个方法应该定期调用，或者在程序退出时调用，
        确保所有缓冲的日志都被写出。
        """
        self._last_flush_time = time.time()
        # 在实际应用中，这里会将日志写入文件或发送到日志服务器
        # 目前只是清空队列，实际写入由其他handler完成
        while not self._log_queue.empty():
            try:
                self._log_queue.get_nowait()
            except queue.Empty:
                break

    def _record_to_entry(self, record: logging.LogRecord) -> LogEntry:
        """将 logging.LogRecord 转换为 LogEntry

        Args:
            record: 日志记录对象

        Returns:
            LogEntry: 日志条目对象
        """
        return LogEntry(
            timestamp=datetime.fromtimestamp(record.created),
            level=self._get_level_name(record.levelno),
            logger_name=record.name,
            message=record.getMessage(),
            exception_info=record.exc_text if record.exc_text else None
        )

    def _get_level_name(self, levelno: int) -> str:
        """将日志级别编号转换为名称

        Args:
            levelno: 日志级别编号

        Returns:
            str: 日志级别名称
        """
        return logging.getLevelName(levelno)

    def get_pending_logs(self) -> List[LogEntry]:
        """获取所有待处理的日志条目

        用于日志查看或分析功能。

        Returns:
            List[LogEntry]: 待处理的日志条目列表
        """
        logs = []
        while not self._log_queue.empty():
            try:
                logs.append(self._log_queue.get_nowait())
            except queue.Empty:
                break
        return logs

    def get_queue_size(self) -> int:
        """获取当前缓冲队列中的日志条目数量

        Returns:
            int: 队列中的日志条目数量
        """
        return self._log_queue.qsize()


class PerformanceLogger:
    """性能日志记录器

    专门用于记录性能相关的事件，如函数执行时间、资源使用情况等。
    使用上下文管理器可以方便地测量代码块的执行时间。

    使用示例：
        logger = PerformanceLogger("my_function")
        with logger.measure():
            # 要测量的代码
            pass
        logger.log_duration()
    """

    def __init__(self, name: str, logger: Optional[logging.Logger] = None):
        """初始化性能日志记录器

        Args:
            name: 性能日志的名称/标识
            logger: 使用的日志记录器，如果为None则使用默认的日志记录器
        """
        self.name = name
        self.logger = logger or logging.getLogger(__name__)
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None
        self._measurements: List[float] = []

    def __enter__(self):
        """上下文管理器入口，开始计时"""
        self._start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口，结束计时"""
        self._end_time = time.perf_counter()
        if self._start_time is not None:
            duration = (self._end_time - self._start_time) * 1000  # 转换为毫秒
            self._measurements.append(duration)
            self.logger.debug(
                "性能测量 [%s]: %.2f ms",
                self.name,
                duration
            )

    def measure(self):
        """返回一个上下文管理器来测量代码块的执行时间

        Returns:
            PerformanceLogger: 返回自身，用于上下文管理器
        """
        return self

    def log_duration(self, message: Optional[str] = None) -> float:
        """记录最后一次测量的持续时间

        Args:
            message: 可选的自定义消息

        Returns:
            float: 持续时间（毫秒）
        """
        if self._start_time is None or self._end_time is None:
            return 0.0

        duration = (self._end_time - self._start_time) * 1000
        if message:
            self.logger.info(
                "性能日志 [%s]: %s - %.2f ms",
                self.name,
                message,
                duration
            )
        else:
            self.logger.info(
                "性能日志 [%s]: %.2f ms",
                self.name,
                duration
            )
        return duration

    def get_average_duration(self) -> float:
        """获取所有测量的平均持续时间

        Returns:
            float: 平均持续时间（毫秒）
        """
        if not self._measurements:
            return 0.0
        return sum(self._measurements) / len(self._measurements)

    def get_max_duration(self) -> float:
        """获取所有测量中的最大持续时间

        Returns:
            float: 最大持续时间（毫秒）
        """
        if not self._measurements:
            return 0.0
        return max(self._measurements)

    def get_min_duration(self) -> float:
        """获取所有测量中的最小持续时间

        Returns:
            float: 最小持续时间（毫秒）
        """
        if not self._measurements:
            return 0.0
        return min(self._measurements)


class StructuredLogger:
    """结构化日志记录器

    提供结构化日志功能，方便日志分析和查询。
    支持键值对形式的日志记录，比纯文本日志更易于解析和分析。

    使用示例：
        logger = StructuredLogger("my_module")
        logger.log_info("用户登录", user_id=123, ip="192.168.1.1")
        logger.log_error("登录失败", user_id=123, error="密码错误")
    """

    def __init__(self, name: str, logger: Optional[logging.Logger] = None):
        """初始化结构化日志记录器

        Args:
            name: 日志记录器的名称
            logger: 使用的日志记录器，如果为None则使用默认的日志记录器
        """
        self.name = name
        self.logger = logger or logging.getLogger(name)

    def _format_message(self, message: str, **kwargs) -> str:
        """格式化结构化日志消息

        Args:
            message: 日志消息
            **kwargs: 额外的键值对参数

        Returns:
            str: 格式化的日志消息
        """
        if not kwargs:
            return message

        # 格式化为 "message {key1: value1, key2: value2, ...}"
        kv_pairs = ", ".join(f"{k}={v!r}" for k, v in kwargs.items())
        return f"{message} {{{kv_pairs}}}"

    def log_debug(self, message: str, **kwargs) -> None:
        """记录 DEBUG 级别的结构化日志

        Args:
            message: 日志消息
            **kwargs: 额外的键值对参数
        """
        formatted_message = self._format_message(message, **kwargs)
        self.logger.debug(formatted_message)

    def log_info(self, message: str, **kwargs) -> None:
        """记录 INFO 级别的结构化日志

        Args:
            message: 日志消息
            **kwargs: 额外的键值对参数
        """
        formatted_message = self._format_message(message, **kwargs)
        self.logger.info(formatted_message)

    def log_warning(self, message: str, **kwargs) -> None:
        """记录 WARNING 级别的结构化日志

        Args:
            message: 日志消息
            **kwargs: 额外的键值对参数
        """
        formatted_message = self._format_message(message, **kwargs)
        self.logger.warning(formatted_message)

    def log_error(self, message: str, **kwargs) -> None:
        """记录 ERROR 级别的结构化日志

        Args:
            message: 日志消息
            **kwargs: 额外的键值对参数
        """
        formatted_message = self._format_message(message, **kwargs)
        self.logger.error(formatted_message)

    def log_critical(self, message: str, **kwargs) -> None:
        """记录 CRITICAL 级别的结构化日志

        Args:
            message: 日志消息
            **kwargs: 额外的键值对参数
        """
        formatted_message = self._format_message(message, **kwargs)
        self.logger.critical(formatted_message)


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    enable_console: bool = True,
    enable_buffered_handler: bool = False
) -> logging.Logger:
    """设置日志系统

    统一配置日志系统，支持控制台输出、文件输出和缓冲处理。

    Args:
        level: 日志级别，可选值：DEBUG, INFO, WARNING, ERROR, CRITICAL
        log_file: 日志文件路径，如果为None则不写入文件
        enable_console: 是否启用控制台输出
        enable_buffered_handler: 是否启用缓冲处理器

    Returns:
        logging.Logger: 配置好的根日志记录器
    """
    # 获取根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 清除现有的处理器
    root_logger.handlers.clear()

    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 添加控制台处理器
    if enable_console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # 添加文件处理器
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # 添加缓冲处理器
    if enable_buffered_handler:
        buffered_handler = BufferedLogHandler()
        root_logger.addHandler(buffered_handler)

    return root_logger


# 导出常用的日志工具类和函数
__all__ = [
    'LogLevel',
    'LogEntry',
    'BufferedLogHandler',
    'PerformanceLogger',
    'StructuredLogger',
    'setup_logging'
]
