# 一 显示 / 隐藏 操作规则

同一个 HWND：

### SW_SHOW 时能获取：

所有信息正常
IsWindowVisible = True
带 WS_VISIBLE
showCmd = SHOW

### SW_HIDE 时能获取：

**除了可见性状态，其他所有信息完全一样！**
IsWindowVisible = False
不带 WS_VISIBLE
showCmd = HIDE



# 最精简代码（直接复制用，速度最快）

```
import win32gui
import win32con

def fast_enum_top_windows():
    hwnd_list = []

    def callback(hwnd, extra):
        # ======================
        # 最快过滤层（必须按这个顺序！）
        # ======================
        if not win32gui.IsWindow(hwnd):          # 1. 无效句柄
            return True
        if not win32gui.IsWindowVisible(hwnd):   # 2. 隐藏窗口（最快）
            return True

        # 可选：过滤工具窗口、小悬浮窗（让结果更干净）
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        if not (style & win32con.WS_OVERLAPPEDWINDOW):
            return True

        # ======================
        # 到这里才是真正的顶层窗口
        # ======================
        hwnd_list.append(hwnd)
        return True

    # 一次性遍历所有顶层窗口（最快API）
    win32gui.EnumWindows(callback, None)
    return hwnd_list

# 使用
if __name__ == '__main__':
    top_windows = fast_enum_top_windows()
    print("有效顶层窗口数量：", len(top_windows))
```



1. 绝对不要在 callback 里做这些（会慢 10~100 倍）
GetWindowText（标题）
GetWindowRect（坐标）
GetWindowThreadProcessId（PID）
GetModuleFileNameEx（进程路径）
这些全部放到筛选完成后再做！
2. 只保留这 2 个判断，就是最快速度
python
运行
if not IsWindow(hwnd): continue
if not IsWindowVisible(hwnd): continue
这是Windows 能达到的最快顶层窗口筛选。
3. 如果你只要 “可见的真实主窗口”
加一行样式过滤即可，速度几乎不变：
python
运行
style = GetWindowLong(...)
if not (style & WS_VISIBLE) or not (style & WS_OVERLAPPEDWINDOW):
    continue
最终最快筛选口诀
EnumWindows 一遍过，
先判断有效、再判断可见，
样式过滤放中间，
标题类名 PID 最后做！



# 一 顶层窗口筛选规则

## 1 枚举系统所有**顶层窗口**pywin32: win32gui.EnumWindows 

**漏洞 / Bug 风险**：

- EnumWindows 会枚举**所有**顶层窗口，包括**看不见的、最小化到托盘、系统隐藏窗口、工具窗口**，必须靠后续过滤，不能直接用。
- 部分窗口**句柄有效但已销毁**，调用 API 会失败，必须加异常 / 空判断。

枚举**最顶层窗口**，不枚举子控件（按钮、输入框等），符合 “无父窗口” 的基础前提。



## 2对你定义的 “可见窗口” 做逐条严格校验

这是最关键的一步，必须全部满足才能进入可见窗口列表。
你定义的标准：
有标题
有最大化 / 最小化按钮
无父窗口（顶层）
Alt+Tab 可切换
任务栏（非托盘区）可见

### 子步骤 2.1：判断窗口是否可见

API：IsWindowVisible(hwnd)
必须返回 True。
漏洞：
最小化窗口也算 Visible，但你要的是 Alt+Tab 可见，所以不能只靠这个。

### 子步骤 2.2：判断窗口有标题

API：GetWindowTextLengthW + GetWindowTextW
标题长度 > 0 才算通过。
漏洞：
有些系统窗口标题为空，会被正确过滤；
部分窗口标题是空白字符（空格），你可能需要额外判断。

### 子步骤 2.3：判断窗口无父窗口（纯顶层）

