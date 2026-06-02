
import win32gui
import win32con

hwnd = 14028408

# GW_OWNER
owner = win32gui.GetWindow(hwnd, win32con.GW_OWNER)
print("GW_OWNER:  {}".format(owner))

# GetParent
parent = win32gui.GetParent(hwnd)
print("GetParent: {}".format(parent))

# 额外信息：owner/parent 的类名和标题
for label, h in [("Owner", owner), ("Parent", parent)]:
    if h:
        try:
            cn = win32gui.GetClassName(h)
            title = win32gui.GetWindowText(h)
            style = win32gui.GetWindowLong(h, win32con.GWL_STYLE)
            ex_style = win32gui.GetWindowLong(h, win32con.GWL_EXSTYLE)
            print("  {} HWND={} class='{}' title='{}' style=0x{:08X} exstyle=0x{:08X}".format(
                label, h, cn, title, style, ex_style))
        except Exception as e:
            print("  {} HWND={} error: {}".format(label, h, e))
    else:
        print("  {} HWND=0 (none)".format(label))
