
import win32gui
import win32con
import win32process
import psutil
import sys

hwnd = 14028408

print("=" * 70)
print("  Diag HWND = {}".format(hwnd))
print("=" * 70)

# 1. IsWindow
is_valid = win32gui.IsWindow(hwnd)
print("  IsWindow:              {}".format(is_valid))

if not is_valid:
    print("  invalid hwnd, exit")
    sys.exit(1)

# 2. IsWindowVisible
is_visible = win32gui.IsWindowVisible(hwnd)
print("  IsWindowVisible:       {}".format(is_visible))

# 3. Style
style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
print("  Style (hex):           0x{:08X}".format(style))
print("  ExStyle (hex):         0x{:08X}".format(ex_style))

# 逐项检查
print("")
print("  --- Style flags ---")
checks = [
    ("WS_OVERLAPPED",        win32con.WS_OVERLAPPED),
    ("WS_POPUP",             win32con.WS_POPUP),
    ("WS_CHILD",             win32con.WS_CHILD),
    ("WS_MINIMIZE",          win32con.WS_MINIMIZE),
    ("WS_VISIBLE",           win32con.WS_VISIBLE),
    ("WS_DISABLED",          win32con.WS_DISABLED),
    ("WS_CLIPSIBLINGS",      win32con.WS_CLIPSIBLINGS),
    ("WS_CLIPCHILDREN",      win32con.WS_CLIPCHILDREN),
    ("WS_MAXIMIZE",          win32con.WS_MAXIMIZE),
    ("WS_BORDER",            win32con.WS_BORDER),
    ("WS_DLGFRAME",          win32con.WS_DLGFRAME),
    ("WS_THICKFRAME",        win32con.WS_THICKFRAME),
    ("WS_SYSMENU",           win32con.WS_SYSMENU),
    ("WS_MINIMIZEBOX",       win32con.WS_MINIMIZEBOX),
    ("WS_MAXIMIZEBOX",       win32con.WS_MAXIMIZEBOX),
    ("WS_OVERLAPPEDWINDOW",  win32con.WS_OVERLAPPEDWINDOW),
]
for name, flag in checks:
    has = bool(style & flag)
    mark = "[Y]" if has else "[N]"
    print("  {} {:<24} {}".format(mark, name, has))

print("")
print("  --- ExStyle flags ---")
ex_checks = [
    ("WS_EX_TOOLWINDOW",     win32con.WS_EX_TOOLWINDOW),
    ("WS_EX_APPWINDOW",      win32con.WS_EX_APPWINDOW),
    ("WS_EX_TOPMOST",        win32con.WS_EX_TOPMOST),
    ("WS_EX_LAYERED",        win32con.WS_EX_LAYERED),
]
for name, flag in ex_checks:
    has = bool(ex_style & flag)
    mark = "[Y]" if has else "[N]"
    print("  {} {:<24} {}".format(mark, name, has))

# 4. Owner
owner = win32gui.GetWindow(hwnd, win32con.GW_OWNER)
owner_info = "(no owner OK)" if not owner else "(has owner -> filtered by child check)"
print("")
print("  Owner HWND:            {} {}".format(owner, owner_info))

# 5. Title
title = win32gui.GetWindowText(hwnd)
title_info = "(non-empty OK)" if title else "(empty FAIL)"
print("  Title:                 '{}' {}".format(title, title_info))

# 6. Size
width, height = 0, 0
try:
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width, height = right - left, bottom - top
    size_info = "(non-zero OK)" if width > 0 and height > 0 else "(zero FAIL)"
    print("  Rect:                  ({},{})-({},{})".format(left, top, right, bottom))
    print("  Size:                  {}x{} {}".format(width, height, size_info))
except Exception as e:
    print("  GetWindowRect FAIL:    {}".format(e))

# 7. Class & Process
class_name = win32gui.GetClassName(hwnd)
_, pid = win32process.GetWindowThreadProcessId(hwnd)
try:
    proc_name = psutil.Process(pid).name()
except Exception:
    proc_name = "<unknown>"
print("  ClassName:             {}".format(class_name))
print("  PID:                   {}".format(pid))
print("  Process:               {}".format(proc_name))

# 8. Diagnosis
print("")
print("=" * 70)
print("  DIAGNOSIS: which filter excluded this window?")
print("=" * 70)

if not is_valid:
    print("  FAIL: IsWindow invalid")
elif ex_style & win32con.WS_EX_TOOLWINDOW:
    print("  FAIL: WS_EX_TOOLWINDOW (priority 1)")
elif owner:
    print("  FAIL: has Owner (HWND={}) -> child filter".format(owner))
elif not (style & win32con.WS_OVERLAPPEDWINDOW) and not (ex_style & win32con.WS_EX_APPWINDOW):
    print("  FAIL: neither WS_OVERLAPPEDWINDOW nor WS_EX_APPWINDOW")
elif (style & win32con.WS_OVERLAPPEDWINDOW) and not (style & win32con.WS_MINIMIZEBOX):
    print("  FAIL: missing WS_MINIMIZEBOX")
elif (style & win32con.WS_OVERLAPPEDWINDOW) and not (style & win32con.WS_MAXIMIZEBOX):
    print("  FAIL: missing WS_MAXIMIZEBOX")
elif (style & win32con.WS_OVERLAPPEDWINDOW) and (style & win32con.WS_POPUP):
    print("  FAIL: WS_POPUP")
elif not title:
    print("  FAIL: empty title")
elif width <= 0 or height <= 0:
    print("  FAIL: zero size")
else:
    print("  PASS: should pass all filters! Check other issues.")
