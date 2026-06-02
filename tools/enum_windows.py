
"""
Windows 顶层窗口枚举工具 — 超级窗口 + 可见主应用窗口

超级窗口定义（任务栏显示条件优先级）:
  优先级1: WS_EX_TOOLWINDOW → ❌ 不显示（工具窗口，最高优先级排除）
  优先级2: 顶层窗口 + 可见 → ✅ 默认显示
  优先级3: 子窗口(有owner) → ❌ 默认不显示（但 WS_EX_APPWINDOW 例外 ✅）

  附加条件:
  - WS_OVERLAPPEDWINDOW（主应用窗口样式）
  - 必须包含 WS_MINIMIZEBOX + WS_MAXIMIZEBOX
  - 必须不是 WS_POPUP
  - 标题非空
  - 尺寸非 0x0
  - 可见主应用窗口 ⊆ 超级窗口

过滤链:
  第1步: 句柄判断 — IsWindow（最快）
  第2步: 样式判断 — TOOLWINDOW(优先级1) → 子窗口(优先级3) → OVERLAPPEDWINDOW + MINBTN + MAXBTN + 非POPUP（极快）
  第3步: 标题+尺寸判断 — GetWindowText 非空 + GetWindowRect 非0x0（仅候选窗口）

输出:
  - 超级窗口：满足全部条件（含隐藏+可见）
  - 可见主应用窗口：超级窗口中当前可见的子集
"""

import win32gui
import win32con
import win32process
import psutil


def enum_top_windows():
    """枚举所有顶层窗口，筛选超级窗口

    超级窗口 = 满足以下全部条件的顶层窗口:
      - IsWindow 有效
      - WS_OVERLAPPEDWINDOW（主应用窗口样式）
      - 非 WS_EX_TOOLWINDOW（非工具窗口）
      - 标题非空
      - 尺寸非 0x0
      - 可见或隐藏均可

    可见主应用窗口 = 超级窗口 ∩ 当前可见
    """

    # 回调内收集候选 hwnd
    candidate_hwnds = []  # 通过快过滤的候选（含隐藏+可见）
    tool_hwnds = []       # 工具窗口（仅统计）

    stats = {"total": 0, "invalid": 0, "hidden": 0, "tool": 0, "child": 0,
             "no_btn": 0, "popup": 0, "no_title": 0, "zero_size": 0, "candidate": 0}

    def callback(hwnd, _extra):
        stats["total"] += 1

        # ═══ 第1步：句柄判断（最快）═══
        if not win32gui.IsWindow(hwnd):
            stats["invalid"] += 1
            return True

        is_visible = win32gui.IsWindowVisible(hwnd)
        if not is_visible:
            stats["hidden"] += 1  # 统计但不跳过，隐藏窗口也可能是超级窗口

        # ═══ 第2步：样式判断（极快）═══
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)

        # 优先级1: WS_EX_TOOLWINDOW → 不显示（工具窗口，最高优先级排除）
        if ex_style & win32con.WS_EX_TOOLWINDOW:
            stats["tool"] += 1
            tool_hwnds.append(hwnd)
            return True

        # 优先级3: 子窗口 → 默认不显示（非顶层窗口）
        # 但 WS_EX_APPWINDOW 窗口即使有 owner 也应显示在任务栏
        owner = win32gui.GetWindow(hwnd, win32con.GW_OWNER)
        has_appwindow = ex_style & win32con.WS_EX_APPWINDOW
        if owner and not has_appwindow:
            stats["child"] += 1
            return True

        # 必须是 WS_OVERLAPPEDWINDOW 或 WS_EX_APPWINDOW（主应用窗口样式）
        has_overlapped = style & win32con.WS_OVERLAPPEDWINDOW
        has_appwindow = ex_style & win32con.WS_EX_APPWINDOW
        if not has_overlapped and not has_appwindow:
            stats["tool"] += 1
            tool_hwnds.append(hwnd)
            return True

        # 必须包含最小化按钮 + 最大化按钮（主应用窗口特征）
        # 对于 WS_EX_APPWINDOW 窗口，放宽此要求
        if has_overlapped and (not (style & win32con.WS_MINIMIZEBOX) or not (style & win32con.WS_MAXIMIZEBOX)):
            stats["no_btn"] += 1
            return True

        # 必须不是 WS_POPUP（排除弹出窗口）
        # 对于 WS_EX_APPWINDOW 窗口，放宽此要求
        if has_overlapped and (style & win32con.WS_POPUP):
            stats["popup"] += 1
            return True

        # ═══ 第3步：标题+尺寸判断（仅候选窗口）═══
        title = win32gui.GetWindowText(hwnd)
        if not title:
            stats["no_title"] += 1
            return True

        # 尺寸非 0x0
        try:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            width, height = right - left, bottom - top
            if width <= 0 or height <= 0:
                stats["zero_size"] += 1
                return True
        except Exception:
            stats["zero_size"] += 1
            return True

        # ═══ 通过全部过滤 → 超级窗口候选 ═══
        stats["candidate"] += 1
        candidate_hwnds.append(hwnd)
        return True

    # 一次性遍历所有顶层窗口
    win32gui.EnumWindows(callback, None)

    # ── 一次性构建 PID→进程名 缓存 ──
    pid_name_map = {}
    try:
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                pid_name_map[proc.info["pid"]] = proc.info["name"]
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception:
        pass

    # ── 回调结束后，补充详细信息 ──
    super_windows = [_get_window_info(h, pid_name_map) for h in candidate_hwnds]

    # 可见主应用窗口 = 超级窗口中当前可见的子集
    visible_app_windows = [w for w in super_windows if "VIS" in w["style_flags"]]

    return super_windows, visible_app_windows, stats


