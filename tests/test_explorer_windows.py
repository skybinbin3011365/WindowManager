"""测试脚本：检测 explorer.exe 进程的窗口状态

用于排查切换窗口列表中 explorer.exe 窗口匹配问题
"""
import win32gui
import win32process
import win32con
import psutil


def enum_windows_callback(hwnd, windows):
    """枚举所有窗口的回调函数"""
    try:
        # 获取窗口标题
        title = win32gui.GetWindowText(hwnd)
        
        # 跳过无标题窗口
        if not title.strip():
            return True
            
        # 获取进程ID
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        
        # 获取进程名
        try:
            proc = psutil.Process(pid)
            process_name = proc.name()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            process_name = "unknown"
        
        # 只检查 explorer.exe
        if process_name.lower() != "explorer.exe":
            return True
        
        # 检查是否为顶层窗口
        parent = win32gui.GetParent(hwnd)
        
        # 检查是否可见
        is_visible = win32gui.IsWindowVisible(hwnd)
        
        # 检查窗口样式
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        has_minimize = bool(style & win32con.WS_MINIMIZEBOX)
        has_maximize = bool(style & win32con.WS_MAXIMIZEBOX)
        
        # 判断 is_taskbar（VW 窗口条件）
        is_taskbar = (
            parent == 0 and
            title.strip() != "" and
            has_minimize and
            has_maximize and
            is_visible
        )
        
        # 打印窗口信息
        print(f"\n{'='*60}")
        print(f"hwnd: {hwnd}")
        print(f"标题: {title}")
        print(f"进程: {process_name} (PID: {pid})")
        print(f"是否为顶层窗口 (GetParent==0): {parent == 0}")
        print(f"是否可见 (IsWindowVisible): {is_visible}")
        print(f"有最小化按钮 (WS_MINIMIZEBOX): {has_minimize}")
        print(f"有最大化按钮 (WS_MAXIMIZEBOX): {has_maximize}")
        print(f"is_taskbar (VW判定): {is_taskbar}")
        print(f"{'='*60}")
        
        windows.append({
            "hwnd": hwnd,
            "title": title,
            "process_name": process_name,
            "pid": pid,
            "is_top_level": parent == 0,
            "is_visible": is_visible,
            "has_minimize": has_minimize,
            "has_maximize": has_maximize,
            "is_taskbar": is_taskbar,
        })
        
    except Exception as e:
        print(f"处理窗口 {hwnd} 时出错: {e}")
    
    return True


def main():
    """主函数"""
    print("="*60)
    print("检测 explorer.exe 进程的所有窗口")
    print("="*60)
    
    windows = []
    win32gui.EnumWindows(enum_windows_callback, windows)
    
    print(f"\n\n{'#'*60}")
    print(f"总结：找到 {len(windows)} 个 explorer.exe 窗口")
    print(f"{'#'*60}")
    
    # 按 is_taskbar 分组
    taskbar_windows = [w for w in windows if w["is_taskbar"]]
    non_taskbar_windows = [w for w in windows if not w["is_taskbar"]]
    
    print(f"\n✅ is_taskbar=True (VW 窗口): {len(taskbar_windows)} 个")
    for w in taskbar_windows:
        print(f"   hwnd={w['hwnd']}, title='{w['title']}'")
    
    print(f"\n❌ is_taskbar=False (非 VW 窗口): {len(non_taskbar_windows)} 个")
    for w in non_taskbar_windows:
        print(f"   hwnd={w['hwnd']}, title='{w['title']}'")
        print(f"      - 顶层窗口: {w['is_top_level']}")
        print(f"      - 可见: {w['is_visible']}")
        print(f"      - 最小化按钮: {w['has_minimize']}")
        print(f"      - 最大化按钮: {w['has_maximize']}")
    
    print(f"\n{'#'*60}")
    print("如果需要添加到切换窗口，应选择 is_taskbar=True 的窗口")
    print(f"{'#'*60}")


if __name__ == "__main__":
    main()
