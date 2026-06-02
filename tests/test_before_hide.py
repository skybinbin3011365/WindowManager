"""测试窗口在隐藏前的状态"""
import win32gui
import win32con
import win32process
import psutil


def test_window_before_hide(hwnd):
    """测试窗口在隐藏前的各种状态信息"""
    print("=" * 70)
    print(f"测试窗口隐藏前的状态: hwnd = {hwnd}")
    print("=" * 70)

    # 1. 获取窗口标题和进程信息
    try:
        title = win32gui.GetWindowText(hwnd)
        class_name = win32gui.GetClassName(hwnd)
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        proc = psutil.Process(pid)
        print(f"\n窗口信息:")
        print(f"  标题: {title}")
        print(f"  类名: {class_name}")
        print(f"  进程: {proc.name()} (PID: {pid})")
    except Exception as e:
        print(f"获取窗口信息失败: {e}")

    # 2. 获取 GetWindowPlacement
    print(f"\nGetWindowPlacement 结果:")
    try:
        placement = win32gui.GetWindowPlacement(hwnd)
        flags, show_cmd, pt_min_pos, pt_max_pos, rc_normal = placement
        
        show_cmd_names = {
            0: "SW_HIDE", 1: "SW_SHOWNORMAL", 2: "SW_SHOWMINIMIZED",
            3: "SW_SHOWMAXIMIZED", 5: "SW_SHOW", 9: "SW_RESTORE",
        }
        print(f"  flags: {flags}")
        print(f"  showCmd: {show_cmd} ({show_cmd_names.get(show_cmd, 'Unknown')})")
        print(f"  ptMinPosition: {pt_min_pos}")
        print(f"  ptMaxPosition: {pt_max_pos}")
        print(f"  rcNormalPosition: {rc_normal}")
        
        normal_width = rc_normal[2] - rc_normal[0]
        normal_height = rc_normal[3] - rc_normal[1]
        print(f"  正常尺寸: width={normal_width}, height={normal_height}")
        
        if normal_width == 0 or normal_height == 0:
            print(f"  ⚠️ 警告：rcNormalPosition 尺寸为 0！")
    except Exception as e:
        print(f"  获取失败: {e}")

    # 3. 获取 GetWindowRect
    print(f"\nGetWindowRect 结果:")
    try:
        rect = win32gui.GetWindowRect(hwnd)
        width = rect[2] - rect[0]
        height = rect[3] - rect[1]
        print(f"  矩形: left={rect[0]}, top={rect[1]}, right={rect[2]}, bottom={rect[3]}")
        print(f"  尺寸: width={width}, height={height}")
        
        if width == 0 or height == 0:
            print(f"  ❌ 窗口当前尺寸为 0x0！")
        else:
            print(f"  ✅ 窗口有有效尺寸")
    except Exception as e:
        print(f"  获取失败: {e}")

    # 4. 获取窗口样式
    print(f"\n窗口样式:")
    try:
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        print(f"  GWL_STYLE: 0x{style:08X}")
        print(f"  WS_VISIBLE: {bool(style & win32con.WS_VISIBLE)}")
        print(f"  WS_MINIMIZE: {bool(style & win32con.WS_MINIMIZE)}")
        print(f"  WS_MAXIMIZE: {bool(style & win32con.WS_MAXIMIZE)}")
    except Exception as e:
        print(f"  获取失败: {e}")

    # 5. 结论
    print(f"\n{'=' * 70}")
    print("结论:")
    print("=" * 70)
    print("1. 如果 GetWindowPlacement 的 rcNormalPosition 尺寸为 0")
    print("2. 但 GetWindowRect 有有效尺寸")
    print("3. 则需要在隐藏前补充保存 GetWindowRect 的尺寸")
    print("4. 显示时使用这个尺寸来设置窗口位置")
    print("=" * 70)


def main():
    print("输入要测试的窗口 hwnd（直接回车自动查找读书巴士）:")
    user_input = input("> ").strip()

    if user_input:
        hwnd = int(user_input)
        test_window_before_hide(hwnd)
    else:
        print("\n查找读书巴士窗口...")
        for proc in psutil.process_iter(["name"]):
            if proc.info["name"].lower() == "book.exe":
                pid = proc.info["pid"]
                print(f"找到进程: {proc.info['name']} (PID: {pid})")

                def enum_callback(hwnd, _):
                    try:
                        _, window_pid = win32process.GetWindowThreadProcessId(hwnd)
                        if window_pid == pid:
                            title = win32gui.GetWindowText(hwnd)
                            if title:
                                print(f"\n找到窗口: hwnd={hwnd}, 标题='{title}'")
                                test_window_before_hide(hwnd)
                    except Exception:
                        pass
                    return True

                win32gui.EnumWindows(enum_callback, None)


if __name__ == "__main__":
    main()
