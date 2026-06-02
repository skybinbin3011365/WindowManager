# 一套通用、稳定、覆盖三种场景、永不失效的综合方案

这是做窗口显示 / 隐藏工具的行业标准逻辑，专门解决：
软件先启动 / 进程先启动
软件崩溃退出后，窗口依然隐藏
精准找到任务栏可见窗口（以下简称：VW）
只操作顶层窗口，不碰子窗口
隐藏 / 显示完全无损恢复
我直接给你完整逻辑架构 + 可落地代码框架，你照着做就能 100% 解决问题。

## 一、综合方案核心思想（超级简单）

一句话总逻辑
永远只对【进程对应的 唯一顶层主窗口】操作，不管它当前是否可见、不管软件怎么重启。
三大铁律（你必须遵守）
不依赖窗口可见性找窗口（否则场景 3 找不到）
不操作子窗口（系统自动继承可见性）
隐藏 = 只隐藏顶层窗口，显示 = 只恢复顶层窗口

## 二、综合方案：统一逻辑规划（三种场景全覆盖）

### 步骤 1：定义什么是【任务栏可见窗口 VW】

你只需要认这4 个条件，满足就是用户看到的主窗口：
是顶层窗口（无父窗口：GetParent(hwnd) == 0）
属于目标进程（book.exe）
有窗口标题（非空）
是标准窗口样式（带 WS_VISIBLE 或WS_MINIMIZEBOX及WS_MAXIMIZEBOX或曾经可见）
→ 满足这 4 条，100% 就是你要操作的那个窗口
→ 不管它当前显示还是隐藏，都能找到！

### 步骤 2：统一窗口查找逻辑（所有场景共用）

不管是场景 1/2/3，找窗口的代码完全一样：
枚举所有顶层窗口
过滤：属于 book.exe
过滤：无父窗口（顶层）
过滤：标题不为空
剩下的唯一一个窗口，就是 VW

### 步骤 3：统一隐藏逻辑

plaintext
隐藏(VW窗口)
    保存当前窗口状态（最大化/最小化/普通）
    执行 ShowWindow(hwnd, SW_HIDE)
✅ 子窗口自动隐藏，不需要管
✅ 窗口句柄不变
✅ 进程不变

### 步骤 4：统一显示逻辑

plaintext
显示(VW窗口)
    读取之前保存的状态
    恢复状态（ShowWindow 还原）
✅ 完美恢复隐藏前的样子
✅ 子窗口自动恢复
✅ 无任何副作用

### 步骤 5：场景 3 专用兜底策略（软件崩溃后重启）

软件重启时：
枚举所有窗口
找到 book.exe 的顶层主窗口（VW）
判断是否隐藏
如果隐藏 → 自动执行恢复
→ 不需要记录任何文件，也能恢复！

## 三、最终三合一通用架构（你直接照抄）

流程总图
plaintext
软件启动
    ↓
 从设置文件读取之前保存的顶层窗口参数以及枚举所有顶层窗口（win32gui.GetParent(hwnd））
     ↓
 上述顶层窗口参数（窗口标题、hwnd、可见状态win32gui.IsWindowVisible(hwnd)、进程名等等）写入dict或list（顶层窗口列表） 
     ↓
根据【进程名+顶层+标题】筛选出 VW（隐藏窗口列表）
    ↓
记住这个 VW（不管是否可见）
    ↓
【隐藏】→ 隐藏 VW
【显示】→ 恢复 VW
    ↓
软件意外退出？
重启后→按上面流程再次找到 VW → 若需要可以显示操作（由用户自行操作，不需要软件启动后直接把隐藏的显示出来）
特点
三种场景自动适配
不依赖配置文件
不依赖缓存句柄
不依赖窗口可见性
永远能找到目标窗口
永远只操作顶层窗口
子窗口完全不用管
四、给你最终版通用代码（可直接运行）
python
运行
import win32gui
import win32process
import win32api
import win32con

# ==============================================
# 核心工具：找到进程的【任务栏可见主窗口 VW】
# 场景1/2/3 通用
# ==============================================
def find_main_window_by_exe_name(exe_name):
    result = None

    def enum_windows(hwnd, extra):
        nonlocal result
    
        # 条件1：必须是顶层窗口（无父窗口）
        if win32gui.GetParent(hwnd) != 0:
            return True
    
        # 条件2：标题不能为空
        title = win32gui.GetWindowText(hwnd).strip()
        if not title:
            return True
    
        # 获取进程PID
        tid, pid = win32process.GetWindowThreadProcessId(hwnd)
    
        try:
            # 打开进程
            hProc = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, False, pid)
            # 获取进程路径
            exe_path = win32process.GetModuleFileNameEx(hProc, 0)
            win32api.CloseHandle(hProc)
    
            # 条件3：匹配 exe 名称
            if exe_name.lower() in exe_path.lower():
                nonlocal result
                result = hwnd  # 找到！
                return False  # 停止枚举
        except:
            pass
    
        return True
    
    win32gui.EnumWindows(enum_windows, None)
    return result

