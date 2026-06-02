"""测试脚本：检测指定 hwnd 的窗口状态

用于排查显示窗口功能失效问题
"""
import win32gui
import win32con
import win32process
import psutil


def check_window_state(hwnd):
    """检查指定 hwnd 的窗口状态"""
    print("=" * 60)
    print(f"检查窗口状态: hwnd = {hwnd}")
    print("=" * 60)

    # 检查窗口句柄是否有效
    is_valid = win32gui.IsWindow(hwnd)
    print(f"窗口句柄是否有效 (IsWindow): {is_valid}")

    if not is_valid:
        print("窗口句柄无效，无法继续检查")
        return

    # 检查窗口是否可见
    is_visible = win32gui.IsWindowVisible(hwnd)
    print(f"窗口是否可见 (IsWindowVisible): {is_visible}")

    # 获取窗口样式
    style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
    is_minimized = bool(style & win32con.WS_MINIMIZE)
    is_maximized = bool(style & win32con.WS_MAXIMIZE)
    print(f"窗口是否最小化 (WS_MINIMIZE): {is_minimized}")
    print(f"窗口是否最大化 (WS_MAXIMIZE): {is_maximized}")

    # 获取窗口放置信息
    try:
        placement = win32gui.GetWindowPlacement(hwnd)
        show_cmd = placement[1]  # showCmd
        show_cmd_names = {
            0: "SW_HIDE",
            1: "SW_SHOWNORMAL",
            2: "SW_SHOWMINIMIZED",
            3: "SW_SHOWMAXIMIZED",
            4: "SW_SHOWNOACTIVATE",
            5: "SW_SHOW",
            6: "SW_MINIMIZE",
            7: "SW_SHOWMINNOACTIVE",
            8: "SW_SHOWNA",
            9: "SW_RESTORE",
            10: "SW_SHOWDEFAULT",
            11: "SW_FORCEMINIMIZE",
        }
        print(f"窗口放置状态 (showCmd): {show_cmd_names.get(show_cmd, f'Unknown({show_cmd})')}")
    except Exception as e:
        print(f"获取窗口放置信息失败: {e}")

    # 获取窗口标题
    try:
        title = win32gui.GetWindowText(hwnd)
        print(f"窗口标题: {title}")
    except Exception as e:
        print(f"获取窗口标题失败: {e}")

    # 获取进程信息
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        proc = psutil.Process(pid)
        print(f"进程名: {proc.name()} (PID: {pid})")
    except Exception as e:
        print(f"获取进程信息失败: {e}")

    # 检查父窗口
    try:
        parent = win32gui.GetParent(hwnd)
        print(f"父窗口 hwnd: {parent}")
        print(f"是否为顶层窗口: {parent == 0}")
    except Exception as e:
        print(f"获取父窗口失败: {e}")

    # 检查窗口矩形区域
    try:
        rect = win32gui.GetWindowRect(hwnd)
        print(f"窗口矩形: left={rect[0]}, top={rect[1]}, right={rect[2]}, bottom={rect[3]}")
        print(f"窗口大小: width={rect[2]-rect[0]}, height={rect[3]-rect[1]}")
    except Exception as e:
        print(f"获取窗口矩形失败: {e}")

    print("\n" + "=" * 60)
    print("结论:")
    if is_visible:
        print("✅ 窗口当前是可见的")
    else:
        print("❌ 窗口当前是隐藏的")
    print("=" * 60)


def main():
    """主函数"""
    print("请输入要检查的窗口 hwnd（直接回车检查所有 book.exe 的窗口）:")
    user_input = input("> ").strip()

    if user_input:
        try:
            hwnd = int(user_input)
            check_window_state(hwnd)
        except ValueError:
            print(f"无效的 hwnd: {user_input}")
    else:
        # 查找所有 book.exe 的窗口
        print("\n查找所有 book.exe 进程的窗口...")
        found_windows = []

        for proc in psutil.process_iter(["name", "pid"]):
            if proc.info["name"].lower() == "book.exe":
                pid = proc.info["pid"]
                print(f"找到进程: book.exe (PID: {pid})")

                # 枚举该进程的所有窗口
                def enum_callback(hwnd, _):
                    try:
                        _, window_pid = win32process.GetWindowThreadProcessId(hwnd)
                        if window_pid == pid:
                            title = win32gui.GetWindowText(hwnd)
                            is_visible = win32gui.IsWindowVisible(hwnd)
                            found_windows.append({
                                "hwnd": hwnd,
                                "title": title,
                                "is_visible": is_visible,
                            })
                    except Exception:
                        pass
                    return True

                win32gui.EnumWindows(enum_callback, None)

        if found_windows:
            print(f"\n找到 {len(found_windows)} 个窗口:")
            for i, win in enumerate(found_windows, 1):
                print(f"\n--- 窗口 {i} ---")
                check_window_state(win["hwnd"])
        else:
            print("未找到 book.exe 的任何窗口")


if __name__ == "__main__":
    main()
