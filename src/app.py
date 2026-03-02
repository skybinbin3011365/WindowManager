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
    """检查程序是否已经在运行"""
    global _mutex_handle
    try:
        # 首先尝试创建全局互斥体（跨会话，管理员和普通用户都能看到）
        # 使用Global\前缀确保在全局命名空间创建互斥体
        global_mutex_name = f"Global\\{APP_GUID}"
        
        # 创建安全描述符，允许所有用户访问
        # 定义SECURITY_ATTRIBUTES结构体
        class SECURITY_ATTRIBUTES(ctypes.Structure):
            _fields_ = [
                ("nLength", ctypes.c_ulong),
                ("lpSecurityDescriptor", ctypes.c_void_p),
                ("bInheritHandle", ctypes.c_int)
            ]
        
        # 创建允许所有人访问的安全描述符
        # 简化处理：先尝试不使用安全描述符
        mutex = ctypes.windll.kernel32.CreateMutexW(
            None,  # lpMutexAttributes
            True,   # bInitialOwner
            global_mutex_name  # lpName - 使用全局命名空间
        )

        # 检查是否成功创建互斥体
        if mutex == 0:
            logger.error("Failed to create global mutex, trying local mutex")
            # 如果全局互斥体创建失败，尝试本地互斥体
            mutex = ctypes.windll.kernel32.CreateMutexW(
                None,
                True,
                APP_GUID
            )
            if mutex == 0:
                logger.error("Failed to create any mutex")
                return True

        # 立即保存互斥体句柄引用，确保后续可以清理
        _mutex_handle = mutex

        # 检查互斥体是否已经存在
        last_error = ctypes.windll.kernel32.GetLastError()
        if last_error == ERROR_ALREADY_EXISTS:
            logger.info("Application is already running (detected by mutex)")
            # 显示弹出提示
            try:
                ctypes.windll.user32.MessageBoxW(
                    0,  # hWnd
                    f"{APP_TITLE}已经在运行中！",  # lpText
                    "提示",  # lpCaption
                    0x40 | 0x1  # MB_ICONINFORMATION | MB_OK
                )
            except Exception as msg_error:
                logger.error("Failed to show message box: %s", str(msg_error))
            finally:
                # 程序已运行，清理互斥体句柄
                cleanup_mutex()
            return True

        logger.info("Application mutex created successfully")
        return False
    except OSError as e:
        logger.error("OS error checking if already running: %s", str(e))
        cleanup_mutex()
        return False
    except Exception as e:
        logger.error("Unexpected error checking if already running: %s", str(e))
        cleanup_mutex()
        return False

def main():
    setup_logging()
    logger.info("=" * 50)
    logger.info("Window Manager Starting... (Import mode: %s)", IMPORT_MODE)
    logger.info("=" * 50)

    # 注册程序退出时清理互斥体
    atexit.register(cleanup_mutex)

    # 检查程序是否已经在运行
    if is_already_running():
        logger.info("Application is already running, exiting...")
        # 这里可以添加代码来显示已运行的实例
        return 1

    try:
        window_manager = WindowManager()
        main_window = AppWindow(window_manager)
        main_window.run()
        logger.info("Window Manager exited normally")
    except Exception as e:
        logger.critical("Application error: %s", e, exc_info=True)
        return 1
    finally:
        # 确保互斥体被清理
        cleanup_mutex()
    return 0


if __name__ == "__main__":
    sys.exit(main())
