# -*- coding: utf-8 -*-
# windowmanager/app.py
"""
应用程序入口模块
负责初始化、启动和主循环管理
"""

import sys
import os

# 强制启用 UTF-8 模式（Nuitka 编译后的 exe 在 Windows 中文环境下可能默认使用 GBK）
# 此设置等效于环境变量 PYTHONUTF8=1 或命令行参数 -X utf8
# 必须在所有其他导入之前执行，确保后续所有文件 I/O 使用 UTF-8 编码
os.environ["PYTHONUTF8"] = "1"

# 仅在开发环境下修改 sys.path（打包后模块已内嵌，无需动态添加路径）
if not getattr(sys, "frozen", False) and not hasattr(sys, "__nuitka_binary__"):
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    sys.path.append(os.getcwd())

import logging  # noqa: E402
import ctypes  # noqa: E402
import atexit  # noqa: E402
import signal  # noqa: E402
from pathlib import Path  # noqa: E402

# 统一的打包环境检测（兼容 PyInstaller 和 Nuitka）
# PyInstaller 设置 sys.frozen = True
# Nuitka 设置 sys.frozen = True 且存在 __nuitka_binary__ 属性
IS_FROZEN = getattr(sys, "frozen", False) or hasattr(sys, "__nuitka_binary__")

if IS_FROZEN:
    # 打包后的路径：exe 所在目录
    BASE_DIR = Path(sys.executable).parent
else:
    PROJECT_ROOT = Path(__file__).parent.parent.absolute()
    BASE_DIR = PROJECT_ROOT

# 配置日志（尽早创建日志目录，在 setup_logging() 之前就设置简单的文件日志）
# 这是为了捕获 PySide6 导入时可能发生的错误
_fallback_log = BASE_DIR / "logs" / "window_manager.log"
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

# 检测是否在打包环境中运行（已在文件顶部定义 IS_FROZEN）
logger = logging.getLogger(__name__)

# Win32 MessageBox 常量（app.py 不依赖 win32con，此处定义局部常量）
_MB_OK = 0x00000000
_MB_YESNO = 0x00000004
_MB_ICONERROR = 0x00000010
_MB_ICONWARNING = 0x00000030
_MB_ICONINFORMATION = 0x00000040
_IDYES = 6

if IS_FROZEN:
    logger.info("检测到打包环境")

try:
    try:
        from ui import AppWindow
        from manager import WindowManager
        from constants import AppConstants
        from utils import setup_logging, is_admin
        from config import ConfigManager
    except ImportError as e1:
        logger.warning("直接导入失败 (%s)，尝试 src. 前缀导入...", e1)
        from src.ui import AppWindow
        from src.manager import WindowManager
        from src.constants import AppConstants
        from src.utils import setup_logging, is_admin
        from src.config import ConfigManager
except ImportError as e:
    logger.error("导入失败: %s", str(e), exc_info=True)
    logger.error("sys.path: %s", sys.path[:5])
    logger.error("sys.modules keys (partial): %s", list(sys.modules.keys())[:20])
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
                    0, f"{AppConstants.APP_TITLE}已经在运行中！", "提示", _MB_ICONINFORMATION | _MB_OK
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


def force_exit(_signum, _frame):
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
            _MB_YESNO | _MB_ICONINFORMATION
        )
        return result == _IDYES
    except Exception as e:
        logger.error("显示权限提升对话框失败: %s", e)
        return False


def handle_uncaught_exception(exc_type, exc_value, exc_traceback):
    """全局未捕获异常处理函数 - 增强版，防止程序退出"""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.critical("未捕获的异常:", exc_info=(exc_type, exc_value, exc_traceback))

    try:
        error_message = (
            f"程序发生未捕获的异常:\n\n"
            f"{exc_type.__name__}: {exc_value}\n\n"
            f"程序将尝试继续运行。"
        )
        # 优先使用 Qt 消息框（主线程中更友好）
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox
            if QApplication.instance():
                QMessageBox.critical(None, "错误", error_message)
            else:
                ctypes.windll.user32.MessageBoxW(None, error_message, "错误", _MB_ICONERROR | _MB_OK)
        except Exception:
            ctypes.windll.user32.MessageBoxW(None, error_message, "错误", _MB_ICONERROR | _MB_OK)

        # 尝试恢复关键服务
        try:
            if _app_window and hasattr(_app_window, 'hotkey_manager'):
                _app_window.hotkey_manager.check_health()
        except Exception as recover_error:
            logger.error("恢复热键服务失败: %s", str(recover_error))

    except Exception as msg_error:
        logger.error("显示错误消息失败: %s", msg_error)


