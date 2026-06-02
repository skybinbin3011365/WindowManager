# -*- coding: utf-8 -*-
# windowmanager/time_sync.py
"""
时间校准核心模块
实现 NTP 时间同步功能，使用线程池实现并行测试
"""

import logging
import time
import threading
from datetime import datetime, timezone
from typing import Optional, List, Tuple, Callable, Dict
from dataclasses import dataclass
from enum import Enum, auto
from concurrent.futures import ThreadPoolExecutor, as_completed

from constants import NTPConstants, TimeConstants
from utils import is_admin

logger = logging.getLogger(__name__)


class SyncStatus(Enum):
    """时间同步状态枚举"""

    IDLE = auto()
    SYNCING = auto()
    SUCCESS = auto()
    FAILED = auto()
    CANCELLED = auto()


@dataclass
class SyncResult:
    """时间同步结果数据类

    属性:
        success: bool - 是否同步成功
        offset_ms: float - 时间偏移量（毫秒）
        server: str - 使用的 NTP 服务器
        message: str - 状态消息
        timestamp: datetime - 同步时间戳
    """

    success: bool = False
    offset_ms: float = 0.0
    server: str = ""
    message: str = ""
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class TimeSyncTool:
    """时间校准工具类

    提供 NTP 时间同步功能，使用线程池实现并行测试
    """

    NTP_TEST_INTERVAL = 3600  # NTP服务器测试间隔（秒），1小时

    def __init__(
        self,
        ntp_servers: Optional[List[str]] = None,
        max_retries: int = NTPConstants.NTP_MAX_RETRIES,
        enable_log: bool = True,
    ):
        """初始化时间校准工具

        Args:
            ntp_servers: NTP 服务器列表，如果为 None 则使用默认列表
            max_retries: 每个服务器的最大重试次数
            enable_log: 是否启用日志记录
        """
        self.ntp_servers = ntp_servers or NTPConstants.DEFAULT_NTP_SERVERS.copy()
        self.max_retries = max_retries
        self.enable_log = enable_log
        self._status = SyncStatus.IDLE
        self._current_server: Optional[str] = None
        self._progress_callback: Optional[Callable[[str], None]] = None
        self._cancel_flag = False
        self._best_server: Optional[str] = None
        self._last_test_time: float = 0
        self._server_response_times: Dict[str, float] = {}
        self._lock = threading.Lock()

    @property
    def best_server(self) -> Optional[str]:
        """获取当前最佳服务器"""
        return self._best_server

    @property
    def server_response_times(self) -> Dict[str, float]:
        """获取服务器响应时间字典"""
        return self._server_response_times

    @property
    def status(self) -> SyncStatus:
        """获取当前同步状态"""
        return self._status

    @property
    def current_server(self) -> Optional[str]:
        """获取当前正在使用的 NTP 服务器"""
        return self._current_server

    @property
    def last_test_time(self) -> float:
        """获取上次测试时间"""
        return self._last_test_time

    def should_test_all_servers(self) -> bool:
        """判断是否需要测试所有服务器

        Returns:
            bool: 如果距离上次测试超过1小时，返回True
        """
        current_time = time.time()
        with self._lock:
            last_test_time = self._last_test_time
        return (current_time - last_test_time) >= self.NTP_TEST_INTERVAL

    def set_best_server(self, server: str) -> None:
        """设置最佳服务器

        Args:
            server: 最佳服务器地址
        """
        with self._lock:
            self._best_server = server

    def set_last_test_time(self, timestamp: float) -> None:
        """设置上次测试时间

        Args:
            timestamp: 上次测试时间戳
        """
        with self._lock:
            self._last_test_time = timestamp

    def set_server_response_times(self, response_times: Dict[str, float]) -> None:
        """设置服务器响应时间

        Args:
            response_times: 服务器响应时间字典
        """
        with self._lock:
            self._server_response_times = response_times.copy()

    def set_progress_callback(self, callback: Callable[[str], None]):
        """设置进度回调函数

        Args:
            callback: 回调函数，接收进度消息字符串
        """
        self._progress_callback = callback

    def _log_progress(self, message: str):
        """记录进度消息

        Args:
            message: 进度消息
        """
        if self.enable_log:
            logger.info(message)
        if self._progress_callback:
            self._progress_callback(message)

    def cancel(self):
        """取消当前同步操作"""
        self._cancel_flag = True
        self._status = SyncStatus.CANCELLED
        self._log_progress("时间同步已取消")

    def sync_time(self, force_test_all: bool = False) -> Tuple[SyncResult, Dict[str, float]]:
        """时间同步（主入口方法，使用线程池实现）

        Args:
            force_test_all: 是否强制测试所有服务器

        Returns:
            Tuple[SyncResult, Dict[str, float]]: (同步结果, 服务器响应时间字典)
        """
        current_time = time.time()
        should_test_all = force_test_all or self.should_test_all_servers()

        if should_test_all:
            return self._sync_and_test_all_servers(current_time)
        return self._sync_with_best_server()

    def _sync_and_test_all_servers(
        self, current_time: float
    ) -> Tuple[SyncResult, Dict[str, float]]:
        """并行测试所有NTP服务器并同步时间

        Args:
            current_time: 当前时间戳

        Returns:
            Tuple[SyncResult, Dict[str, float]]: (同步结果, 服务器响应时间字典)
        """
        self._status = SyncStatus.SYNCING
        self._cancel_flag = False
        self._log_progress("开始并行测试所有NTP服务器...")

        def test_single_server(server: str) -> Tuple[str, Optional[SyncResult], float]:
            """测试单个服务器，返回(服务器地址, 结果, 响应时间)"""
            if self._cancel_flag:
                return server, None, float("inf")

            for attempt in range(self.max_retries):
                if self._cancel_flag:
                    return server, None, float("inf")

                try:
                    start_time = time.time()
                    result = self._sync_with_server_simple(server, attempt)
                    end_time = time.time()
                    response_time = (end_time - start_time) * 1000

                    if result.success:
                        return server, result, response_time
                    if attempt < self.max_retries - 1:
                        time.sleep(TimeConstants.SHORT_SLEEP_SECONDS)
                except Exception:
                    if attempt < self.max_retries - 1:
                        time.sleep(TimeConstants.SHORT_SLEEP_SECONDS)

            return server, None, float("inf")

        sync_results = []
        server_response_times = {}

        with ThreadPoolExecutor(max_workers=min(len(self.ntp_servers), 5)) as executor:
            future_to_server = {
                executor.submit(test_single_server, server): server for server in self.ntp_servers
            }

            for future in as_completed(future_to_server):
                server = future_to_server[future]
                try:
                    srv, result, response_time = future.result()
                    if result and result.success:
                        sync_results.append(result)
                        server_response_times[srv] = response_time
                        self._log_progress(f"NTP {srv} 响应时间: {response_time:.0f}ms")
                    else:
                        server_response_times[srv] = float("inf")
                except Exception as e:
                    server_response_times[server] = float("inf")
                    logger.warning(f"测试服务器 {server} 时发生异常: {e}")

        with self._lock:
            self._last_test_time = current_time
            self._server_response_times = server_response_times.copy()

        best_result = SyncResult(success=False, message="所有 NTP 服务器均无法连接")

        if sync_results:
            valid_times = {k: v for k, v in server_response_times.items() if v != float("inf")}
            if valid_times:
                best_server = min(valid_times, key=lambda k: valid_times[k])
                best_response_time = valid_times[best_server]

                if best_server != self._best_server:
                    with self._lock:
                        self._best_server = best_server
                    self._log_progress(f"最佳服务器: {best_server} ({best_response_time:.0f}ms)")

                best_result = next(r for r in sync_results if r.server == best_server)

            self._status = SyncStatus.SUCCESS
            self._log_progress(
                f"校准成功: {best_result.server}, 偏移量: {best_result.offset_ms:.2f}ms"
            )
        else:
            self._status = SyncStatus.FAILED
            self._log_progress("所有NTP服务器均无法连接")

        return best_result, server_response_times

    def _sync_with_best_server(self) -> Tuple[SyncResult, Dict[str, float]]:
        """仅与最佳服务器同步时间

        Returns:
            Tuple[SyncResult, Dict[str, float]]: (同步结果, 服务器响应时间字典)
        """
        self._status = SyncStatus.SYNCING
        self._cancel_flag = False

        with self._lock:
            best_server = self._best_server

        if not best_server or best_server not in self.ntp_servers:
            return self._sync_and_test_all_servers(time.time())

        self._log_progress(f"校准中: {best_server}...")

        for attempt in range(self.max_retries):
            if self._cancel_flag:
                return SyncResult(success=False, message="同步已取消", server=best_server), {
                    best_server: float("inf")
                }

            try:
                start_time = time.time()
                result = self._sync_with_server_simple(best_server, attempt)
                end_time = time.time()
                response_time = (end_time - start_time) * 1000

                if result.success:
                    with self._lock:
                        self._server_response_times[best_server] = response_time
                    self._status = SyncStatus.SUCCESS
                    self._log_progress(f"校准成功: {best_server}, 偏移量: {result.offset_ms:.2f}ms")
                    with self._lock:
                        return result, self._server_response_times.copy()
                else:
                    if attempt < self.max_retries - 1:
                        backoff_time = min(0.5 * (2**attempt), 2)
                        time.sleep(backoff_time)
                    else:
                        with self._lock:
                            self._best_server = None
                        self._log_progress(f"最佳服务器 {best_server} 连接失败，开始测试所有服务器")
                        return self._sync_and_test_all_servers(time.time())
            except Exception:
                if attempt < self.max_retries - 1:
                    backoff_time = min(0.5 * (2**attempt), 2)
                    time.sleep(backoff_time)
                else:
                    with self._lock:
                        self._best_server = None
                    self._log_progress("最佳服务器异常，开始测试所有服务器")
                    return self._sync_and_test_all_servers(time.time())

        return (
            SyncResult(success=False, message="同步失败", server=best_server or ""),
            self._server_response_times.copy(),
        )

    def _sync_with_server_simple(self, server: str, attempt: int = 0) -> SyncResult:
        """与指定NTP服务器同步时间（同步版本，在后台线程中运行）

        Args:
            server: NTP服务器地址
            attempt: 当前尝试次数

        Returns:
            SyncResult: 同步结果
        """
        import socket

        try:
            timeout = min(NTPConstants.NTP_TIMEOUT * (2**attempt), 10)
            addr = socket.gethostbyname(server)
        except socket.gaierror:
            return SyncResult(success=False, message="DNS解析失败", server=server)

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)

        try:
            ntp_packet = self._create_ntp_packet()
            send_time = time.time()
            sock.sendto(ntp_packet, (addr, NTPConstants.NTP_PORT))
            data, _ = sock.recvfrom(1024)
            receive_time = time.time()
            response_time = (receive_time - send_time) * 1000

            if not data or len(data) < 48:
                return SyncResult(success=False, message="无效响应", server=server)

            offset, server_timestamp = self._calculate_offset(
                ntp_packet, data, send_time, receive_time
            )

            if server_timestamp < 0 or server_timestamp > time.time() + 86400 * 365:
                return SyncResult(success=False, message="无效时间戳", server=server)

            round_trip_time = response_time
            if round_trip_time > 5000:
                return SyncResult(success=False, message="延迟过高", server=server)

            ntp_datetime = datetime.fromtimestamp(server_timestamp)
            return SyncResult(
                success=True,
                offset_ms=offset,
                server=server,
                message=f"响应时间：{response_time:.0f}ms",
                timestamp=ntp_datetime,
            )
        except socket.timeout:
            return SyncResult(success=False, message="超时", server=server)
        except socket.error:
            return SyncResult(success=False, message="网络错误", server=server)
        except Exception as e:
            logger.debug(
                "NTP同步异常 - 服务器: %s, 异常类型: %s, 详细信息: %s",
                server,
                type(e).__name__,
                str(e),
            )
            return SyncResult(success=False, message=f"异常: {type(e).__name__}", server=server)
        finally:
            try:
                sock.close()
            except Exception:
                pass

    def _create_ntp_packet(self) -> bytes:
        """创建 NTP 数据包

        Returns:
            bytes: NTP 数据包
        """
        ntp_packet = bytearray(48)
        ntp_packet[0] = (0 << 6) | (3 << 3) | 3
        return bytes(ntp_packet)

    def _calculate_offset(
        self,
        _request_packet: bytes,
        response_data: bytes,
        send_time: float,
        receive_time: float,
    ) -> Tuple[float, float]:
        """计算时间偏移量并返回服务器时间戳

        Args:
            request_packet: 发送的 NTP 请求包
            response_data: 接收的 NTP 响应包
            send_time: 发送时间（Unix 时间戳）
            receive_time: 接收时间（Unix 时间戳）

        Returns:
            Tuple[float, float]: (时间偏移量（毫秒）, 服务器发送时间 t3)
        """
        import struct

        def unpack_timestamp(packet_bytes: bytes, offset: int) -> float:
            """从 NTP 包中提取时间戳并转换为 Unix 时间戳"""
            seconds, fraction = struct.unpack("!II", packet_bytes[offset : offset + 8])
            return seconds - NTPConstants.NTP_TIMESTAMP_DELTA + fraction / 2**32

        t1 = send_time
        t4 = receive_time
        t2 = unpack_timestamp(response_data, 32)
        t3 = unpack_timestamp(response_data, 40)
        offset = ((t2 - t1) + (t3 - t4)) / 2
        return offset * 1000, t3

    def sync_time_blocking(self) -> Tuple[SyncResult, Dict[str, float]]:
        """同步时间（阻塞版本，用于非异步环境）

        Returns:
            Tuple[SyncResult, Dict[str, float]]: (同步结果, 服务器响应时间字典)
        """
        return self.sync_time()


