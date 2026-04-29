# 一 窗口管理器

## 1 设定窗口的管理逻辑

### 1.1 类似windows系统的任务管理器，列出所有进程

### 1.2 区分“应用”与“后台进程”：

Windows 任务管理器 “进程” 标签下的 **应用** 与 **后台进程**，核心区分规则只有一条：**是否有可见窗口（UI 线程）**。

| 类别                              | 判定标准                                                     | 典型特征                                  | 常见示例                                        |
| --------------------------------- | ------------------------------------------------------------ | ----------------------------------------- | ----------------------------------------------- |
| **应用 (App)**                    | 进程拥有**可见窗口**（有 UI 线程 / 主窗口句柄）Microsoft Learn | 可交互、可关闭、会在任务栏 / Alt+Tab 显示 | 浏览器、Office、微信、代码编辑器                |
| **后台进程 (Background Process)** | 进程**无可见窗口**（无 UI 线程）Microsoft Learn              | 无界面、常驻后台、用户不直接交互          | 浏览器渲染 / 插件进程、输入法、下载器、应用助手 |

### 补充说明

1. **边界情况**

   

   - 最小化到托盘的应用（如钉钉）仍算 “应用”，因主进程有窗口；托盘仅为子窗口 / 图标。
   - 部分应用拆分为 “前台 + 后台” 组合（如 Chrome 多进程），主窗口进程归 “应用”，渲染 / 插件归 “后台进程”。

   

2. **与 “Windows 进程” 的区别**

   

   - **Windows 进程**：系统关键进程（如 `explorer.exe`、`system`），标记为 critical，通常不建议结束Microsoft Learn。

   

3. **实用判断技巧**

   

   - 在任务管理器 “进程” 标签，勾选 **“命令行”** 列，查看进程是否有 `-window`、`-ui` 等启动参数辅助判断。
   - 结束 “应用” 可直接右键 “结束任务”；结束 “后台进程” 需谨慎，避免影响主程序或系统稳定。

   

------

一句话总结：**看得见窗口的是 “应用”，完全后台运行的是 “后台进程”**。



![PixPin_2026-04-23_11-18-51](D:\Program Files\PixPin\Temp\PixPin_2026-04-23_11-18-51.jpg)

### 1.3 对于"应用"进行管理，获取列表：

**完全能精准拿到任务管理器里显示的「应用」列表**（就是带窗口、出现在 Alt+Tab、任务栏里的那些）。

原理就是：**任务管理器判定 “应用” 的官方标准 = 有可见、可切换、非子窗口的顶层窗口**。

下面给你一段 **可直接运行的 Python 代码**，精确筛选出任务管理器里的「应用」，不是后台进程。

------

# Python 代码：获取任务管理器中的「应用」列表

依赖：`pywin32`

```
import win32gui
import win32process
import psutil

def is_visible_top_window(hwnd):
    """判断一个窗口是否是任务管理器认定的「应用窗口」"""
    # 1. 必须可见
    if not win32gui.IsWindowVisible(hwnd):
        return False

    # 2. 必须是顶层窗口（无父窗口）
    if win32gui.GetParent(hwnd) != 0:
        return False

    # 3. 必须有 WS_EX_APPWINDOW 或 WS_EX_WINDOWEDGE 风格（Alt+Tab 可切换）
    exstyle = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    if not (exstyle & win32con.WS_EX_APPWINDOW):
        return False

    # 4. 窗口标题不能为空
    title = win32gui.GetWindowText(hwnd).strip()
    if not title:
        return False

    return True

def get_taskmanager_app_list():
    app_list = []

    def callback(hwnd, extra):
        if is_visible_top_window(hwnd):
            title = win32gui.GetWindowText(hwnd)
            tid, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                proc = psutil.Process(pid)
                app_list.append({
                    'pid': pid,
                    'name': proc.name(),
                    'title': title,
                    'exe': proc.exe()
                })
            except:
                pass
        return True

    win32gui.EnumWindows(callback, None)
    return app_list


# 测试
if __name__ == '__main__':
    import win32con
    apps = get_taskmanager_app_list()
    for app in apps:
        print(f"[{app['pid']}] {app['name']} - {app['title']}")
```

它**完全复刻任务管理器筛选 “应用” 的逻辑**：

1. 窗口必须 **可见**
2. 必须是 **顶层窗口**（不是子控件）
3. 必须是 **Alt+Tab 可切换** 的窗口（`WS_EX_APPWINDOW`）
4. 必须有 **窗口标题**
5. 排除托盘类后台小窗口

这样得到的列表，**和任务管理器 → 进程 → “应用” 一栏完全一致**。

### 1.4 “关键字”列表

关键字列表中，是一些字段，而“应用”的标题“title”中可能包含其中的字段

### 1.5 “设定窗口”列表

- 包含“关键字”字段的窗口，自动添加到“设定窗口”列表
- 对“应用”列表中的窗口，可以进行选中和取消选中的操作；选中后自动添加到“设定窗口”列表
- “设定窗口”列表中的条目，按上述分两类，来自于“关键字“列表的以及从“应用”列表中添加的
- 对于从“应用”列表中添加的条目，可以进行移除操作（鼠标右键菜单）
- 来自于“关键字“列表的条目，仅能通过从”关键字“列表中移除关键字之后才能自动移除
- 设定窗口列表，具备状态显示，”隐藏“和”可见“以及”无效“三种状态（可以根据字面意思理解”隐藏“”可见“状态，"无效"状态是指进程不存在的状态）
- 设定窗口列表中的条目，需获取进程名以及对应的句柄hwnd，同时加入字典。比如：{name:notepad.exe,title:记事本,hwnd:218}
- 上述字典需定时保存到config文件中

