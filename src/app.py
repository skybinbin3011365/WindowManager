# windowmanager/app.py
"""
应用程序入口模块
负责初始化、启动和主循环管理
"""

import sys
import os
import logging
import ctypes
import atexit
import signal
from pathlib import Path

# 设置基础目录（保留对PyInstaller打包的支持）
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    PROJECT_ROOT = Path(__file__).parent.parent.absolute()
    BASE_DIR = PROJECT_ROOT

# 配置日志（尽早创建日志目录，在 setup_logging() 之前就设置简单的文件日志）
# 这是为了捕获 PySide6 导入时可能发生的错误
_fallback_log = BASE_DIR / "logs" / "windowmanager.log"
_fallback_log.parent.mkdir(parents=True, exist_ok=True)

# 在模块级别就设置简单的文件日志，确保即使在导入阶段崩溃也能记录错误
try:
    _fallback_handler = logging.FileHandler(str(_fallback_log), encoding='utf-8')
    _fallback_handler.setLevel(logging.DEBUG)
    _fallback_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logging.getLogger().addHandler(_fallback_handler)
    logging.getLogger().setLevel(logging.DEBUG)
except Exception:
    # 如果连文件日志都无法创建，就没办法记录错误了
    pass

# 检测是否在打包环境中运行
IS_FROZEN = getattr(sys, "frozen", False)
logger = logging.getLogger(__name__)

if IS_FROZEN:
    logger.info("检测到打包环境")

try:
    from ui import AppWindow
    from manager import WindowManager
    from constants import AppConstants
    from utils import setup_logging, is_admin
    from config import ConfigManager
except ImportError as e:
    logger.error("导入失败: %s", str(e))
    sys.exit(1)

# 全局互斥体引用
_mutex_handle = None
# 全局应用窗口引用，用于强制退出
_app_window = None
# 全局QApplication引用
_qt_app = None


def cleanup_mutex():
    """清理互斥体资源"""
    global _mutex_handle
    if _mutex_handle:
        try:
            # 检查句柄有效性
            ctypes.windll.kernel32.CloseHandle(_mutex_handle)
            _mutex_handle = None
            logger.info("互斥体已清理")
        except Exception as e:
            logger.error("清理互斥体失败: %s", str(e))


def is_already_running():
    """检查程序是否已经在运行（改进版本）"""
    global _mutex_handle
    try:
        # 使用多种方式检测，确保可靠性
        # 方式1：全局互斥体
        global_mutex_name = f"Global\\{AppConstants.APP_GUID}"
        # 方式2：本地互斥体（作为备选）
        local_mutex_name = AppConstants.APP_GUID

        # 首先尝试创建全局互斥体
        mutex = ctypes.windll.kernel32.CreateMutexW(
            None, True, global_mutex_name)

        if mutex == 0:
            last_error = ctypes.windll.kernel32.GetLastError()
            logger.error(f"创建全局互斥体失败，错误码: {last_error}，尝试本地互斥体")
            # 全局互斥体失败，尝试本地互斥体
            mutex = ctypes.windll.kernel32.CreateMutexW(
                None, True, local_mutex_name)
            if mutex == 0:
                last_error = ctypes.windll.kernel32.GetLastError()
                logger.error(f"创建任何互斥体都失败，错误码: {last_error}，假设程序未运行")
                # 如果连本地互斥体都创建失败，可能是权限问题，允许运行
                return False

        # 立即保存互斥体句柄引用
        _mutex_handle = mutex

        # 检查是否已经存在
        last_error = ctypes.windll.kernel32.GetLastError()
        if last_error == AppConstants.ERROR_ALREADY_EXISTS:
            logger.info("应用程序已在运行（通过互斥体检测到）")
            # 显示弹出提示
            try:
                ctypes.windll.user32.MessageBoxW(
                    0, f"{AppConstants.APP_TITLE}已经在运行中！", "提示", 0x40 | 0x1
                )
            except Exception as msg_error:
                logger.error("显示提示框失败: %s", str(msg_error))
            finally:
                cleanup_mutex()
            return True

        logger.info("应用程序互斥体创建成功")
        return False
    except Exception as e:
        logger.error("检查程序是否已在运行时发生未知错误: %s", str(e), exc_info=True)
        cleanup_mutex()
        # 出错时允许运行，避免程序无法启动
        return False


def force_exit(signum, frame):
    """强制退出处理函数"""
    logger.warning("收到强制退出信号")
    global _app_window, _qt_app
    try:
        if _app_window:
            # 尝试正常关闭
            _app_window._on_close()
            _app_window = None  # 确保标记为 None
        if _qt_app:
            _qt_app.quit()
            _qt_app = None  # 确保标记为 None
    except Exception as e:
        logger.error("强制退出时出错: %s", str(e))
    finally:
        cleanup_mutex()
        # 使用 sys.exit 让 Python 正常执行清理流程（atexit、finally、对象析构器）
        sys.exit(1)


def run_as_admin():
    """以管理员权限重新运行程序"""
    try:
        # 构建命令行参数
        if sys.executable.endswith("python.exe") or sys.executable.endswith("pythonw.exe"):
            params = " ".join(
                [f'"{arg}"' if " " in arg else arg for arg in sys.argv])
            # 为新进程设置环境变量（通过命令行参数传递）
            # 注意：ShellExecuteW 不支持直接传递环境变量，我们通过命令行参数传递
            # 然后在新进程中检查这个参数
            if "ADMIN_ELEVATION_ATTEMPTED" not in sys.argv:
                params += " --admin-elevation-attempted"
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, params, None, 1)
        else:
            # 对于编译后的可执行文件，使用 ShellExecuteW
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, "--admin-elevation-attempted", None, 1
            )
        return True
    except Exception as e:
        logger.error("以管理员权限运行失败: %s", str(e))
        return False