def _get_window_info(hwnd, pid_name_map=None):
    """获取窗口详细信息

    pid_name_map: 预构建的 PID→进程名 缓存，避免逐个创建 psutil.Process
    """
    title = win32gui.GetWindowText(hwnd)
    class_name = win32gui.GetClassName(hwnd)
    _, pid = win32process.GetWindowThreadProcessId(hwnd)

    # 进程名（从缓存获取，O(1)）
    if pid_name_map and pid in pid_name_map:
        process_name = pid_name_map[pid]
    elif pid > 0:
        # 缓存未命中，回退到单次查询
        try:
            process_name = psutil.Process(pid).name()
        except psutil.NoSuchProcess:
            process_name = "<exited>"
        except psutil.AccessDenied:
            process_name = "<denied>"
        except Exception:
            process_name = "<error>"
    else:
        process_name = "<system>"

    # 窗口尺寸
    try:
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        width, height = right - left, bottom - top
    except Exception:
        width, height = 0, 0

    # 样式标志
    style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
    ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)

    flags = []
    if style & win32con.WS_VISIBLE:      flags.append("VIS")
    if style & win32con.WS_DISABLED:     flags.append("DIS")
    if style & win32con.WS_POPUP:        flags.append("POPUP")
    if style & win32con.WS_MINIMIZE:     flags.append("MIN")
    if style & win32con.WS_MAXIMIZE:     flags.append("MAX")
    if style & win32con.WS_THICKFRAME:   flags.append("THICK")
    if style & win32con.WS_SYSMENU:      flags.append("SYS")
    if style & win32con.WS_MINIMIZEBOX:  flags.append("MINBTN")
    if style & win32con.WS_MAXIMIZEBOX:  flags.append("MAXBTN")
    if ex_style & win32con.WS_EX_TOOLWINDOW: flags.append("TOOL")
    if ex_style & win32con.WS_EX_TOPMOST:    flags.append("TOP")
    if ex_style & win32con.WS_EX_LAYERED:    flags.append("LAYER")

    return {
        "hwnd": hwnd,
        "title": title,
        "class_name": class_name,
        "pid": pid,
        "process_name": process_name,
        "width": width,
        "height": height,
        "style_flags": "|".join(flags) if flags else "-",
    }


def print_table(windows):
    """打印窗口表格"""
    if not windows:
        print("\n  （无）")
        return

    # 按 PID 排序
    windows = sorted(windows, key=lambda w: (w["pid"], w["title"].lower()))

    # 动态列宽
    max_title = min(max((len(w["title"]) for w in windows), default=0), 45)
    max_class = min(max((len(w["class_name"]) for w in windows), default=0), 26)
    max_proc  = min(max((len(w["process_name"]) for w in windows), default=0), 18)

    hdr = f"  {'HWND':<8} {'PID':<7} {'状态':<4} {'进程':<{max_proc}} {'标题':<{max_title}} {'类名':<{max_class}} {'尺寸':<10} {'样式'}"
    print(hdr)
    print("  " + "─" * (len(hdr) - 2))

    for w in windows:
        t = w["title"][:max_title]
        c = w["class_name"][:max_class]
        p = w["process_name"][:max_proc]
        size = f"{w['width']}x{w['height']}"
        vis = "可见" if "VIS" in w["style_flags"] else "隐藏"
        print(f"  {w['hwnd']:<8} {w['pid']:<7} {vis:<4} {p:<{max_proc}} {t:<{max_title}} {c:<{max_class}} {size:<10} {w['style_flags']}")