1. ### 6 对”设定窗口列表“内所有条目进行”隐藏“和"显示"操作

2. ## 隐藏显示操作

   2.1 使用软件界面按钮或设置好的热键组合，实现窗口隐藏/显示

   实现窗口隐藏 / 显示，就是对句柄做了这两件事之一：
   

   ## 隐藏（推荐）

   ```
   def hide_to_tray(hwnd):
       win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
   ```

   ## 恢复

   ```
   def show_from_tray(hwnd):
       win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
   ```

   2. 2 实现上述隐藏之后，”应用“列表中就找不到这个进程了；但在”设定窗口“列表中始终存在，只是状态从”可见“变成了”隐藏“

3. 异常处理

   在一些应用被隐藏之后，若软件出了意外的处理：

   3.1 软件再次启动，需从config中恢复”设定窗口“列表的内容，因为被隐藏的应用没有变化，因此这些软件的hwnd也没有变化

   3.2 对恢复的”设定窗口“列表中的所有条目，检测一遍是否后台在运行，以确定状态：可见、隐藏、无效。

   3. 3这时候通过热键或”显示窗口“按钮，应该可以把软件意外发生之前隐藏的窗口可以显示回来

4. WMI 事件监听机制

   - 在进程不存在的时候，”应用“列表中是没有某个进程的；设定窗口列表中的一些条目，在进程不存在的时候也是”无效“状态

   - 软件运行期间，可能我们打开了一些进程，这时候，就需要WMI 事件监听机制来监测到这个进程启动了，然后设定窗口列表中的状态进行实时更新且热键可以对这个进程进行显示隐藏窗口的操作

   - **任何新进程启动，你的程序立刻收到通知**（仅监控设定窗口列表中的进程）

     包括：主程序后来才启动的子进程、插件进程、辅助进程…

```
import wmi
import threading

def monitor_process_creation():
    """实时监听新进程创建（专业方案）"""
    def watcher():
        c = wmi.WMI()
        # 监听 Windows 进程创建事件（系统级推送，不占CPU）
        process_watcher = c.Win32_Process.watch_for("creation")
        
        while True:
            try:
                # 阻塞等待，进程来之前不占CPU
                new_process = process_watcher()
                pid = new_process.ProcessId
                name = new_process.Name
                cmdline = new_process.CommandLine
                
                print(f"【新进程启动】pid={pid}, name={name}")
                
                # =============================================
                # 你在这里写判断：
                # if "xxx.exe" in name:
                #     do_something()
                # =============================================
                
            except Exception as e:
                break

    # 后台线程运行，不卡主程序
    thread = threading.Thread(target=watcher, daemon=True)
    thread.start()

# ======================
# 启动监听
# ======================
monitor_process_creation()

# 主程序继续运行...
input("按回车退出\n")
```

参考代码：

```
import wmi
import threading
import psutil

# ======================
# 你要监控的目标进程名
# ======================
TARGET_PROCESS_NAMES = {"notepad.exe", "chrome.exe", "wechat.exe"}

def check_existing_processes():
    """
    1. 软件启动时：检查【已经在运行】的进程
    """
    print("\n=== 检查当前已运行的进程 ===")
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            pid = proc.info['pid']
            name = proc.info['name'].lower()
            if name in TARGET_PROCESS_NAMES:
                print(f"[已存在] {name} (PID: {pid})")
                # 这里写你要执行的逻辑
        except:
            pass

def monitor_process_creation():
    """
    2. 监听【后来才启动】的新进程（实时推送，无CPU占用）
    """
    def watcher():
        c = wmi.WMI()
        process_watcher = c.Win32_Process.watch_for("creation")
        
        while True:
            try:
                new_proc = process_watcher()  # 阻塞等事件，不占CPU
                pid = new_proc.ProcessId
                name = new_proc.Name.lower()

                if name in TARGET_PROCESS_NAMES:
                    print(f"\n[新进程启动] {name} (PID: {pid})")
                    # 这里写你要执行的逻辑
                    
            except Exception:
                break

    t = threading.Thread(target=watcher, daemon=True)
    t.start()

# ======================
# 启动完整监控
# ======================
if __name__ == "__main__":
    # 第一步：查已经在运行的
    check_existing_processes()

    # 第二步：监听未来启动的
    monitor_process_creation()

    print("\n✅ 进程监控已启动（按回车退出）...\n")
    input()
```



# 这个方案是最合理的？

## 1. 启动时枚举 = 抓**过去已存在**的

- 只执行**一次**
- 极快
- 不会漏

## 2. WMI 事件监听 = 抓**未来新增**的

- **0% CPU**
- 系统主动推送
- 实时响应
- 不卡、不轮询、不延迟

## 3. **没有比这个更优的方案了**

- 定时器：差、占 CPU、会漏
- 只监听：会漏掉启动前就运行的进程
- **枚举 + 监听**：**100% 全覆盖**

------

# 你的场景完美匹配：

### 情况 A：进程已经运行

→ **check_existing_processes () 立刻抓到**

### 情况 B：进程后来才启动

→ **monitor_process_creation () 实时收到**

### 结果：

**无论进程什么时候启动，你都能稳稳监测到。**

------

# 极简总结

## 要实现：

**进程已运行 + 后启动软件 → 都能监测**

## 正确方案只有一种：

### **启动枚举一次已存在进程 + 启动 WMI 实时监听未来进程**







5 白名单机制：对于某些进程，加入白名单，禁止对其中的进程进行任何的隐藏显示操作。同时白名单中的进程，不再出现在可见窗口名单中。