class SystemTimeSetter:
    """系统时间设置器

    提供设置系统时间的功能（需要管理员权限）
    """

    @staticmethod
    def is_admin() -> bool:
        """检查当前进程是否具有管理员权限

        Returns:
            bool: 是否具有管理员权限
        """
        return is_admin()

    @staticmethod
    def set_system_time(offset_ms: float, enable_log: bool = True) -> bool:
        """设置系统时间

        Args:
            offset_ms: 时间偏移量（毫秒），正数表示调快，负数表示调慢
            enable_log: 是否启用日志记录

        Returns:
            bool: 是否设置成功
        """
        if abs(offset_ms) < 1:
            if enable_log:
                logger.info("偏移量过小，无需调整")
            return True

        if not SystemTimeSetter.is_admin():
            if enable_log:
                logger.error("设置系统时间需要管理员权限")
            return False

        try:
            import ctypes
            from ctypes import Structure, c_ushort

            class SYSTEMTIME(Structure):
                _fields_ = [
                    ("wYear", c_ushort),
                    ("wMonth", c_ushort),
                    ("wDayOfWeek", c_ushort),
                    ("wDay", c_ushort),
                    ("wHour", c_ushort),
                    ("wMinute", c_ushort),
                    ("wSecond", c_ushort),
                    ("wMilliseconds", c_ushort),
                ]

            now = datetime.now()
            new_time = now.timestamp() * 1000 + offset_ms
            new_datetime = datetime.fromtimestamp(new_time / 1000, tz=timezone.utc)

            st = SYSTEMTIME(
                wYear=new_datetime.year,
                wMonth=new_datetime.month,
                wDayOfWeek=new_datetime.weekday(),
                wDay=new_datetime.day,
                wHour=new_datetime.hour,
                wMinute=new_datetime.minute,
                wSecond=new_datetime.second,
                wMilliseconds=new_datetime.microsecond // 1000,
            )

            ctypes.windll.kernel32.SetSystemTime(ctypes.byref(st))
            if enable_log:
                logger.info("系统时间已调整：%.2fms", offset_ms)
            else:
                if abs(offset_ms) >= 1000:
                    logger.info("系统时间已调整：%.2fms", offset_ms)
            return True

        except PermissionError:
            if enable_log:
                logger.error("设置系统时间需要管理员权限")
            return False
        except Exception as e:
            if enable_log:
                logger.error("设置系统时间失败：%s", str(e))
            return False


def create_time_sync_tool(
    ntp_servers: Optional[List[str]] = None, enable_log: bool = True
) -> TimeSyncTool:
    """创建时间校准工具实例

    Args:
        ntp_servers: NTP 服务器列表
        enable_log: 是否启用日志记录

    Returns:
        TimeSyncTool: 时间校准工具实例
    """
    return TimeSyncTool(ntp_servers, enable_log=enable_log)