def analyze_pid_duplicates(windows):
    """分析 PID 去重（one-VW-per-PID）"""
    pid_map = {}
    for w in windows:
        pid_map.setdefault(w["pid"], []).append(w)

    multi = {pid: wins for pid, wins in pid_map.items() if len(wins) > 1}
    if multi:
        print(f"\n  ⚠️  发现 {len(multi)} 个进程有多个可见顶层窗口:")
        for pid, wins in sorted(multi.items()):
            print(f"\n  PID={pid} ({wins[0]['process_name']}) — {len(wins)} 个窗口:")
            for w in wins:
                print(f"    HWND={w['hwnd']:<8} \"{w['title']}\"  {w['class_name']}  {w['width']}x{w['height']}  {w['style_flags']}")
    else:
        print(f"\n  ✅ 所有可见窗口均满足 one-VW-per-PID（无重复PID）")

    print(f"\n  可见窗口: {len(windows)} 个, 涉及进程: {len(pid_map)} 个")


def main():
    print("=" * 90)
    print("  Windows 顶层窗口枚举工具 — 超级窗口 + 可见主应用窗口")
    print("  过滤链: 句柄 → 样式(WS_OVERLAPPEDWINDOW+非TOOLWINDOW) → 标题+尺寸")
    print("=" * 90)

    super_wins, visible_wins, stats = enum_top_windows()

    # ── 过滤统计 ──
    print(f"\n{'─' * 90}")
    print(f"  📊 过滤统计")
    print(f"{'─' * 90}")
    print(f"  EnumWindows 回调总数:     {stats['total']}")
    print(f"  第1步 过滤（句柄判断）:")
    print(f"    无效句柄:               {stats['invalid']}")
    print(f"    隐藏窗口:               {stats['hidden']}（仍参与后续过滤）")
    print(f"  第2步 过滤（样式判断，按优先级）:")
    print(f"    WS_EX_TOOLWINDOW(优先级1): {stats['tool']}")
    print(f"    子窗口/有owner(优先级3):   {stats['child']}")
    print(f"    非OVERLAPPEDWINDOW:       {stats['tool']}")
    print(f"    缺少最小化/最大化按钮:     {stats['no_btn']}")
    print(f"    WS_POPUP弹出窗口:         {stats['popup']}")
    print(f"  第3步 过滤（标题+尺寸）:")
    print(f"    无标题窗口:             {stats['no_title']}")
    print(f"    零尺寸窗口:             {stats['zero_size']}")
    print(f"  ────────────────────────")
    print(f"  🌟 超级窗口:              {stats['candidate']}")
    print(f"  ✅ 可见主应用窗口:         {len(visible_wins)}")

    # ── 1. 超级窗口（含隐藏+可见）──
    print(f"\n{'═' * 90}")
    hidden_count = len([w for w in super_wins if "VIS" not in w["style_flags"]])
    print(f"  🌟 超级窗口 ({len(super_wins)} 个, 其中 {hidden_count} 个隐藏)")
    print(f"{'═' * 90}")
    print_table(super_wins)

    # ── 2. 可见主应用窗口 ──
    print(f"\n{'═' * 90}")
    print(f"  ✅ 可见主应用窗口 ({len(visible_wins)} 个)")
    print(f"{'═' * 90}")
    print_table(visible_wins)

    # ── 3. PID 去重分析 ──
    print(f"\n{'═' * 90}")
    print(f"  🔍 PID 去重分析 (one-VW-per-PID)")
    print(f"{'═' * 90}")
    analyze_pid_duplicates(visible_wins)

    print(f"\n{'═' * 90}")
    print(f"  枚举完成")
    print(f"{'═' * 90}")


if __name__ == "__main__":
    main()
