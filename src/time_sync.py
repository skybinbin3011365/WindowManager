# windowmanager/time_sync.py
"""
时间同步模块
负责处理NTP服务器时间同步相关的功能
"""
import socket
import struct
import time
import datetime
import ctypes
import logging
import threading

logger = logging.getLogger(__name__)

# Windows系统时间结构体
class SYSTEMTIME(ctypes.Structure):
    _fields_ = [
        ("wYear", ctypes.c_ushort),
        ("wMonth", ctypes.c_ushort),
        ("wDayOfWeek", ctypes.c_ushort),
        ("wDay", ctypes.c_ushort),
        ("wHour", ctypes.c_ushort),
        ("wMinute", ctypes.c_ushort),
        ("wSecond", ctypes.c_ushort),
        ("wMilliseconds", ctypes.c_ushort)
    ]


def is_admin():
    """检查当前进程是否具有管理员权限"""
    try:
        import ctypes.wintypes
        OpenProcessToken = ctypes.windll.advapi32.OpenProcessToken
        GetTokenInformation = ctypes.windll.advapi32.GetTokenInformation
        CloseHandle = ctypes.windll.kernel32.CloseHandle
        GetCurrentProcess = ctypes.windll.kernel32.GetCurrentProcess
        
        TOKEN_QUERY = 0x0008
        TokenElevation = 20
        
        hToken = ctypes.wintypes.HANDLE()
        if not OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, ctypes.byref(hToken)):
            return False
        
        try:
            elevation = ctypes.c_int()
            size = ctypes.wintypes.DWORD()
            if GetTokenInformation(hToken, TokenElevation, ctypes.byref(elevation),
                                   ctypes.sizeof(elevation), ctypes.byref(size)):
                return elevation.value != 0
            return False
        finally:
            CloseHandle(hToken)
    except Exception as e:
        logger.warning("检查管理员权限时出错: %s", str(e))
        return False


def request_admin_restart():
    """请求以管理员权限重新启动程序"""
    try:
        import sys
        import os
        ShellExecuteW = ctypes.windll.shell32.ShellExecuteW
        
        if getattr(sys, "frozen", False):
            script_path = sys.executable
        else:
            script_path = os.path.abspath(sys.argv[0])
        
        result = ShellExecuteW(
            None,
            "runas",
            script_path,
            " ".join(sys.argv[1:]),
            None,
            1
        )
        return result > 32
    except Exception as e:
        logger.error("请求管理员权限重启时出错: %s", str(e))
        return False