def prompt_admin_elevation() -> bool:
    """请求管理员权限提升的用户确认对话框

    使用 Windows 原生 MessageBox，不依赖 Qt，可以在 QApplication 创建之前调用。

    Returns:
        bool: 用户确认返回 True，取消返回 False
    """
    try:
        # 使用 Windows 原生 MessageBox，不依赖 Qt
        result = ctypes.windll.user32.MessageBoxW(
            None,
            "窗口管理器需要管理员权限来管理窗口。\n\n"
            "是否立即提升权限并重启程序？\n\n"
            '点击"是"提升权限，点击"否"以有限权限继续运行（部分功能可能受限）。',
            "权限提升请求",
            0x24 | 0x40  # MB_YESNO | MB_ICONINFORMATION
        )
        return result == 6  # IDYES
    except Exception as e:
        logger.error("显示权限提升对话框失败: %s", e)
        return False


def handle_uncaught_exception(exc_type, exc_value, exc_traceback):
    """全局未捕获异常处理函数"""
    if issubclass(exc_type, KeyboardInterrupt):
        # 忽略键盘中断，让正常的退出流程处理
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    # 记录异常到日志
    logger.critical("未捕获的异常:", exc_info=(exc_type, exc_value, exc_traceback))

    # 尝试使用 MessageBox 显示错误信息（不依赖 Qt）
    try:
        error_message = f"程序发生未捕获的异常:\n\n{exc_type.__name__}: {exc_value}\n\n请查看日志文件获取详细信息。"
        ctypes.windll.user32.MessageBoxW(
            None, error_message, "错误", 0x10 | 0x1  # MB_ICONERROR | MB_OK
        )
    except Exception as msg_error:
        logger.error("显示错误消息失败: %s", msg_error)


def main():
    """主函数 - PySide6版本"""
    from PySide6.QtWidgets import QApplication

    # 设置全局未捕获异常钩子
    sys.excepthook = handle_uncaught_exception

    setup_logging()
    logger.info("=" * 50)
    logger.info("窗口管理器启动中...")
    logger.info("=" * 50)
    logger.info("进程ID: %d", os.getpid())

    if not is_admin():
        logger.info("未以管理员权限运行，尝试提升权限...")
        if prompt_admin_elevation():
            if run_as_admin():
                logger.info("已提升为管理员权限，当前实例将退出")
                return 0
            else:
                logger.warning("提升管理员权限失败，继续以有限权限运行")
        else:
            logger.info("用户取消权限提升，继续以有限权限运行")
    else:
        logger.info("正在以管理员权限运行")

    # 权限提升后验证：如果用户选择了提升权限，但当前实例仍不是管理员，说明提升失败
    if "--admin-elevation-attempted" in sys.argv:
        if not is_admin():
            logger.warning("权限提升未成功，程序将以有限权限运行，部分功能可能受限")
            try:
                # 显示警告信息
                warning_message = (
                    "权限提升未成功，程序将以有限权限运行。\n\n部分窗口管理功能可能无法正常工作。"
                )
                ctypes.windll.user32.MessageBoxW(
                    None, warning_message, "权限警告", 0x30 | 0x1  # MB_ICONWARNING | MB_OK
                )
            except Exception as msg_error:
                logger.error("显示权限警告失败: %s", msg_error)

    # 检查程序是否已经在运行
    if is_already_running():
        logger.info("应用程序已在运行，正在退出...")
        return 1

    # 注册程序退出时清理互斥体（在确认不是重复运行后注册）
    atexit.register(cleanup_mutex)

    # 注册信号处理，用于强制退出
    try:
        signal.signal(signal.SIGTERM, force_exit)
        signal.signal(signal.SIGINT, force_exit)
    except Exception as e:
        logger.warning("注册信号处理程序失败: %s", str(e))

    try:
        # 创建QApplication实例
        global _qt_app
        _qt_app = QApplication(sys.argv)

        # 设置应用程序属性
        _qt_app.setApplicationName(AppConstants.APP_TITLE)
        _qt_app.setQuitOnLastWindowClosed(False)  # 关闭窗口时不退出，最小化到托盘

        # 创建窗口管理器
        window_manager = WindowManager()

        # 初始化缓存，填充黑白名单
        logger.info("正在初始化窗口管理器缓存...")
        window_manager.init_cache()

        # 自动检测隐藏窗口并将其添加到选中窗口列表
        logger.info("正在检测隐藏窗口...")
        # 加载配置，获取关键字列表
        config_manager = ConfigManager.get_instance()
        config = config_manager.load()
        keywords = config.keywords
        logger.info("使用关键字列表检测隐藏窗口: %s", keywords)
        # 检测隐藏窗口（不恢复，只添加到列表）
        hidden_windows = window_manager.recover_hidden_windows(keywords)
        if hidden_windows:
            logger.info("检测到 %d 个隐藏窗口，已添加到选中窗口列表", len(hidden_windows))
        else:
            logger.info("未检测到被隐藏的窗口")

        # 创建主窗口
        main_window = AppWindow(window_manager)
        global _app_window
        _app_window = main_window

        # 主窗口在初始化时已经显示
        logger.info("主窗口已初始化并显示")

        # 运行事件循环
        exit_code = _qt_app.exec()

        logger.info("窗口管理器正常退出，退出码: %d", exit_code)
        return exit_code

    except Exception as e:
        logger.critical("应用程序错误: %s", e, exc_info=True)
        return 1
    finally:
        # 确保互斥体被清理
        cleanup_mutex()
        _app_window = None
        _qt_app = None


if __name__ == "__main__":
    sys.exit(main())
