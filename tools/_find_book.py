import sys
sys.path.insert(0, r"e:\my_project\01_已完成项目\windowmanager\tools")
from enum_windows import enum_top_windows, print_table

super_wins, visible_wins, stats = enum_top_windows()

# 过滤 book.exe 的窗口
book_windows = [w for w in super_wins if w["process_name"].lower() == "book.exe"]

print("=" * 80)
print("  book.exe 进程的所有窗口")
print("=" * 80)

if book_windows:
    print_table(book_windows)
else:
    print("\n  未找到 book.exe 进程或其窗口")
    print("\n  当前所有可见窗口进程:")
    seen = set()
    for w in visible_wins:
        if w["pid"] not in seen:
            seen.add(w["pid"])
            print(f"    {w['process_name']} (PID: {w['pid']})")