class TimeSync:
    """时间同步类"""

    def __init__(self):
        # 使用国内优质NTP服务器
        self.default_ntp_servers = [
            "ntp1.aliyun.com",
            "ntp2.aliyun.com",
            "ntp3.aliyun.com",
            "ntp1.ntsc.ac.cn",
            "ntp1.tencent.com"
        ]
        self._lock = threading.RLock()
        self._is_calibrating = False
        self._last_calibration_time = 0
        self._min_calibration_interval = 5

    def _query_ntp_server(self, server, timeout=2):
        """查询NTP服务器获取时间数据（修复WinError 10022）"""
        sock = None
        try:
            # 创建UDP socket，显式指定协议
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.settimeout(timeout)
            
            # 发送NTP请求
            ntp_request = b'\x1b' + 47 * b'\x00'
            sock.sendto(ntp_request, (server, 123))
            
            # 接收响应
            data, addr = sock.recvfrom(48)
            return True, data
            
        except socket.timeout:
            return False, "连接超时"
        except socket.gaierror:
            return False, "无法解析服务器地址"
        except socket.error as e:
            return False, "Socket错误: {}".format(str(e))
        except Exception as e:
            return False, "未知错误: {}".format(str(e))
        finally:
            if sock is not None:
                try:
                    sock.close()
                except Exception:
                    pass

    def test_ntp_servers(self, servers=None):
        """测试NTP服务器连接"""
        with self._lock:
            if servers is None:
                servers = self.default_ntp_servers

            results = []

            for server in servers:
                start_time = time.time()
                success, data = self._query_ntp_server(server, timeout=2)
                end_time = time.time()

                if success:
                    response_time = (end_time - start_time) * 1000
                    results.append((server, response_time))
                    logger.info("NTP服务器 %s 测试成功，响应时间: %.2fms", server, response_time)
                else:
                    logger.warning("NTP服务器 %s 测试失败: %s", server, data)

                time.sleep(0.1)

            results.sort(key=lambda x: x[1])
            logger.info("NTP服务器测试完成，成功 %s 个，失败 %s 个", len(results), len(servers) - len(results))
            return results[:3]

    def _parse_ntp_response(self, data, local_time):
        """解析NTP服务器响应数据"""
        try:
            transmit_timestamp = data[40:48]
            timestamp_seconds = struct.unpack('!I', transmit_timestamp[:4])[0]
            ntp_time_utc = timestamp_seconds - 2208988800
            time_diff = abs(ntp_time_utc - local_time)
            ntp_datetime_local = datetime.datetime.fromtimestamp(ntp_time_utc)
            ntp_datetime_utc = datetime.datetime.utcfromtimestamp(ntp_time_utc)
            ntp_time_str = ntp_datetime_local.strftime("%Y-%m-%d %H:%M:%S")

            return {
                "success": True,
                "ntp_time_utc": ntp_time_utc,
                "time_diff": time_diff,
                "ntp_time_str": ntp_time_str,
                "ntp_datetime_utc": ntp_datetime_utc,
                "error": None
            }
        except struct.error as e:
            return {
                "success": False,
                "ntp_time_utc": None,
                "time_diff": 0,
                "ntp_time_str": "",
                "ntp_datetime_utc": None,
                "error": "数据解析错误: {}".format(str(e))
            }

    def get_ntp_time(self, servers=None, max_retries=3):
        """获取NTP服务器时间，支持重试机制"""
        with self._lock:
            if servers is None:
                servers = self.default_ntp_servers

            local_time = time.time()
            last_error = None

            for server in servers:
                for attempt in range(max_retries):
                    success, data = self._query_ntp_server(server, timeout=2)

                    if success and len(data) == 48:
                        parsed = self._parse_ntp_response(data, local_time)
                        if parsed["success"]:
                            logger.info("Successfully got time from %s (attempt %d)", server, attempt + 1)
                            return {
                                "success": True,
                                "timestamp": parsed["ntp_time_utc"],
                                "server": server,
                                "time_diff": parsed["time_diff"],
                                "ntp_time_str": parsed["ntp_time_str"]
                            }
                        else:
                            last_error = parsed["error"]
                            logger.warning("NTP服务器 %s 时间获取失败: %s (attempt %d)",
                                       server, last_error, attempt + 1)
                            if attempt < max_retries - 1:
                                time.sleep(0.5)
                            continue
                    else:
                        last_error = data
                        logger.warning("NTP服务器 %s 时间获取失败: %s (attempt %d)",
                                   server, last_error, attempt + 1)
                        if attempt < max_retries - 1:
                            time.sleep(0.5)
                        continue

            logger.error("无法获取NTP服务器时间，最后错误: %s", last_error)
            return {
                "success": False,
                "timestamp": None,
                "server": "",
                "time_diff": 0,
                "ntp_time_str": "无法获取NTP时间",
                "error": last_error
            }

    def calibrate_time(self, servers=None, error_threshold=5, skip_interval_check=False):
        """校准系统时间
        
        Args:
            servers: NTP服务器列表
            error_threshold: 误差阈值
            skip_interval_check: 是否跳过最小间隔检查（用于时间差超阈值时的立即校准）
        """
        with self._lock:
            if self._is_calibrating:
                logger.info("时间校准正在进行中，跳过本次校准")
                return {
                    "success": False,
                    "server": "",
                    "ntp_time": "",
                    "local_time": "",
                    "time_diff": 0,
                    "message": "时间校准正在进行中"
                }

            current_time = time.time()
            if not skip_interval_check and current_time - self._last_calibration_time < self._min_calibration_interval:
                logger.info("距离上次校准时间不足 %s 秒，跳过本次校准", self._min_calibration_interval)
                return {
                    "success": False,
                    "server": "",
                    "ntp_time": "",
                    "local_time": "",
                    "time_diff": 0,
                    "message": "距离上次校准时间不足 {} 秒".format(self._min_calibration_interval)
                }

            self._is_calibrating = True

        try:
            if servers is None:
                servers = self.default_ntp_servers

            local_time = time.time()
            local_datetime = datetime.datetime.fromtimestamp(local_time)
            local_time_str = local_datetime.strftime("%Y-%m-%d %H:%M:%S")

            for server in servers:
                success, data = self._query_ntp_server(server, timeout=3)

                if success and len(data) == 48:
                    parsed = self._parse_ntp_response(data, local_time)
                    if parsed["success"]:
                        ntp_datetime_utc = parsed["ntp_datetime_utc"]
                        ntp_time_str = parsed["ntp_time_str"]
                        time_diff = parsed["time_diff"]

                        if time_diff > error_threshold:
                            try:
                                year, month, day, hour, minute, second = ntp_datetime_utc.year, ntp_datetime_utc.month, ntp_datetime_utc.day, ntp_datetime_utc.hour, ntp_datetime_utc.minute, int(ntp_datetime_utc.second)

                                st = SYSTEMTIME()
                                st.wYear = year
                                st.wMonth = month
                                st.wDay = day
                                st.wHour = hour
                                st.wMinute = minute
                                st.wSecond = second
                                st.wMilliseconds = 0
                                st.wDayOfWeek = ntp_datetime_utc.weekday()

                                success = ctypes.windll.kernel32.SetSystemTime(ctypes.byref(st))
                                if success:
                                    with self._lock:
                                        self._last_calibration_time = time.time()
                                    return {
                                        "success": True,
                                        "server": server,
                                        "ntp_time": ntp_time_str,
                                        "local_time": local_time_str,
                                        "time_diff": time_diff,
                                        "message": "时间校准成功！服务器: %s，时间差: %.2f秒" % (server, time_diff)
                                    }
                                else:
                                    # 只有实际设置失败时才提示需要管理员权限
                                    return {
                                        "success": False,
                                        "server": server,
                                        "ntp_time": ntp_time_str,
                                        "local_time": local_time_str,
                                        "time_diff": time_diff,
                                        "message": "时间校准失败：需要管理员权限，请以管理员身份运行程序"
                                    }
                            except (ctypes.ArgumentError, ctypes.ArgumentTypeError) as e:
                                return {
                                    "success": False,
                                    "server": server,
                                    "ntp_time": ntp_time_str,
                                    "local_time": local_time_str,
                                    "time_diff": time_diff,
                                    "message": "时间校准失败：参数错误: %s" % str(e)
                                }
                            except OSError as e:
                                return {
                                    "success": False,
                                    "server": server,
                                    "ntp_time": ntp_time_str,
                                    "local_time": local_time_str,
                                    "time_diff": time_diff,
                                    "message": "时间校准失败：系统错误: %s" % str(e)
                                }
                        else:
                            with self._lock:
                                self._last_calibration_time = time.time()
                            return {
                                "success": False,
                                "server": server,
                                "ntp_time": ntp_time_str,
                                "local_time": local_time_str,
                                "time_diff": time_diff,
                                "message": "时间正常，无需校准。服务器: %s，时间差: %.2f秒" % (server, time_diff)
                            }
                    else:
                        logger.warning("NTP服务器 %s 校准失败: %s", server, parsed["error"])
                        continue
                else:
                    logger.warning("NTP服务器 %s 校准失败: %s", server, data)
                    continue

            logger.error("所有NTP服务器校准失败")
            return {
                "success": False,
                "server": "",
                "ntp_time": "",
                "local_time": local_time_str,
                "time_diff": 0,
                "message": "所有NTP服务器校准失败"
            }
        finally:
            with self._lock:
                self._is_calibrating = False