def _check_admin_privileges():
    """检查并尝试提升管理员权限

    返回:
        int: 0 表示继续运行，1 表示应退出（权限提升成功后新实例启动）
    """
    if not is_admin():
        logger.info("未以管理员权限运行，尝试提升权限...")
        if prompt_admin_elevation():
            if run_as_admin():
                logger.info("已提升为管理员权限，当前实例将退出")
                return 1
            logger.warning("提升管理员权限失败，继续以有限权限运行")
        else:
            logger.info("用户取消权限提升，继续以有限权限运行")
    else:
        logger.info("正在以管理员权限运行")
    return 0


def _check_elevation_result():
    """检查权限提升结果，如果失败则显示警告"""
    if "--admin-elevation-attempted" not in sys.argv:
        return
    if is_admin():
        return
    logger.warning("权限提升未成功，程序将以有限权限运行，部分功能可能受限")
    try:
        warning_message = (
            "权限提升未成功，程序将以有限权限运行。\n\n部分窗口管理功能可能无法正常工作。"
        )
        ctypes.windll.user32.MessageBoxW(
            None, warning_message, "权限警告", _MB_ICONWARNING | _MB_OK
        )
    except Exception as msg_error:
        logger.error("显示权限警告失败: %s", msg_error)


def _init_window_manager(qt_app):
    """初始化窗口管理器和主窗口

    参数:
        qt_app: QApplication 实例

    返回:
        tuple: (window_manager, main_window) 或 (None, None) 如果失败
    """
    window_manager = WindowManager()

    logger.info("正在初始化窗口管理器缓存...")
    window_manager.init_cache()

    logger.info("正在检测隐藏窗口...")
    config_manager = ConfigManager.get_instance()
    config = config_manager.load()
    keywords = config.filter.keywords
    logger.info("使用关键字列表检测隐藏窗口: %s", keywords)
    hidden_windows = window_manager.detect_target_windows(keywords)
    if hidden_windows:
        logger.info("检测到 %d 个隐藏窗口，已添加到选中窗口列表", len(hidden_windows))
    else:
        logger.info("未检测到被隐藏的窗口")

    main_window = AppWindow(window_manager)
    logger.info("主窗口已初始化并显示")

    return window_manager, main_window


def main():
    """主函数 - PySide6版本"""
    from PySide6.QtWidgets import QApplication

    sys.excepthook = handle_uncaught_exception

    setup_logging()
    logger.info("=" * 50)
    logger.info("窗口管理器启动中...")
    logger.info("=" * 50)
    logger.info("进程ID: %d", os.getpid())

    if _check_admin_privileges() != 0:
        return 0

    _check_elevation_result()

    if is_already_running():
        logger.info("应用程序已在运行，正在退出...")
        return 1

    atexit.register(cleanup_mutex)

    try:
        signal.signal(signal.SIGTERM, force_exit)
        signal.signal(signal.SIGINT, force_exit)
    except Exception as e:
        logger.warning("注册信号处理程序失败: %s", str(e))

    try:
        global _qt_app
        _qt_app = QApplication(sys.argv)
        _qt_app.setApplicationName(AppConstants.APP_TITLE)
        _qt_app.setQuitOnLastWindowClosed(False)

        # 安装 Qt 事件循环异常过滤器，防止未捕获异常导致程序退出
        def _qt_exception_hook(exc_type, exc_value, exc_tb):
            logger.critical("Qt 事件循环未捕获异常:", exc_info=(exc_type, exc_value, exc_tb))
            try:
                if _app_window and hasattr(_app_window, 'hotkey_manager'):
                    _app_window.hotkey_manager.check_health()
            except Exception:
                pass

        from PySide6.QtCore import qInstallMessageHandler

        def _qt_message_handler(msg_type, context, msg):
            level_map = {
                0: logging.DEBUG,
                1: logging.WARNING,
                2: logging.ERROR,
                4: logging.INFO,
            }
            level = level_map.get(msg_type, logging.WARNING)
            logger.log(level, "Qt 消息: %s", msg)
        qInstallMessageHandler(_qt_message_handler)

        _, main_window = _init_window_manager(_qt_app)
        global _app_window
        _app_window = main_window

        exit_code = _qt_app.exec()
        logger.info("窗口管理器正常退出，退出码: %d", exit_code)
        return exit_code

    except Exception as e:
        logger.critical("应用程序错误: %s", e, exc_info=True)
        # 尝试恢复而不是直接退出
        try:
            if _app_window and hasattr(_app_window, 'hotkey_manager'):
                _app_window.hotkey_manager.check_health()
            logger.info("尝试从应用程序错误中恢复...")
            if _qt_app:
                return _qt_app.exec()
        except Exception:
            pass
        return 1
    finally:
        cleanup_mutex()
        _app_window = None
        _qt_app = None


if __name__ == "__main__":
    sys.exit(main())