# ==============================================
# 隐藏窗口（只隐藏选中的顶层主窗口）
# ==============================================
def hide_window(hwnd):
    if not hwnd:
        return
    # 保存状态
​    placement = win32gui.GetWindowPlacement(hwnd)
    # 隐藏
​    win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
​    return placement

# ==============================================
# 显示窗口（完美恢复隐藏前状态）
# ==============================================
def show_window(hwnd, placement=None):
    if not hwnd:
        return

    if placement:
        # 恢复之前的状态
        win32gui.SetWindowPlacement(hwnd, placement)
    else:
        # 自动恢复
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    
    # 激活到前台
    win32gui.SetForegroundWindow(hwnd)

# ==============================================
# 三合一统一入口（你只需要调用这个）
# ==============================================
class WindowManager:
    def __init__(self, exe_name):
        self.exe_name = exe_name
        self.vw_hwnd = None
        self.last_placement = None

    def find_vw(self):
        self.vw_hwnd = find_main_window_by_exe_name(self.exe_name)
        return self.vw_hwnd
    
    def hide(self):
        self.find_vw()
        if self.vw_hwnd:
            self.last_placement = hide_window(self.vw_hwnd)
    
    def show(self):
        self.find_vw()
        if self.vw_hwnd:
            show_window(self.vw_hwnd, self.last_placement)

# ==============================
# 使用示例（三场景通用）
# ==============================
if __name__ == "__main__":
    # 你要管理的进程名
    manager = WindowManager("book.exe")

    # 显示窗口
    # manager.show()
    
    # 隐藏窗口
    # manager.hide()
五、这个方案如何完美支持三种场景？
场景 1：软件先启动 → book.exe 后启动
调用 find_vw() → 自动找到新启动的窗口
场景 2：book.exe 先启动 → 软件后启动
调用 find_vw() → 立刻找到当前可见窗口
场景 3：book.exe 隐藏 → 软件崩溃重启 → 再启动
调用 find_vw() → 依然能找到窗口
调用 show() → 直接恢复显示
六、最终总结（你只需要记住这 4 句）
只操作顶层窗口，子窗口不用管
用 exe + 顶层 + 标题找主窗口，永远不失效
隐藏 = SW_HIDE
显示 = SW_RESTORE
这套逻辑是Windows 窗口管理工具的工业级标准方案，稳定、简洁、无坑。









1. **只对顶层窗口（GA_ROOT）执行显示 / 隐藏 / 最小化**

   不要对子控件操作，否则会崩溃或界面错乱。

   

2. **隐藏主窗口时，最好也隐藏它的所有 Owned 窗口**

   否则会出现：主窗口藏了，弹窗还飘在桌面。

   

3. **判断是否是主窗口：看是否是顶层窗口 + 有 WS_VISIBLE 样式**

   

4. **不要用 Parent 找主窗口！必须用 GA_ROOT！**

   pywin32 快速判断工具（直接用）

   ```
   import win32gui
   import win32con
   
   def get_window_relation(hwnd):
       info = {}
   
       # 父窗口
       info['parent'] = win32gui.GetParent(hwnd)
   
       # 所有者窗口
       info['owner'] = win32gui.GetWindow(hwnd, win32con.GW_OWNER)
   
       # 顶层根窗口
       info['root'] = win32gui.GetAncestor(hwnd, win32con.GA_ROOT)
   
       # 是否是顶层窗口
       info['is_top_level'] = (info['parent'] == 0)
   
       # 是否是子窗口
       info['is_child'] = (info['parent'] != 0)
   
       # 是否有所有者
       info['is_owned'] = (info['owner'] != 0)
   
       return info
   ```

   判断顶层窗口的唯一正确方法：

   

   ```
   win32gui.GetParent(hwnd) == 0
   ```

   = 0 → **顶层窗口**

   ≠0 → 子窗口 / 控件







## 下列内容中book.exe仅用于举例说明，coding的时候绝对不要硬编码

