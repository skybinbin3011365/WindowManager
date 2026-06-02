"""测试窗口显示恢复时不同参数的效果"""
import win32gui
import win32con
import win32process
import psutil
import time


def test_show_window(hwnd):
    """测试不同方式显示窗口的效果"""
    print("=" * 70)
    print(f"测试窗口显示恢复: hwnd = {hwnd}")
    print("=" * 70)

    # 1. 获取当前窗口状态
    print("\n[当前状态]")
    try:
        title = win32gui.GetWindowText(hwnd)
        rect = win32gui.GetWindowRect(hwnd)
        placement = win32gui.GetWindowPlacement(hwnd)
        print(f"  标题: {title}")
        print(f"  GetWindowRect: {rect}")
        print(f"  GetWindowPlacement: {placement}")
        width = rect[2] - rect[0]
        height = rect[3] - rect[1]
        print(f"  尺寸: {width}x{height}")
    except Exception as e:
        print(f"  获取失败: {e}")
        return

    input("\n按回车键测试 SW_RESTORE（不传递尺寸参数）...")
    
    # 2. 测试 SW_RESTORE
    print("\n[测试1: SW_RESTORE]")
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        time.sleep(0.5)
        rect = win32gui.GetWindowRect(hwnd)
        placement = win32gui.GetWindowPlacement(hwnd)
        print(f"  GetWindowRect: {rect}")
        print(f"  GetWindowPlacement: {placement}")
        width = rect[2] - rect[0]
        height = rect[3] - rect[1]
        print(f"  尺寸: {width}x{height}")
        print(f"  结果: {'✅ 窗口有尺寸' if width > 0 and height > 0 else '❌ 尺寸为 0'}")
    except Exception as e:
        print(f"  失败: {e}")

    input("\n按回车键测试 SW_SHOW（不传递尺寸参数）...")
    
    # 3. 测试 SW_SHOW
    print("\n[测试2: SW_SHOW]")
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
        time.sleep(0.5)
        rect = win32gui.GetWindowRect(hwnd)
        print(f"  GetWindowRect: {rect}")
        width = rect[2] - rect[0]
        height = rect[3] - rect[1]
        print(f"  尺寸: {width}x{height}")
        print(f"  结果: {'✅ 窗口有尺寸' if width > 0 and height > 0 else '❌ 尺寸为 0'}")
    except Exception as e:
        print(f"  失败: {e}")

    input("\n按回车键测试 SetWindowPos（使用固定尺寸 800x600）...")
    
    # 4. 测试 SetWindowPos 使用固定尺寸
    print("\n[测试3: SetWindowPos 800x600]")
    try:
        # 获取屏幕尺寸
        import ctypes
        user32 = ctypes.windll.user32
        screen_width = user32.GetSystemMetrics(0)
        screen_height = user32.GetSystemMetrics(1)
        
        # 设置窗口位置（屏幕居中，800x600）
        x = (screen_width - 800) // 2
        y = (screen_height - 600) // 2
        win32gui.SetWindowPos(hwnd, 0, x, y, 800, 600, win32con.SWP_NOZORDER | win32con.SWP_SHOWWINDOW)
        time.sleep(0.5)
        rect = win32gui.GetWindowRect(hwnd)
        print(f"  设置位置: x={x}, y={y}, 800x600")
        print(f"  GetWindowRect: {rect}")
        width = rect[2] - rect[0]
        height = rect[3] - rect[1]
        print(f"  尺寸: {width}x{height}")
        print(f"  结果: {'✅ 窗口有尺寸' if width > 0 and height > 0 else '❌ 尺寸为 0'}")
    except Exception as e:
        print(f"  失败: {e}")

    print("\n" + "=" * 70)
    print("结论:")
    print("=" * 70)
    print("1. SW_RESTORE 和 SW_SHOW 是否能让窗口恢复有效尺寸？")
    print("2. SetWindowPos 是否能强制设置窗口尺寸？")
    print("3. 窗口尺寸参数是否是必需的？")
    print("=" * 70)


def main():
    print("输入要测试的窗口 hwnd:")
    hwnd = int(input("> ").strip())
    test_show_window(hwnd)


if __name__ == "__main__":
    main()
