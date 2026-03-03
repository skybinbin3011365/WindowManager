# windowmanager/app.py
"""
窗口管理器 - 应用模块
简化版本：应用入口
"""
import sys
import logging
import ctypes
import os
import atexit
import signal

from .constants import ERROR_ALREADY_EXISTS, APP_GUID, APP_TITLE
from .config import ConfigManager, Config
from .utils import setup_logging
from . import manager
from . import ui
from . import hotkey_manager
from . import time_sync

WindowManager = manager.WindowManager
AppWindow = ui.AppWindow

# 智能导入处理 - 支持直接运行、包导入和PyInstaller打包环境
try:
    # 检查是否在PyInstaller打包环境中
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # PyInstaller打包环境
        base_path = sys._MEIPASS
        sys.path.insert(0, base_path)
        IMPORT_MODE = "pyinstaller"
    else:
        # 开发环境
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            sys.path.insert(0, current_dir)
        except NameError:
            # __file__不可用时使用当前目录
            current_dir = os.getcwd()
            sys.path.insert(0, current_dir)
        IMPORT_MODE = "direct"
except ImportError as e:
    # 导入失败时，添加更多的路径尝试
    try:
        if not getattr(sys, 'frozen', False):
            # 仅在开发环境尝试额外路径
            try:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                parent_dir = os.path.dirname(current_dir)
                sys.path.insert(0, parent_dir)
                sys.path.insert(0, os.path.join(parent_dir, 'src'))
            except NameError:
                pass
        if not getattr(sys, 'frozen', False):
            IMPORT_MODE = "parent"
    except ImportError as e2:
        # 导入失败，输出详细信息
        print(f"Import error: {e2}")
        print(f"Current directory: {os.getcwd()}")
        print(f"Python path: {sys.path}")
        print(f"Frozen: {getattr(sys, 'frozen', False)}")
        if hasattr(sys, '_MEIPASS'):
            print(f"MEIPASS: {sys._MEIPASS}")
        logging.basicConfig(level=logging.DEBUG)
        logger = logging.getLogger(__name__)
        logger.critical("Failed to import required modules: %s", str(e2))
        sys.exit(1)

logger = logging.getLogger(__name__)

# 全局互斥体引用
_mutex_handle = None
# 全局应用窗口引用，用于强制退出
_app_window = None

def cleanup_mutex():
    """清理互斥体资源"""
    global _mutex_handle
    if _mutex_handle:
        try:
            ctypes.windll.kernel32.CloseHandle(_mutex_handle)
            _mutex_handle = None
            logger.info("Mutex cleaned up")
        except Exception as e:
            logger.error("Error cleaning up mutex: %s", str(e))

def is_already_running():
    """检查程序是否已经在运行（改进版本）"""
    global _mutex_handle
    try:
        # 使用多种方式检测，确保可靠性
        # 方式1：全局互斥体
        global_mutex_name = f"Global\\{APP_GUID}"
        # 方式2：本地互斥体（作为备选）
        local_mutex_name = APP_GUID
        
        # 首先尝试创建全局互斥体
        mutex = ctypes.windll.kernel32.CreateMutexW(
            None,
            True,
            global_mutex_name
        )

        if mutex == 0:
            logger.error("Failed to create global mutex, trying local mutex")
            # 全局互斥体失败，尝试本地互斥体
            mutex = ctypes.windll.kernel32.CreateMutexW(
                None,
                True,
                local_mutex_name
            )
            if mutex == 0:
                logger.error("Failed to create any mutex, assuming not running")
                # 如果连本地互斥体都创建失败，可能是权限问题，允许运行
                return False
        
        # 立即保存互斥体句柄引用
        _mutex_handle = mutex
        
        # 检查是否已经存在
        last_error = ctypes.windll.kernel32.GetLastError()
        if last_error == ERROR_ALREADY_EXISTS:
            logger.info("Application is already running (detected by mutex)")
            # 显示弹出提示
            try:
                ctypes.windll.user32.MessageBoxW(
                    0,
                    f"{APP_TITLE}已经在运行中！",
                    "提示",
                    0x40 | 0x1
                )
            except Exception as msg_error:
                logger.error("Failed to show message box: %s", str(msg_error))
            finally:
                cleanup_mutex()
            return True
        
        logger.info("Application mutex created successfully")
        return False
    except Exception as e:
        logger.error("Unexpected error checking if already running: %s", str(e), exc_info=True)
        cleanup_mutex()
        # 出错时允许运行，避免程序无法启动
        return False

def force_exit(signum, frame):
    """强制退出处理函数"""
    logger.warning("Force exit signal received")
    global _app_window
    try:
        if _app_window:
            # 尝试正常关闭
            _app_window._on_close()
    except Exception as e:
        logger.error("Error during forced exit: %s", str(e))
    finally:
        cleanup_mutex()
        # 强制退出
        os._exit(1)

def main():
    setup_logging()
    logger.info("=" * 50)
    logger.info("Window Manager Starting... (Import mode: %s)", IMPORT_MODE)
    logger.info("=" * 50)
    logger.info("Process ID: %d", os.getpid())

    # 注册程序退出时清理互斥体
    atexit.register(cleanup_mutex)
    
    # 注册信号处理，用于强制退出
    try:
        signal.signal(signal.SIGTERM, force_exit)
        signal.signal(signal.SIGINT, force_exit)
    except Exception as e:
        logger.warning("Failed to register signal handlers: %s", str(e))

    # 检查程序是否已经在运行
    if is_already_running():
        logger.info("Application is already running, exiting...")
        return 1

    try:
        window_manager = WindowManager()
        main_window = AppWindow(window_manager)
        global _app_window
        _app_window = main_window
        main_window.run()
        logger.info("Window Manager exited normally")
    except Exception as e:
        logger.critical("Application error: %s", e, exc_info=True)
        return 1
    finally:
        # 确保互斥体被清理
        cleanup_mutex()
        _app_window = None
    return 0


if __name__ == "__main__":
    sys.exit(main())