我来描述比如，当前一个进程book.exe,这个进程可能对应了几个窗口（截图显示了几个窗口，对与使用者，可见的体现在任务栏的，应该是唯一的一个，这里暂且命名为“VW”(visibleWindow)，也是可以通过ALT+TAB可以和其他进程进行窗口切换桌面显示的）。
有三种情况：
1、正常情况：本软件先启动；book.exe后启动。
2、正常情况：book.exe先启动，处于正常的状态（没有被本软件进行过显示隐藏操作）；本软件后启动。
3、非正常情况：book.exe进程存在，之前被本软件进行了隐藏操作；之后由于各种原因，本软件退出了，book.exe这个窗口依旧处于隐藏状态，这时候启动本软件，需要对book.exe进行显示操作，使它恢复到正常状态。

针对上述三种情况的操作：
1、隐藏窗口操作，需要把可见的变为隐藏，set iswindowvisiblehwnd false，这里的操作是针对顶层窗口？至于其他的子窗口等等，只要没有显示，不会被人看到，我不关心；
2、显示窗口操作，就是把隐藏掉的窗口（我认为是顶层窗口，不确定是否准确）恢复到隐藏前的状态，比如VW窗口从隐藏恢复到显示，至于其他的子窗口，若隐藏过程中有参数修改，则恢复即可，子窗口在隐藏前不可见，仍旧不可见；当然最佳选择是在可以隐藏顶层窗口的前提下不要修改子窗口的参数，这样恢复显示的时候也不需要对子窗口进行任何操作。

我来帮你把这个场景和三种情况彻底理清楚，同时给你一套能直接落地的处理方案。
一、先澄清核心概念
你截图里的 book.exe 出现了 3 个窗口：
1 个可见窗口（标题：读书巴士 12.7）
2 个后台 / 隐藏窗口（标题：读书巴士 / 空标题）
这就是为什么：
用户在任务栏 / Alt+Tab 里只看到一个窗口（VW），但进程里实际有多个窗口句柄。
你做显示 / 隐藏时，如果选错了句柄，就会出现 “点了隐藏，界面没消失” 或者 “点了显示，界面还是看不见” 的问题。
关键结论（给你的场景）
✅ 你只需要对 book.exe 的「顶层可见主窗口」进行 ShowWindow 操作即可，其他子窗口 / 后台窗口一律不碰。
隐藏：对 VW 执行 ShowWindow(SW_HIDE)，系统会自动把它的所有子窗口一起隐藏，不用你逐个操作。
显示：对 VW 执行 ShowWindow(SW_SHOW)，子窗口会跟着一起恢复，不用额外处理。
二、三种场景的具体处理方案
场景 1：本软件先启动，book.exe 后启动
目标：在 book.exe 启动时，自动找到它的 VW 窗口，并能执行隐藏 / 显示。
步骤：
监听 book.exe 进程启动（可选，也可以定时枚举窗口）
枚举所有顶层窗口（EnumWindows），过滤条件：
进程名 = book.exe
IsWindowVisible(hwnd) == True
GetWindowText(hwnd) 非空
GetParent(hwnd) == 0（无父窗口，是顶层窗口）
把这个 hwnd 记录为该进程的 VW 句柄
隐藏时：直接 ShowWindow(vw_hwnd, SW_HIDE)
显示时：直接 ShowWindow(vw_hwnd, SW_SHOW) 或 SW_RESTORE
场景 2：book.exe 先启动，本软件后启动（未隐藏过）
目标：启动软件时，能正确找到当前可见的 VW 窗口。
步骤：
枚举所有顶层窗口，过滤条件同上（进程名、可见、非空标题、无父窗口）
直接把找到的 hwnd 记录为 VW
后续隐藏 / 显示操作同上
场景 3：book.exe 之前被隐藏过，本软件退出后再启动（窗口处于隐藏状态）
核心难点：此时 IsWindowVisible(vw_hwnd) == False，你用 “可见” 条件就找不到它了。
解决思路：
放弃用 “可见性” 作为唯一筛选条件，改用进程 + 标题 + 无父窗口来定位：
进程名 = book.exe
GetWindowText(hwnd) 匹配你预期的标题（比如包含 “读书巴士”）
GetParent(hwnd) == 0（顶层窗口）
同时记录每个进程的 “上次隐藏状态”（比如在本地保存一个 JSON：{pid: {hwnd: xxx, hidden: true}}），启动时优先用 pid + hwnd 恢复。
恢复显示时，直接对找到的 hwnd 执行：
python
运行
win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
win32gui.SetForegroundWindow(hwnd)  # 可选，拉到前台
三、关键技术细节（避坑）

