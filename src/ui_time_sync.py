# windowmanager/ui_time_sync.py
"""
窗口管理器 - 时间校准界面模块
包含时间校准相关的UI组件
"""
import logging
from typing import Optional

try:
    import tkinter as tk
    from tkinter import ttk
    from tkinter import messagebox
    TK_AVAILABLE = True
except ImportError:
    TK_AVAILABLE = False
    tk = ttk = messagebox = None

from . import time_sync
TimeSync = time_sync.TimeSync

logger = logging.getLogger(__name__)


class TimeSyncTab:
    """时间校准选项卡类"""

    def __init__(self, root, config_manager=None, config=None):
        """初始化时间校准选项卡

        Args:
            root: Tkinter根窗口
            config_manager: 配置管理器实例
            config: 配置对象
        """
        if not TK_AVAILABLE:
            raise RuntimeError("Tkinter is required")

        self.root = root
        self.config_manager = config_manager
        self.config = config

        # 初始化时间同步对象
        self.time_sync = TimeSync()

        # UI变量
        self.ntp_auto_var = None
        self.ntp_interval_var = None
        self.ntp_threshold_var = None
        self.ntp_status_var = None
        self.local_time_var = None
        self.ntp_server_time_var = None
        self.ntp_server_var = None
        self.time_diff_var = None
        self.ntp_countdown_var = None
        self.server_test_text = None

        # 软件内部的时间状态
        self._software_ntp_time = 0  # 软件内部保存的NTP时间（从网络获取）
        self._software_local_time = 0  # 软件内部模拟的本地时间
        self._last_ntp_update_time = 0  # 上次NTP网络更新时间
        self._ntp_update_interval = 60  # NTP网络更新间隔，单位秒
        self._is_ntp_initialized = False  # NTP时间是否已初始化

        # 定时更新相关
        self._time_update_timer = None
        self._time_update_interval = 1000  # 1秒更新一次UI显示

        # 倒计时相关
        self._countdown_timer = None
        self._current_countdown = 0
        self._auto_calibrate_timer = None

        # 防止校准过于频繁的标志
        self._is_calibrating = False

    def build_time_sync_tab(self, parent):
        """构建时间校准选项卡

        Args:
            parent: 父容器
        """
        # 创建左右分割布局
        left_frame = ttk.Frame(parent, width=500)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        right_frame = ttk.Frame(parent, width=400)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 时间校准设置
        ntp_frame = ttk.LabelFrame(left_frame, text="时间校准设置")
        ntp_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 自动校准开关
        ntp_auto_frame = ttk.Frame(ntp_frame)
        ntp_auto_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(ntp_auto_frame, text="自动时间校准:").pack(side=tk.LEFT, padx=5)
        self.ntp_auto_var = tk.BooleanVar(value=True)
        self.ntp_auto_var.trace_add('write', self._on_auto_calibrate_changed)
        ntp_auto_checkbox = ttk.Checkbutton(ntp_auto_frame, variable=self.ntp_auto_var, text="")
        try:
            ntp_auto_checkbox.pack(side=tk.LEFT, padx=5, ipady=5)
        except Exception:
            ntp_auto_checkbox.pack(side=tk.LEFT, padx=5)

        # 检查间隔（仅用于倒计时显示）
        ntp_interval_frame = ttk.Frame(ntp_frame)
        ntp_interval_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(ntp_interval_frame, text="检查间隔 (秒):").pack(side=tk.LEFT, padx=5)
        self.ntp_interval_var = tk.StringVar(value="60")
        self.ntp_interval_var.trace_add('write', self._on_interval_changed)
        ttk.Entry(ntp_interval_frame, textvariable=self.ntp_interval_var, width=10).pack(side=tk.LEFT, padx=5)
        self.ntp_countdown_var = tk.StringVar(value="(60秒)")
        ttk.Label(ntp_interval_frame, textvariable=self.ntp_countdown_var).pack(side=tk.LEFT, padx=5)

        # 误差阈值
        ntp_threshold_frame = ttk.Frame(ntp_frame)
        ntp_threshold_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(ntp_threshold_frame, text="误差阈值 (秒):").pack(side=tk.LEFT, padx=5)
        ntp_error_threshold = 5
        if self.config and hasattr(self.config, 'ntp_error_threshold'):
            ntp_error_threshold = self.config.ntp_error_threshold
        self.ntp_threshold_var = tk.StringVar(value=str(ntp_error_threshold))
        ttk.Entry(ntp_threshold_frame, textvariable=self.ntp_threshold_var, width=10).pack(side=tk.LEFT, padx=5)

        # NTP服务器测试
        ntp_test_frame = ttk.Frame(ntp_frame)
        ntp_test_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(ntp_test_frame, text="测试NTP服务器", command=self._test_ntp_servers).pack(side=tk.LEFT, padx=5)
        self.ntp_status_var = tk.StringVar(value="就绪")
        ttk.Label(ntp_test_frame, textvariable=self.ntp_status_var).pack(side=tk.LEFT, padx=10)

        # 创建时间显示和服务器测试的左右布局
        time_display_frame = ttk.Frame(ntp_frame)
        time_display_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 左侧：时间显示
        left_time_frame = ttk.Frame(time_display_frame)
        left_time_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        # 第一行：本地时间
        local_time_frame = ttk.Frame(left_time_frame)
        local_time_frame.pack(fill=tk.X, padx=5, pady=2)
        self.local_time_var = tk.StringVar(value="")
        ttk.Label(local_time_frame, text="本地时间:").pack(side=tk.LEFT, padx=5)
        ttk.Label(local_time_frame, textvariable=self.local_time_var, width=30).pack(side=tk.LEFT, padx=5)

        # 第二行：NTP时间
        ntp_time_frame = ttk.Frame(left_time_frame)
        ntp_time_frame.pack(fill=tk.X, padx=5, pady=2)
        self.ntp_server_time_var = tk.StringVar(value="")
        ttk.Label(ntp_time_frame, text="NTP时间:").pack(side=tk.LEFT, padx=5)
        ttk.Label(ntp_time_frame, textvariable=self.ntp_server_time_var, width=30).pack(side=tk.LEFT, padx=5)

        # 第三行：NTP服务器
        ntp_server_frame = ttk.Frame(left_time_frame)
        ntp_server_frame.pack(fill=tk.X, padx=5, pady=2)
        self.ntp_server_var = tk.StringVar(value="")
        ttk.Label(ntp_server_frame, text="NTP服务器:").pack(side=tk.LEFT, padx=5)
        ttk.Label(ntp_server_frame, textvariable=self.ntp_server_var, width=30).pack(side=tk.LEFT, padx=5)

        # 第四行：时间差
        time_diff_frame = ttk.Frame(left_time_frame)
        time_diff_frame.pack(fill=tk.X, padx=5, pady=2)
        self.time_diff_var = tk.StringVar(value="")
        ttk.Label(time_diff_frame, text="时间差:").pack(side=tk.LEFT, padx=5)
        ttk.Label(time_diff_frame, textvariable=self.time_diff_var, width=15).pack(side=tk.LEFT, padx=5)

        # 第五行：更新时间按钮
        update_button_frame = ttk.Frame(left_time_frame)
        update_button_frame.pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(update_button_frame, text="立即更新NTP", command=self._force_update_ntp).pack(side=tk.LEFT, padx=5)

        # 右侧：服务器测试结果
        right_server_frame = ttk.Frame(time_display_frame, width=300)
        right_server_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5)

        server_test_label = ttk.Label(right_server_frame, text="服务器测试结果", font=('Arial', 10, 'bold'))
        server_test_label.pack(anchor=tk.NW, padx=5, pady=5)

        # 服务器测试结果显示
        self.server_test_text = tk.Text(right_server_frame, height=8, width=40, wrap=tk.WORD)
        self.server_test_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 手动校准
        ntp_calibrate_frame = ttk.Frame(ntp_frame)
        ntp_calibrate_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(ntp_calibrate_frame, text="手动校准时间", command=self._calibrate_time).pack(side=tk.LEFT, padx=5)

        # 延迟初始化，避免选项卡切换时阻塞UI
        def delayed_init():
            logger.info("开始延迟初始化时间校准选项卡（简化版本）")
            # 只初始化本地时间，不自动连接NTP服务器
            import time
            import datetime
            real_local_time = time.time()
            self._software_local_time = real_local_time
            self._software_ntp_time = real_local_time  # 初始时使用本地时间作为NTP时间
            self._last_ntp_update_time = real_local_time
            self._is_ntp_initialized = True  # 标记为已初始化，避免等待
            logger.info("时间校准选项卡初始化完成（使用本地时间）")
            # 启动定时更新
            self._start_time_update()
            # 初始化倒计时
            self._reset_countdown()
        
        self.root.after(500, delayed_init)

    def _initialize_times(self):
        """初始化软件内部时间"""
        import time
        import datetime
        
        # 获取真实本地时间
        real_local_time = time.time()
        self._software_local_time = real_local_time
        
        # 获取NTP时间（后台线程）
        def fetch_ntp():
            try:
                ntp_result = self.time_sync.get_ntp_time()
                if ntp_result and isinstance(ntp_result, dict) and ntp_result.get('success'):
                    self._software_ntp_time = ntp_result.get('timestamp', 0)
                    self._last_ntp_update_time = time.time()
                    self._is_ntp_initialized = True
                    logger.info("NTP时间初始化成功: %.2f", self._software_ntp_time)
                    
                    def update_ui():
                        self.ntp_server_var.set(ntp_result.get('server', ''))
                    self.root.after(0, update_ui)
            except Exception as e:
                logger.error("初始化NTP时间失败: %s", str(e))
        
        import threading
        threading.Thread(target=fetch_ntp, daemon=True).start()

    def _start_time_update(self):
        """启动时间定时更新"""
        if self._time_update_timer:
            self.root.after_cancel(self._time_update_timer)
        
        def schedule_next_update():
            """调度下一次更新"""
            self._time_update_timer = self.root.after(
                self._time_update_interval,
                self._update_and_reschedule
            )
        
        # 延迟第一次更新
        self.root.after(500, schedule_next_update)

    def _update_and_reschedule(self):
        """更新时间并重新调度"""
        self._update_time_display()
        
        if self._time_update_timer:
            self._time_update_timer = self.root.after(
                self._time_update_interval,
                self._update_and_reschedule
            )

    def _stop_time_update(self):
        """停止时间定时更新"""
        if self._time_update_timer:
            self.root.after_cancel(self._time_update_timer)
            self._time_update_timer = None

    def _update_time_display(self):
        """更新时间显示 - 本地时间每秒+1，NTP每分钟从网络更新"""
        try:
            import time
            import datetime
            
            # 检查UI变量
            if not all([self.local_time_var, self.ntp_server_time_var,
                      self.ntp_server_var, self.time_diff_var]):
                return

            # 软件内部本地时间每秒+1
            self._software_local_time += 1
            
            # 更新本地时间显示
            local_datetime = datetime.datetime.fromtimestamp(self._software_local_time)
            local_time_str = local_datetime.strftime("%Y-%m-%d %H:%M:%S")
            self.local_time_var.set(local_time_str)

            # 检查是否需要更新NTP时间（每分钟一次）
            current_real_time = time.time()
            if (self._is_ntp_initialized and 
                current_real_time - self._last_ntp_update_time >= self._ntp_update_interval):
                self._update_ntp_from_network()

            # 如果NTP时间已初始化，显示NTP时间和时间差
            if self._is_ntp_initialized:
                # NTP时间也每秒+1
                self._software_ntp_time += 1
                
                # 显示NTP时间
                ntp_datetime = datetime.datetime.fromtimestamp(self._software_ntp_time)
                ntp_time_str = ntp_datetime.strftime("%Y-%m-%d %H:%M:%S")
                self.ntp_server_time_var.set(ntp_time_str)
                
                # 计算并显示时间差
                time_diff = abs(self._software_ntp_time - self._software_local_time)
                self.time_diff_var.set(f"{time_diff:.2f}秒")
                
                # 检查时间差是否超过阈值
                if self.ntp_auto_var and self.ntp_auto_var.get():
                    self._check_and_calibrate_if_needed(time_diff)
            else:
                self.ntp_server_time_var.set("初始化中...")
                self.time_diff_var.set("")
                
        except Exception as e:
            logger.error("更新时间显示出错: %s", str(e), exc_info=True)

    def _update_ntp_from_network(self):
        """从网络更新NTP时间"""
        import time
        
        def fetch_ntp():
            try:
                logger.debug("从网络更新NTP时间")
                ntp_result = self.time_sync.get_ntp_time()
                if ntp_result and isinstance(ntp_result, dict) and ntp_result.get('success'):
                    new_ntp_time = ntp_result.get('timestamp', 0)
                    if new_ntp_time > 0:
                        self._software_ntp_time = new_ntp_time
                        self._last_ntp_update_time = time.time()
                        logger.info("NTP时间从网络更新成功: %.2f", self._software_ntp_time)
                        
                        def update_ui():
                            self.ntp_server_var.set(ntp_result.get('server', ''))
                        self.root.after(0, update_ui)
            except Exception as e:
                logger.error("从网络更新NTP时间失败: %s", str(e))
        
        import threading
        threading.Thread(target=fetch_ntp, daemon=True).start()

    def _force_update_ntp(self):
        """强制立即更新NTP时间"""
        import time
        
        def fetch_ntp():
            try:
                logger.info("强制更新NTP时间")
                ntp_result = self.time_sync.get_ntp_time()
                if ntp_result and isinstance(ntp_result, dict) and ntp_result.get('success'):
                    new_ntp_time = ntp_result.get('timestamp', 0)
                    if new_ntp_time > 0:
                        self._software_ntp_time = new_ntp_time
                        self._last_ntp_update_time = time.time()
                        self._is_ntp_initialized = True
                        logger.info("NTP时间强制更新成功: %.2f", self._software_ntp_time)
                        
                        def update_ui():
                            self.ntp_server_var.set(ntp_result.get('server', ''))
                        self.root.after(0, update_ui)
            except Exception as e:
                logger.error("强制更新NTP时间失败: %s", str(e))
        
        import threading
        threading.Thread(target=fetch_ntp, daemon=True).start()

    def _test_ntp_servers(self):
        """测试NTP服务器"""
        if not self.ntp_status_var or not self.server_test_text:
            return

        def _test_in_background():
            """在后台线程中执行NTP服务器测试"""
            try:
                results = self.time_sync.test_ntp_servers()

                def update_ui():
                    if results:
                        self.server_test_text.insert(tk.END, "NTP服务器测试结果:\n")
                        self.server_test_text.insert(tk.END, "-" * 50 + "\n")
                        for server, response_time in results:
                            self.server_test_text.insert(tk.END,
                                f"服务器: {server}\n响应时间: {response_time:.2f}ms\n\n")
                        self.ntp_status_var.set("测试完成")
                    else:
                        self.server_test_text.insert(tk.END, "所有NTP服务器测试失败")
                        self.ntp_status_var.set("测试失败")

                self.root.after(0, update_ui)
            except Exception as e:
                logger.error("测试NTP服务器出错: %s", str(e))
                def update_error():
                    self.server_test_text.insert(tk.END, f"测试NTP服务器时出错: {str(e)}")
                    self.ntp_status_var.set("测试出错")
                self.root.after(0, update_error)

        self.ntp_status_var.set("测试中...")
        self.server_test_text.delete(1.0, tk.END)

        import threading
        test_thread = threading.Thread(target=_test_in_background, daemon=True)
        test_thread.start()

    def _check_and_calibrate_if_needed(self, time_diff):
        """检查时间差并在需要时执行校准"""
        try:
            error_threshold = 5
            if self.ntp_threshold_var:
                try:
                    error_threshold = float(self.ntp_threshold_var.get())
                except ValueError:
                    pass

            logger.debug("检查时间差: %.2f秒, 阈值: %.2f秒, 正在校准: %s", 
                        time_diff, error_threshold, self._is_calibrating)

            if abs(time_diff) > error_threshold:
                logger.info("时间差 %.2f秒超过阈值 %.2f秒", time_diff, error_threshold)
                if not self._is_calibrating:
                    logger.info("开始执行自动校准")
                    self._is_calibrating = True
                    
                    import threading
                    calibrate_thread = threading.Thread(target=self._calibrate_in_background, daemon=True)
                    calibrate_thread.start()
                else:
                    logger.debug("校准正在进行中，跳过本次校准")
        except Exception as e:
            logger.error("检查和校准时出错: %s", str(e), exc_info=True)
            self._is_calibrating = False

    def _calibrate_in_background(self):
        """在后台线程中执行校准 - 调整本地时间与软件NTP时间一致"""
        logger.info("_calibrate_in_background 开始执行")
        try:
            error_threshold = 5
            if self.ntp_threshold_var:
                try:
                    error_threshold = float(self.ntp_threshold_var.get())
                except ValueError:
                    pass

            logger.info("开始校准时间，将本地时间调整为软件NTP时间: %.2f", self._software_ntp_time)
            
            # 使用软件内部的NTP时间来校准系统时间
            result = self._set_system_time_from_software_ntp()
            logger.info("校准返回结果: %s", result)
            
            if result['success']:
                if self.config and hasattr(self.config, 'log_time_calibration') and self.config.log_time_calibration:
                    logger.info("自动时间校准成功: %s", result['message'])
                # 校准成功后，同步软件本地时间到新的系统时间
                import time
                self._software_local_time = time.time()
                self.root.after(0, self._update_time_display)
            else:
                if self.config and hasattr(self.config, 'log_time_calibration') and self.config.log_time_calibration:
                    logger.warning("自动时间校准失败: %s", result['message'])
        except Exception as e:
            logger.error("后台校准时出错: %s", str(e), exc_info=True)
        finally:
            logger.info("_calibrate_in_background 执行完毕，重置 _is_calibrating 为 False")
            self._is_calibrating = False

    def _set_system_time_from_software_ntp(self):
        """使用软件内部的NTP时间设置系统时间"""
        import ctypes
        import datetime
        
        try:
            ntp_datetime_utc = datetime.datetime.utcfromtimestamp(self._software_ntp_time)
            
            st = time_sync.SYSTEMTIME()
            st.wYear = ntp_datetime_utc.year
            st.wMonth = ntp_datetime_utc.month
            st.wDay = ntp_datetime_utc.day
            st.wHour = ntp_datetime_utc.hour
            st.wMinute = ntp_datetime_utc.minute
            st.wSecond = int(ntp_datetime_utc.second)
            st.wMilliseconds = 0
            st.wDayOfWeek = ntp_datetime_utc.weekday()

            success = ctypes.windll.kernel32.SetSystemTime(ctypes.byref(st))
            if success:
                return {
                    "success": True,
                    "message": "时间校准成功！使用软件NTP时间"
                }
            else:
                return {
                    "success": False,
                    "message": "时间校准失败：需要管理员权限，请以管理员身份运行程序"
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"时间校准失败：{str(e)}"
            }

    def _calibrate_time(self):
        """校准系统时间"""
        try:
            error_threshold = 5
            if self.ntp_threshold_var:
                try:
                    error_threshold = float(self.ntp_threshold_var.get())
                except ValueError:
                    pass

            result = self.time_sync.calibrate_time(error_threshold=error_threshold)

            if result['success']:
                if self.config and hasattr(self.config, 'log_time_calibration') and self.config.log_time_calibration:
                    logger.info("时间校准成功: %s", result['message'])
                messagebox.showinfo("成功", result['message'])
                # 校准成功后，重新初始化软件时间
                import time
                self._software_local_time = time.time()
                self._force_update_ntp()
            else:
                if self.config and hasattr(self.config, 'log_time_calibration') and self.config.log_time_calibration:
                    logger.warning("时间校准失败: %s", result['message'])
                messagebox.showwarning("提示", result['message'])
        except Exception as e:
            logger.error("_calibrate_time 出错: %s", str(e), exc_info=True)
            messagebox.showerror("错误", f"时间校准失败: {str(e)}")

    def _on_auto_calibrate_changed(self, *args):
        """自动校准开关变化时的回调函数"""
        if self.ntp_auto_var and self.ntp_auto_var.get():
            self._reset_countdown()
        else:
            self._stop_countdown()
            try:
                interval = int(self.ntp_interval_var.get())
                self._current_countdown = interval
                self._update_countdown_display()
            except ValueError:
                pass

    def _on_interval_changed(self, *args):
        """检查间隔变化时的回调函数"""
        self._reset_countdown()

    def _reset_countdown(self):
        """重置倒计时"""
        try:
            interval = int(self.ntp_interval_var.get())
            if interval < 1:
                interval = 60
        except ValueError:
            interval = 60
        
        self._current_countdown = interval
        self._update_countdown_display()
        
        self._stop_countdown()
        
        if self.ntp_auto_var and self.ntp_auto_var.get():
            self._start_countdown()

    def _start_countdown(self):
        """启动倒计时"""
        self._stop_countdown()
        self._countdown_timer = self.root.after(1000, self._tick_countdown)

    def _stop_countdown(self):
        """停止倒计时"""
        if self._countdown_timer:
            self.root.after_cancel(self._countdown_timer)
            self._countdown_timer = None

    def _tick_countdown(self):
        """倒计时的tick"""
        self._current_countdown -= 1
        
        if self._current_countdown <= 0:
            self._auto_calibrate()
            self._reset_countdown()
        else:
            self._update_countdown_display()
            self._countdown_timer = self.root.after(1000, self._tick_countdown)

    def _update_countdown_display(self):
        """更新倒计时显示"""
        if self.ntp_countdown_var:
            self.ntp_countdown_var.set(f"({self._current_countdown}秒)")

    def _auto_calibrate(self):
        """执行自动校准"""
        try:
            error_threshold = 5
            if self.ntp_threshold_var:
                try:
                    error_threshold = float(self.ntp_threshold_var.get())
                except ValueError:
                    pass

            result = self.time_sync.calibrate_time(error_threshold=error_threshold)
            
            if result['success']:
                if self.config and hasattr(self.config, 'log_time_calibration') and self.config.log_time_calibration:
                    logger.info("自动时间校准成功: %s", result['message'])
                import time
                self._software_local_time = time.time()
                self._update_time_display()
            else:
                if self.config and hasattr(self.config, 'log_time_calibration') and self.config.log_time_calibration:
                    logger.warning("自动时间校准失败: %s", result['message'])
        except Exception as e:
            logger.error("_auto_calibrate 出错: %s", str(e), exc_info=True)