API：GetParent(hwnd)
返回 0 或 NULL 才算无父窗口。
漏洞：
有些窗口是owned window（被拥有窗口），父窗口为空，但属于另一个窗口的从属窗口（比如输入法小窗口、悬浮条），这类也必须排除。
→ 解决方案：额外判断 GetWindowLongPtr 中是否带 WS_EX_APPWINDOW 样式。
子步骤 2.4：判断窗口有最大化、最小化按钮
API：GetWindowLongPtrW 获取窗口样式 GWL_STYLE
必须同时包含：
WS_MINIMIZEBOX
WS_MAXIMIZEBOX
漏洞：
有些窗口有按钮但被禁用，样式依然存在，会被误判；
无边框窗口（如部分新版软件）没有这两个样式，会被你排除（符合你的需求）。
子步骤 2.5：判断窗口 Alt+Tab 可切换 + 任务栏主图标可见
这是你需求里最容易写错的地方。
判断标准（Windows 官方规则）：
必须满足 两个条件同时成立：
窗口没有设置工具窗口属性：WS_EX_TOOLWINDOW = 不存在
窗口有应用窗口属性：WS_EX_APPWINDOW = 存在
满足这两条 = Alt+Tab 可见 + 任务栏主图标显示。
漏洞 / Bug 高危点：
只判断 “是否可见” 会把大量托盘窗口、悬浮窗加进来；
只判断 “是否顶层” 会把系统后台窗口加进来；
很多教程漏判 WS_EX_TOOLWINDOW，导致结果错误。
子步骤 2.6：最终过滤规则（必须全部满足）
一个窗口进入【可见窗口列表】的充要条件：
IsWindowVisible = True
标题长度 > 0
GetParent = 无父窗口
包含 WS_MINIMIZEBOX + WS_MAXIMIZEBOX
无 WS_EX_TOOLWINDOW
有 WS_EX_APPWINDOW
步骤 3：从可见窗口列表 → 每个进程取唯一 HWND
流程：
对每个通过校验的窗口，用 API 获取进程 ID：
GetWindowThreadProcessId(hwnd, &pid)
建立字典：key = pid, value = hwnd
规则：一个进程只存第一个遇到的 hwnd / 或只存主窗口
关键：如何保证 “一个进程有且只有一个 hwnd”？
你有两种安全策略：
方案 A（最简单、最稳定）
遍历顺序遇到第一个符合条件的窗口，就存入字典
后续同进程窗口直接跳过
→ 保证唯一，不会重复
方案 B（更精准，推荐）
同进程多个窗口时，优先选择：
窗口状态为 “正常 / 最大化”（非最小化）
窗口标题最像主窗口
窗口尺寸最大
→ 选出的 HWND 更符合 “主窗口” 直觉
三、全流程漏洞 & Bug 总清单（必须提前处理）
EnumWindows 会枚举无效 / 已销毁句柄 → 调用任何 API 前必须判断 IsWindow(hwnd)
最小化窗口会被判定为可见 → 不影响你的需求（Alt+Tab 最小化也能切）
部分进程有多个符合条件的窗口 → 必须用字典去重，只保留一个
工具窗口（WS_EX_TOOLWINDOW）会混入 → 必须强制排除
无边框窗口没有最大最小化按钮 → 会被你过滤（符合你的定义）
系统桌面窗口、Program Manager 窗口 → 会被枚举，必须靠样式过滤
UAC 权限问题 → 部分系统窗口需要管理员权限才能获取信息
→ 建议程序以管理员身份运行
Windows 特殊窗口（如设置、新版照片） 是 UWP 框架，句柄规则特殊，但依然符合 WS_EX_APPWINDOW，可以正常识别
四、最终输出结构
plaintext
{
  进程ID1: 主窗口HWND1,
  进程ID2: 主窗口HWND2,
  ...
}
保证：
所有 HWND 都来自你的【可见窗口列表】
一个进程 最多一个 HWND
完全符合你对 “顶层可见窗口” 的定义
总结
这套流程是Windows 平台筛选 “Alt+Tab / 任务栏可见主窗口” 的标准工业方案，我已经把你每一步可能踩的坑全部标出。
只要严格按这个判断逻辑走，就能100% 匹配你要的窗口，并且实现进程 ↔ 唯一 HWND。