1. 为什么只操作顶层窗口就够了？
Windows 窗口的可见性是层级继承的：
顶层窗口隐藏 → 所有子窗口自动隐藏（哪怕子窗口的 IsWindowVisible 是 True，也不会被绘制）
顶层窗口显示 → 所有子窗口自动恢复绘制状态
所以你完全不需要遍历子窗口，只对顶层窗口操作即可，恢复时也不会出现子窗口状态错乱的问题。
2. 如何精准定位 book.exe 的顶层窗口？
给你一个可以直接用的过滤函数：
python
运行
import win32gui
import win32process
import win32con

def find_book_windows():
    book_hwnds = []
    def enum_callback(hwnd, _):
        if win32gui.GetParent(hwnd) != 0:
            return True  # 跳过非顶层窗口
        tid, pid = win32process.GetWindowThreadProcessId(hwnd)
        title = win32gui.GetWindowText(hwnd)
        # 这里可以根据你的需求调整过滤条件
        if "book.exe" in win32process.GetModuleFileNameEx(
            win32api.OpenProcess(0x400, False, pid), 0
        ):
            book_hwnds.append({
                "hwnd": hwnd,
                "title": title,
                "visible": win32gui.IsWindowVisible(hwnd)
            })
        return True
    win32gui.EnumWindows(enum_callback, None)
    return book_hwnds
正常情况下，返回的列表里会有 1 个可见的、标题为 “读书巴士 12.7” 的 hwnd，这就是你的 VW。
被隐藏后，这个 hwnd 依然存在，只是 visible 变成 False，标题也还在，你依然能找到它。
3. 隐藏 / 显示的最佳实践
python
运行
# 隐藏窗口
def hide_window(hwnd):
    win32gui.ShowWindow(hwnd, win32con.SW_HIDE)

# 显示窗口（恢复到之前的状态）
def show_window(hwnd):
    # 先获取窗口之前的状态（最小化/最大化/正常）
​    placement = win32gui.GetWindowPlacement(hwnd)
​    cmd_show = placement[1]  # SW_SHOWNORMAL / SW_SHOWMINIMIZED / SW_SHOWMAXIMIZED
​    win32gui.ShowWindow(hwnd, cmd_show)
​    win32gui.SetForegroundWindow(hwnd)  # 可选，激活窗口
用 GetWindowPlacement 能让窗口恢复到隐藏前的状态（比如之前是最大化，恢复后还是最大化），比直接用 SW_SHOW 更友好。
四、针对场景 3 的终极方案
为了防止软件退出后，book.exe 窗口一直处于隐藏状态，建议你：
在隐藏窗口时，把 (pid, hwnd, original_state) 保存到本地文件（比如 window_state.json）
软件启动时，读取这个文件，对每个记录的 hwnd 执行 ShowWindow(original_state)
操作完成后，清空或更新文件，避免重复恢复
示例 JSON 结构：
json
{
  "hidden_windows": [
​    {
​      "pid": 1234,
​      "hwnd": 196610,
​      "title": "读书巴士12.7",
​      "restore_cmd": 9  // 对应 SW_RESTORE
​    }
  ]
}
五、总结你的核心需求
✅ 你只需要做两件事：
对 book.exe 的顶层窗口执行 ShowWindow(SW_HIDE) 隐藏
对同一个 hwnd 执行 ShowWindow(restore_cmd) 恢复显示
子窗口完全不用管，系统会自动处理，也不会出现状态错乱的问题。





## 一、基础标识信息（最常用）

### 1. 窗口标题（窗口文本）

- **pywin32**：`win32gui.GetWindowText(hwnd)`
- 说明：顶层窗口是标题栏；控件是显示文本（跨进程控件可能取不到）Microsoft Learn

### 2. 窗口类名（Class Name）

- **pywin32**：`win32gui.GetClassName(hwnd)`
- 说明：如 `Notepad`、`Chrome_WidgetWin_1`、`CalcFrame`

### 3. 进程 ID（PID）& 线程 ID（TID）

- **pywin32**：`tid, pid = win32process.GetWindowThreadProcessId(hwnd)`
- 用途：定位进程、杀进程、权限判断

### 4. 所在进程路径（EXE 路径）

- pywin32

  ```
  import win32process, win32api
  tid, pid = win32process.GetWindowThreadProcessId(hwnd)
  hProcess = win32api.OpenProcess(0x400 | 0x10, False, pid)
  path = win32process.GetModuleFileNameEx(hProcess, 0)
  ```

  

