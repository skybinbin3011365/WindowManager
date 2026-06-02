
import win32gui
import win32con
import win32process
import sys
import argparse

def bring_window_to_front(hwnd):
    """
    将指定窗口显示到前台

    参数:
        hwnd: 窗口句柄
    """
    # 检查窗口是否有效
    if not win32gui.IsWindow(hwnd):
        print(f"错误: 窗口句柄 {hwnd} 无效")
        return False

    # 获取窗口标题，用于显示
    title = win32gui.GetWindowText(hwnd)

    # 将窗口设置为前台显示
    try:
        # 恢复窗口（如果最小化）
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

        # 将窗口置于前台
        win32gui.SetForegroundWindow(hwnd)

        # 强制重绘窗口
        win32gui.RedrawWindow(hwnd, None, None, 
                             win32con.RDW_INVALIDATE | win32con.RDW_UPDATENOW | win32con.RDW_ALLCHILDREN)

        print(f"已将窗口 '{title}' (HWND: {hwnd}) 显示到前台")
        return True
    except Exception as e:
        print(f"显示窗口时出错: {e}")
        return False

def main():
    # 设置命令行参数解析
    parser = argparse.ArgumentParser(description='将指定窗口显示到前台')
    parser.add_argument('hwnd', type=int, help='要显示的窗口句柄')

    # 解析参数
    args = parser.parse_args()
    hwnd = args.hwnd

    # 显示窗口
    bring_window_to_front(hwnd)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使用方法: show_window.py <hwnd>")
        print("示例: show_window.py 13406")
        sys.exit(1)

    main()
