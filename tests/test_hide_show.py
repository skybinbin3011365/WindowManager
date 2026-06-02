#!/usr/bin/env python3
"""
窗口隐藏/显示功能测试脚本

用于测试 WindowOperator 的 hide_window / show_window / show_and_minimize_window 功能。
支持两种测试模式：
1. 自动模式：创建临时的测试记事本窗口进行测试
2. 手动模式：指定窗口句柄进行测试

使用方法：
    python test_hide_show.py --auto           # 自动创建记事本测试
    python test_hide_show.py --hwnd 12345     # 测试指定窗口句柄
    python test_hide_show.py --list            # 列出所有可见窗口
"""

import argparse
import logging
import sys
import time
import subprocess
import os

# 设置日志
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("test_hide_show")


def setup_import():
    """设置模块导入路径"""
    project_root = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.join(project_root, "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)


def list_all_windows():
    """列出所有可见窗口"""
    setup_import()
    from core import SafeWindowsAPI

    logger.info("=" * 60)
    logger.info("所有可见窗口列表：")
    logger.info("=" * 60)

    windows = []
    try:
        def callback(hwnd, _):
            try:
                if not SafeWindowsAPI.is_window(hwnd):
                    return True
                if not SafeWindowsAPI.window_has_visible_style(hwnd):
                    return True
                title = SafeWindowsAPI.get_window_text(hwnd).strip()
                if not title:
                    return True
                class_name = SafeWindowsAPI.get_window_class(hwnd)
                _, pid = SafeWindowsAPI.get_window_thread_process_id(hwnd)
                process_name = SafeWindowsAPI.get_process_name(pid)
                windows.append((hwnd, title, class_name, pid, process_name))
            except Exception:
                pass
            return True

        import win32gui
        win32gui.EnumWindows(callback, None)
    except ImportError:
        logger.error("win32gui 模块不可用")
        return

    # 按进程名分组显示
    by_process = {}
    for hwnd, title, class_name, pid, process_name in windows:
        if process_name not in by_process:
            by_process[process_name] = []
        by_process[process_name].append((hwnd, title, class_name))

    for process_name, wins in sorted(by_process.items()):
        logger.info(f"\n[{process_name}] ({len(wins)} 个窗口)")
        for hwnd, title, class_name in wins:
            title_short = title[:40] + "..." if len(title) > 40 else title
            logger.info(f"  HWND={hwnd:8d} | {title_short}")
            logger.info(f"            | class={class_name}")

    logger.info(f"\n总计: {len(windows)} 个窗口")


def find_test_window(process_name_hint: str = "") -> tuple:
    """查找测试窗口"""
    setup_import()
    from core import SafeWindowsAPI

    target_windows = []
    try:
        def callback(hwnd, _):
            try:
                if not SafeWindowsAPI.is_window(hwnd):
                    return True
                if not SafeWindowsAPI.window_has_visible_style(hwnd):
                    return True
                title = SafeWindowsAPI.get_window_text(hwnd).strip()
                if not title:
                    return True
                _, pid = SafeWindowsAPI.get_window_thread_process_id(hwnd)
                process_name = SafeWindowsAPI.get_process_name(pid)
                if not process_name_hint or process_name_hint.lower() in process_name.lower():
                    target_windows.append((hwnd, title, process_name))
            except Exception:
                pass
            return True

        import win32gui
        win32gui.EnumWindows(callback, None)
    except ImportError:
        logger.error("win32gui 模块不可用")
        return None

    return target_windows[0] if target_windows else None


def test_hide_show_by_hwnd(hwnd: int):
    """测试指定窗口的隐藏/显示功能"""
    setup_import()
    from window_operations import WindowOperator
    from core import SafeWindowsAPI

    op = WindowOperator()

    # 获取窗口信息
    try:
        title = SafeWindowsAPI.get_window_text(hwnd)
        _, pid = SafeWindowsAPI.get_window_thread_process_id(hwnd)
        process_name = SafeWindowsAPI.get_process_name(pid)
        is_visible = SafeWindowsAPI.window_has_visible_style(hwnd)
        logger.info(f"窗口信息: HWND={hwnd}, PID={pid}, 进程={process_name}")
        logger.info(f"窗口标题: {title}")
        logger.info(f"当前可见: {is_visible}")
    except Exception as e:
        logger.error(f"获取窗口信息失败: {e}")
        return

    # 测试隐藏
    logger.info("\n" + "=" * 40)
    logger.info("步骤1: 隐藏窗口")
    logger.info("=" * 40)
    try:
        success = op.hide_window(hwnd)
        logger.info(f"hide_window() 返回: {success}")
        time.sleep(0.5)
        is_visible_after = SafeWindowsAPI.window_has_visible_style(hwnd)
        logger.info(f"隐藏后可见性: {is_visible_after} (应为 False)")
        assert not is_visible_after, "隐藏后窗口仍然可见！"
        logger.info("✓ 隐藏成功")
    except AssertionError as e:
        logger.error(f"✗ 隐藏失败: {e}")
        return
    except Exception as e:
        logger.error(f"隐藏操作异常: {e}")
        return

    # 测试显示
    logger.info("\n" + "=" * 40)
    logger.info("步骤2: 显示窗口")
    logger.info("=" * 40)
    try:
        success = op.show_window(hwnd)
        logger.info(f"show_window() 返回: {success}")
        time.sleep(0.5)
        is_visible_after = SafeWindowsAPI.window_has_visible_style(hwnd)
        logger.info(f"显示后可见性: {is_visible_after} (应为 True)")
        assert is_visible_after, "显示后窗口仍然不可见！"
        logger.info("✓ 显示成功")
    except AssertionError as e:
        logger.error(f"✗ 显示失败: {e}")
        return
    except Exception as e:
        logger.error(f"显示操作异常: {e}")
        return

    # 测试显示并最小化
    logger.info("\n" + "=" * 40)
    logger.info("步骤3: 显示并最小化窗口")
    logger.info("=" * 40)
    try:
        success = op.show_and_minimize_window(hwnd)
        logger.info(f"show_and_minimize_window() 返回: {success}")
        time.sleep(0.5)
        from core import win32con
        placement = SafeWindowsAPI.get_window_placement(hwnd)
        if placement:
            logger.info(f"窗口位置状态: {placement[0]} (SW_SHOWMINIMIZED={win32con.SW_SHOWMINIMIZED})")
            is_minimized = placement[0] == win32con.SW_SHOWMINIMIZED
            logger.info(f"最小化状态: {is_minimized} (应为 True)")
            assert is_minimized, "窗口未最小化！"
            logger.info("✓ 显示并最小化成功")
        else:
            logger.warning("无法获取窗口位置状态")
    except AssertionError as e:
        logger.error(f"✗ 显示并最小化失败: {e}")
        return
    except Exception as e:
        logger.error(f"显示并最小化操作异常: {e}")
        return

    logger.info("\n" + "=" * 60)
    logger.info("所有测试通过！")
    logger.info("=" * 60)


def test_auto():
    """自动测试模式：创建记事本窗口进行测试"""
    logger.info("=" * 60)
    logger.info("自动测试模式")
    logger.info("=" * 60)

    # 查找记事本进程
    test_process_hint = "notepad"
    existing = find_test_window(test_process_hint)

    if existing:
        hwnd, title, process_name = existing
        logger.info(f"找到现有记事本窗口: HWND={hwnd}, 标题={title}")
    else:
        # 启动记事本
        logger.info(f"未找到 {test_process_hint}，正在启动...")
        try:
            proc = subprocess.Popen(
                [os.environ.get("COMSPEC", "cmd.exe"), "/c", "start", "notepad"],
                shell=True,
            )
            time.sleep(1.5)
            # 关闭启动的 cmd 窗口
            try:
                subprocess.run(["taskkill", "/F", "/IM", "cmd.exe"], capture_output=True, timeout=2)
            except Exception:
                pass
        except Exception as e:
            logger.error(f"启动记事本失败: {e}")
            return

        # 查找记事本窗口
        for attempt in range(5):
            existing = find_test_window(test_process_hint)
            if existing:
                hwnd, title, process_name = existing
                logger.info(f"找到记事本窗口: HWND={hwnd}, 标题={title}")
                break
            logger.info(f"等待记事本窗口出现... ({attempt + 1}/5)")
            time.sleep(0.5)
        else:
            logger.error("未能找到或启动记事本窗口")
            logger.info("请手动指定窗口句柄进行测试：")
            logger.info("  python test_hide_show.py --list  # 查看所有窗口")
            logger.info("  python test_hide_show.py --hwnd <HWND>  # 测试指定窗口")
            return

    # 执行测试
    test_hide_show_by_hwnd(existing[0])

    # 询问是否关闭记事本
    if not find_test_window(test_process_hint):
        logger.info("记事本窗口已不存在，跳过关闭步骤")
    else:
        logger.info("\n测试完成，记事本窗口保持打开状态")
        logger.info("可以手动关闭记事本，或继续测试其他功能")


def test_manager_flow():
    """测试 WindowManager 的完整隐藏/显示流程"""
    setup_import()
    from manager import WindowManager

    logger.info("=" * 60)
    logger.info("WindowManager 完整流程测试")
    logger.info("=" * 60)

    # 创建 WindowManager
    wm = WindowManager()
    wm.start()

    # 查找测试窗口
    existing = find_test_window("notepad")
    if not existing:
        logger.error("未找到测试窗口，请先运行 --auto 或使用 --list 查看窗口")
        return

    hwnd, title, process_name = existing
    logger.info(f"测试窗口: HWND={hwnd}, 标题={title}")

    # 测试隐藏
    logger.info("\n--- 隐藏窗口 ---")
    success = wm.hide_window(hwnd)
    logger.info(f"hide_window() = {success}")
    time.sleep(0.3)

    # 检查窗口是否被隐藏
    hidden_list = wm.get_software_hidden_windows()
    logger.info(f"软件隐藏列表: {hidden_list}")

    # 测试显示
    logger.info("\n--- 显示窗口 ---")
    success = wm.show_and_minimize_window(hwnd)
    logger.info(f"show_and_minimize_window() = {success}")

    wm.stop()
    logger.info("\n✓ WindowManager 流程测试完成")


def main():
    parser = argparse.ArgumentParser(
        description="窗口隐藏/显示功能测试脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python test_hide_show.py --list          # 列出所有窗口
  python test_hide_show.py --auto         # 自动测试（启动记事本）
  python test_hide_show.py --hwnd 12345   # 测试指定窗口
  python test_hide_show.py --manager      # 测试 WindowManager 流程
        """,
    )
    parser.add_argument("--list", action="store_true", help="列出所有可见窗口")
    parser.add_argument("--auto", action="store_true", help="自动测试模式")
    parser.add_argument("--hwnd", type=int, help="指定窗口句柄进行测试")
    parser.add_argument("--manager", action="store_true", help="测试 WindowManager 流程")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.list:
        list_all_windows()
    elif args.hwnd:
        test_hide_show_by_hwnd(args.hwnd)
    elif args.manager:
        test_manager_flow()
    elif args.auto:
        test_auto()
    else:
        parser.print_help()
        print("\n[提示] 推荐先运行 --list 查看可用窗口，再运行测试")


if __name__ == "__main__":
    main()