------

## 二、窗口几何与位置（屏幕坐标）

### 1. 窗口外框矩形（含边框 / 标题栏）

- **pywin32**：`left, top, right, bottom = win32gui.GetWindowRect(hwnd)`
- 单位：像素；坐标：屏幕左上角为原点

### 2. 客户区矩形（不含边框，可绘制区域）

- **pywin32**：`win32gui.GetClientRect(hwnd)`
- 用途：绘图、鼠标点击相对位置

### 3. 窗口是否最小化 / 最大化 / 还原

- pywin32

  ：

  ```
  placement = win32gui.GetWindowPlacement(hwnd)
  ```

  - `placement[1]`：`SW_SHOWNORMAL`/`SW_SHOWMINIMIZED`/`SW_SHOWMAXIMIZED`

  

------

## 三、窗口样式（Style）与扩展样式（ExStyle）

### 1. 标准窗口样式（WS_*）

- **pywin32**：`style = win32api.GetWindowLong(hwnd, win32con.GWL_STYLE)`

- 常用标志：

  - `WS_OVERLAPPEDWINDOW`：普通窗口
  - **<u>`WS_MINIMIZEBOX` / `WS_MAXIMIZEBOX`：有最小 / 最大化按钮</u>**
  - `WS_SYSMENU`：有关闭菜单
  - `WS_BORDER` / `WS_THICKFRAME`：边框样式
  - `WS_DISABLED`：窗口禁用
  - <u>**`WS_VISIBLE`：可见（同 `IsWindowVisible`）**</u>

  

### 2. 扩展窗口样式（WS_EX_*）

- **pywin32**：`exstyle = win32api.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)`

- 常用：

  - `WS_EX_TOPMOST`：总在最前
  - `WS_EX_TOOLWINDOW`：工具窗口（不在任务栏显示）
  - `WS_EX_LAYERED`：分层窗口（透明）
  - `WS_EX_NOACTIVATE`：不激活
  - `WS_EX_TRANSPARENT`：鼠标穿透

  

------

## 四、窗口状态与行为

### 1. 可见性（是否显示）

- **pywin32**：`win32gui.IsWindowVisible(hwnd)` → True/False

### 2. 是否启用（可交互）

- **pywin32**：`win32gui.IsWindowEnabled(hwnd)`

### 3. 是否为 Unicode 窗口

- 

### 4. 是否为悬挂窗口（Hung）

- 用途：判断程序是否假死

### 5. 窗口是否被激活（前景窗口）

- **pywin32**：`win32gui.GetForegroundWindow() == hwnd`

### 6. 窗口 Z 序（前后层级）

- **API**：`GetNextWindow` / `GetTopWindow` / `GetWindow(GW_HWNDPREV)`
- **pywin32**：`win32gui.GetWindow(hwnd, win32con.GW_HWNDNEXT)`

------

## 五、父子 / 归属关系

### 1. 父窗口

- **API**：`GetParent(hwnd)`
- **pywin32**：`win32gui.GetParent(hwnd)`

### 2. 所有者窗口（Owner）

- **API**：`GetWindow(hwnd, GW_OWNER)`
- 区别：Owner 影响模态、Z 序、关闭联动

### 3. 枚举所有子窗口

- **API**：`EnumChildWindows`
- **pywin32**：`win32gui.EnumChildWindows(hwnd, callback, param)`

### 4. 顶层窗口（是否是桌面直接子窗口）

- **API**：`GetAncestor(hwnd, GA_ROOT)`

------

## 六、窗口属性与附加数据

### 1. 窗口属性列表（系统 / 应用附加键值）

- **API**：`EnumPropsEx` / `GetProp`Microsoft Learn
- **pywin32**：`win32gui.EnumPropsEx(hwnd, callback)`Microsoft Learn
- 用途：读取系统 / 第三方附加标记

### 2. 窗口额外数据（GWL_USERDATA）

- **API**：`GetWindowLongPtr(hwnd, GWLP_USERDATA)`Microsoft Learn
- **pywin32**：`win32api.GetWindowLong(hwnd, win32con.GWL_USERDATA)`

------

## 七、控件专用信息（若为子控件）

### 1. 控件 ID

- **API**：`GetDlgCtrlID(hwnd)`
- **pywin32**：`win32gui.GetDlgCtrlID(hwnd)`

### 2. 编辑框 / 按钮等文本（同 GetWindowText）

- 跨进程控件可能需要 `WM_GETTEXT` + 内存注入

------

## 八、其他高级信息

### 1. DPI 感知 / 缩放

- **API**：`GetDpiForWindow` / `GetDpiForSystem`（Win10+）

### 2. 窗口透明度（Layered Window）

- **API**：`GetLayeredWindowAttributes`
- 可获取：透明色、透明度值（Alpha）

### 3. 窗口菜单

- **API**：`GetMenu(hwnd)` / `GetSystemMenu`

### 4. 窗口字体

- **API**：`SendMessage(hwnd, WM_GETFONT, 0, 0)`


---

## 九、核心架构原则：hwnd 唯一标识

### 1. hwnd 是唯一标识符

**核心原则**：在整个软件中，hwnd 是窗口的唯一标识符（主键）。标题（title）和进程名（process_name）仅用于人类辨识和日志记录，不参与窗口身份判定。

- **不做标题严格匹配**：窗口被隐藏后标题可能变化（如浏览器切换标签页），hwnd 仍指向同一个窗口
- **不做进程名严格匹配**：同一个进程可能拥有多个窗口，只有 hwnd 能精确区分
- **配置文件中的 key**：使用 hwnd 而非 (process_name, title) 作为去重和索引依据

### 2. is_taskbar_window vs is_candidate_taskbar_window

| 函数 | IsWindowVisible 检查 | 使用场景 |
|------|---------------------|---------|
| `is_taskbar_window` | **检查**（要求可见） | 检测新窗口路径（process_detector、window_classifier） |
| `is_candidate_taskbar_window` | **不检查**（跳过可见性） | 恢复/跟踪路径（启动恢复、关键字自动选择、防御性写入） |

**原因**：被 `SW_HIDE` 的窗口 `WS_VISIBLE=0`，`is_taskbar_window` 返回 False，但恢复路径需要识别这些窗口。

### 3. 隐藏窗口恢复流程

```
主路径：IsWindow(hwnd) + psutil.pid_exists(pid) → 进程存活即恢复
回退路径：hwnd 失效时按进程名枚举窗口，同样不做标题匹配
防御性检查：is_candidate_taskbar_window(hwnd)（排除 hwnd 被系统复用指向非用户窗口的极端情况）
```

**不做什么**：不验证 `curr_title == saved_title`（标题可能已变化）

### 4. 关键字 → hwnd 流程

```
关键字列表
  ↓
标题匹配 / 进程名匹配 / 关键字.exe 匹配
  ↓
is_candidate_taskbar_window 过滤
  ↓
one-VW-per-PID 过滤（每个 PID 只取一个 VW 窗口）
  ↓
唯一 hwnd → 加入 _hidden_windows / _selected_windows
```

### 5. process_detector 10 步过滤链

所有步骤共用一套过滤逻辑（`_detect_and_track_target_windows_once`）：

1. 子窗口过滤（GetParent != 0）
2. 窗口有效性（is_window）
3. 标题非空
4. 非用户窗口类名排除（DirectUIHWND、Internet Explorer_* 等）
5. 工具窗口排除（WS_EX_TOOLWINDOW）
6. 极小窗口排除（宽/高 < 30px）
7. PID 在目标列表中
8. 标题关键字匹配
9. **is_candidate_taskbar_window**（不检查可见性，兼容 SW_HIDE）
10. one-VW-per-PID（每个 PID 只取一个 VW）

### 6. 函数命名规范

| 旧名（已废弃） | 新名 | 说明 |
|---------------|------|------|
| `check_background_processes` | `detect_target_windows` | 检测目标进程窗口 |
| `recover_hidden_windows` | (已删除) | 纯转发方法，调用方直接用 `detect_target_windows` |
| `is_process_foreground` | `get_process_visible_hwnds` | 返回可见窗口句柄列表 |
| `find_visible_windows_by_process_name` | `find_visible_hwnds_by_process_name` | 按进程名查可见窗口句柄 |
| `find_all_windows_by_process_name` | `find_all_hwnds_by_process_name` | 按进程名查所有窗口句柄 |
| `incremental_detect` | `scan_visible_processes` | 增量扫描可见进程 |
| `_find_matching_background_processes` | `_detect_and_register_background_processes` | 内部：检测并注册后台进程 |
| `_find_all_target_windows_once` | `_detect_and_track_target_windows_once` | 内部：单次枚举检测跟踪 |
| `_enumerate_windows_by_process_name` | `_enumerate_hwnds_by_process_name` | 内部：按进程名枚举句柄 |









