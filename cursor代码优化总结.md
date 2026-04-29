## 总体结论（现状画像）

这个项目已经形成了清晰的功能主链路：启动入口 → Qt 主窗口 → 热键/托盘 → 窗口枚举与隐藏/恢复 → 配置持久化 →（可选）NTP 校时。P0 级别的启动崩溃问题已全部修复，项目现在可以稳定运行。

------

## 修复状态复核结果（2026-04-27 更新）

### ✅ P0 已完成的修复（已验证）

| 问题 | 文件 | 修复内容 | 验证状态 |
|------|------|----------|----------|
| 缺失 Qt 组件导入 | `src/ui_main.py` | 补齐 `QFrame`、`QComboBox`、`QApplication` 导入 | ✅ 已验证 |
| 未定义变量 | `src/ui_main.py` | 增加 `PSUTIL_AVAILABLE`、`WIN32GUI_AVAILABLE` 可用性探测 | ✅ 已验证 |
| 状态枚举引用错误 | `src/window_classifier.py` | 修正 `WindowState` 为 `WindowEntryState` | ✅ 已验证 |
| 跨线程触达 Qt/UI | `src/ui_main.py` | 新增 `request_refresh`、`request_save_hidden_windows` 信号 | ✅ 已验证 |
| 跨线程触达 Qt/UI | `src/ui.py` | 新增 `request_refresh_windows` 信号，后台线程通过 emit 触发主线程刷新 | ✅ 已验证 |
| 退出时配置不落盘 | `src/ui.py` | 退出保存改为 `immediate=True`，调用 `config_manager.close()` | ✅ 已验证 |
| 配置管理器资源收敛 | `src/config.py` | 新增 `close()` 方法，取消延迟保存 Timer | ✅ 已验证 |
| 依赖策略不一致 | `src/manager.py` | `psutil` 改为可选导入，与 `core.py` 对齐 | ✅ 已验证 |
| 仓库卫生 | `.gitignore` | 已添加 `backup/`、`backup20260427/`、`src_backup/`、`logs/`、`cache.json` | ✅ 已验证 |

------

## 待办事项清单（未完成的优化）

### P1 - 高优先级（建议尽快完成）

---

#### ~~1. 依赖版本约束问题~~ ✅ 已验证无需修复

**验证结果**：
- psutil 7.x 版本已发布（当前环境为 7.2.2）
- `psutil>=7.0.0` 约束正确，无需修改
- 本项目可直接使用 psutil 7.2.2 版本

**结论**：此项为误判，从待办清单中移除。

---

#### 1. Win32/psutil 降级体验优化

**问题描述**：
- 当 `psutil` 或 `win32gui` 依赖缺失时，仅在日志中警告
- 用户无法感知功能受限，可能导致困惑

**涉及文件**：
- `src/ui_main.py`
- `src/ui.py`
- `src/core.py`

**解决方案**：

```python
# src/ui.py - 在 AppWindow.__init__ 中添加依赖状态检查
class AppWindow(QMainWindow):
    def __init__(self, ...):
        super().__init__()
        # ... 现有代码 ...
        
        # 检查依赖状态并显示提示
        self._check_dependencies()

    def _check_dependencies(self):
        """检查关键依赖状态，在状态栏显示提示"""
        warnings = []
        
        # 检查 psutil
        if not PSUTIL_AVAILABLE:
            warnings.append("psutil 不可用，进程名显示受限")
        
        # 检查 win32gui
        if not WIN32_AVAILABLE:
            warnings.append("Win32 API 不可用，窗口管理功能不可用")
        
        # 在状态栏显示警告
        if warnings:
            warning_msg = "⚠️ " + "；".join(warnings)
            self.status_label.setText(warning_msg)
            logger.warning("依赖检查: %s", warning_msg)
            
            # 可选：首次启动时弹窗提示
            if self.config.get("first_run", True):
                QMessageBox.warning(
                    self,
                    "依赖警告",
                    f"以下功能受限：\n\n" + "\n".join(f"• {w}" for w in warnings) +
                    "\n\n请安装相应依赖以获得完整功能。",
                )
```

**风险等级**：🟡 中 - 用户不知道为何某些功能不可用

---

#### 2. 打包资源目录收敛

**问题描述**：
- 资源文件（图标、配置）分散在项目根目录
- spec 文件多处引用，维护困难
- 打包失败或运行时资源缺失风险

**涉及文件**：
- `WinHide_NoConsole.spec`
- `WinHide_WithConsole.spec`
- `WinHide_NoConsole_New.spec`
- 项目根目录的 `WinHide2.ico`、`WinHide2.png`、`config.json`

**解决方案**：

**步骤1：创建资源目录**
```
windowmanager/
├── assets/
│   ├── icons/
│   │   ├── WinHide.ico
│   │   └── WinHide.png
│   └── config/
│       └── config.default.json
├── src/
└── ...
```

**步骤2：修改 spec 文件**
```python
# WinHide_NoConsole.spec 修改
a = Analysis(
    ['run_spec.py'],
    pathex=[str(project_root), str(project_root / 'src')],
    binaries=[],
    datas=[
        # 统一从 assets 目录打包
        ('assets/icons', 'assets/icons'),
        ('assets/config/config.default.json', 'assets/config'),
    ],
    # ... 其他配置 ...
)
```

**步骤3：修改 utils.py 资源路径获取**
```python
# src/utils.py - 更新 get_resource_path 函数
def get_resource_path(relative_path: str) -> str:
    """获取资源文件的绝对路径，支持打包和开发环境"""
    import sys
    from pathlib import Path
    
    # 打包环境
    if getattr(sys, 'frozen', False):
        base_path = Path(sys.executable).parent
    else:
        base_path = Path(__file__).parent.parent
    
    # 优先检查 assets 目录
    assets_path = base_path / 'assets' / relative_path
    if assets_path.exists():
        return str(assets_path)
    
    # 兼容旧路径（根目录）
    root_path = base_path / relative_path
    if root_path.exists():
        return str(root_path)
    
    return str(assets_path)  # 返回期望路径（即使不存在）
```

**风险等级**：🟡 中 - 打包失败或运行时资源缺失

---

#### 3. spec 文件收敛

**问题描述**：
- 存在3份 spec 文件，维护成本高
- 配置不一致可能导致打包行为差异

**涉及文件**：
- `WinHide_NoConsole.spec`
- `WinHide_WithConsole.spec`
- `WinHide_NoConsole_New.spec`

**解决方案**：

**步骤1：删除冗余 spec**
```bash
# 删除冗余文件
rm WinHide_NoConsole_New.spec
```

**步骤2：创建共享配置模块**
```python
# pyinstaller_config.py - 新建共享配置
"""PyInstaller 共享配置"""

# 隐藏导入模块列表
HIDDEN_IMPORTS = [
    # PySide6 核心模块
    'PySide6', 'PySide6.QtCore', 'PySide6.QtWidgets', 'PySide6.QtGui',
    'shiboken6',
    # pynput 模块
    'pynput', 'pynput.keyboard', 'pynput.mouse',
    'pynput._util', 'pynput._util.win32',
    # 系统模块
    'psutil', 'psutil._common', 'psutil._pswindows',
    'win32api', 'win32con', 'win32gui', 'win32process',
    # 项目模块
    'ui', 'ui_main', 'ui_settings', 'ui_about',
    'manager', 'core', 'config', 'constants', 'utils',
    'window_classifier', 'window_models',
]

# 排除模块列表
EXCLUDES = [
    'tkinter', 'test', 'unittest', 'doctest',
    'PySide6.Qt3D*', 'PySide6.QtBluetooth', 'PySide6.QtWebEngine*',
]

# 数据文件
DATAS = [
    ('assets/icons', 'assets/icons'),
    ('assets/config/config.default.json', 'assets/config'),
]
```

**步骤3：简化 spec 文件引用共享配置**
```python
# WinHide_NoConsole.spec
from pyinstaller_config import HIDDEN_IMPORTS, EXCLUDES, DATAS

a = Analysis(
    ['run_spec.py'],
    hiddenimports=HIDDEN_IMPORTS,
    excludes=EXCLUDES,
    datas=DATAS,
    # ...
)
```

**风险等级**：🟡 中 - 配置不一致导致打包行为差异

---

### P2 - 中优先级（建议逐步完成）

---

#### 4. 包结构升级

**问题描述**：
- `src/` 作为扁平顶层模块，容易与其他模块冲突
- PyInstaller 隐藏导入维护成本高
- 入口点 `winhide=app:main` 可能找不到模块

**涉及文件**：
- 整个 `src/` 目录
- `pyproject.toml`
- `setup.py`
- 所有 spec 文件

**解决方案**：

**步骤1：重构目录结构**
```
windowmanager/
├── src/
│   └── windowmanager/          # 新增包目录
│       ├── __init__.py
│       ├── __main__.py         # 支持 python -m windowmanager
│       ├── app.py              # 入口模块
│       ├── core/
│       │   ├── __init__.py
│       │   ├── windows_api.py  # 从 core.py 拆分
│       │   └── models.py       # 数据模型
│       ├── ui/
│       │   ├── __init__.py
│       │   ├── main_window.py  # 从 ui.py 重命名
│       │   ├── tabs/
│       │   │   ├── main_tab.py
│       │   │   ├── settings_tab.py
│       │   │   └── about_tab.py
│       │   └── widgets/
│       ├── services/
│       │   ├── __init__.py
│       │   ├── window_manager.py
│       │   ├── hotkey_manager.py
│       │   └── time_sync.py
│       └── config/
│           ├── __init__.py
│           └── config_manager.py
├── tests/
├── assets/
└── pyproject.toml
```

**步骤2：更新 pyproject.toml**
```toml
[project.scripts]
winhide = "windowmanager.app:main"

[tool.setuptools.packages.find]
where = ["src"]
namespaces = false

[tool.setuptools.package-data]
windowmanager = ["assets/**/*"]
```

**步骤3：更新所有导入语句**
```python
# 旧导入
from core import SafeWindowsAPI
from manager import WindowManager

# 新导入
from windowmanager.core.windows_api import SafeWindowsAPI
from windowmanager.services.window_manager import WindowManager
```

**收益**：
- 减少模块名冲突
- 简化 PyInstaller 配置（自动发现包内模块）
- 更清晰的代码组织

**风险等级**：🟢 低 - 但改动量大，需充分测试

---

#### 5. 窗口枚举/分类单一事实来源（SSOT）

**问题描述**：
- 存在三套并行的窗口枚举逻辑：
  1. `core.SafeWindowsAPI.enum_windows()/enum_hidden_windows()`
  2. `manager.WindowManager.incremental_detect()`
  3. `window_classifier.WindowClassifier.classify_windows()`
- 逻辑重复，维护困难，可能导致不一致

**涉及文件**：
- `src/core.py`
- `src/manager.py`
- `src/window_classifier.py`

**解决方案**：

**步骤1：定义统一的窗口快照数据结构**
```python
# src/window_models.py - 扩展现有模型
@dataclass
class WindowSnapshot:
    """窗口快照 - 统一的窗口信息数据结构"""
    hwnd: int
    pid: int
    process_name: str
    title: str
    class_name: str
    is_visible: bool
    is_taskbar: bool
    state: WindowEntryState
    monitor_id: Optional[int] = None
    
    # 分类信息
    category: str = "unknown"  # "app" | "background" | "system"
```

**步骤2：统一枚举入口**
```python
# src/services/window_enumerator.py - 新建模块
class WindowEnumerator:
    """窗口枚举器 - 单一事实来源"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_all_windows(self) -> List[WindowSnapshot]:
        """获取所有窗口快照（唯一入口）"""
        windows = []
        
        def enum_callback(hwnd, _):
            snapshot = self._create_snapshot(hwnd)
            if snapshot:
                windows.append(snapshot)
            return True
        
        if WIN32_AVAILABLE:
            win32gui.EnumWindows(enum_callback, None)
        
        return windows
    
    def _create_snapshot(self, hwnd: int) -> Optional[WindowSnapshot]:
        """创建单个窗口快照"""
        # 统一的快照创建逻辑
        ...
```

**步骤3：重构现有模块**
```python
# manager.py - 使用统一枚举器
class WindowManager:
    def __init__(self):
        self._enumerator = WindowEnumerator()
    
    def refresh_windows(self):
        """刷新窗口列表"""
        self._windows = self._enumerator.get_all_windows()

# window_classifier.py - 只做分类策略
class WindowClassifier:
    def classify(self, windows: List[WindowSnapshot]) -> Tuple[List, List]:
        """对已枚举的窗口进行分类"""
        apps = []
        background = []
        for window in windows:
            if self._is_app_window(window):
                window.category = "app"
                apps.append(window)
            else:
                window.category = "background"
                background.append(window)
        return apps, background
```

**收益**：
- 消除重复逻辑
- 确保数据一致性
- 简化维护

**风险等级**：🟢 低 - 但需仔细测试

---

#### 7. 配置模型与 UI 解耦

**问题描述**：
- `ui_settings.py` 直接读取 `about_tab` 的勾选框状态写回配置
- UI 结构变化会影响配置保存逻辑

**涉及文件**：
- `src/ui_settings.py`
- `src/ui_about.py`

**解决方案**：

**步骤1：在 SettingsTab 中维护完整配置状态**
```python
# src/ui_settings.py
class SettingsTab(QWidget):
    def __init__(self, ...):
        # 日志配置控件（从 AboutTab 移过来）
        self.ntp_log_checkbox = QCheckBox("显示 NTP 日志")
        self.window_refresh_log_checkbox = QCheckBox("显示窗口刷新日志")
        self.window_operation_log_checkbox = QCheckBox("显示窗口操作日志")
        self.debug_log_checkbox = QCheckBox("显示 DEBUG 日志")
    
    def load_config(self, config: Config):
        """从配置加载到控件"""
        self.ntp_log_checkbox.setChecked(config.enable_ntp_log)
        self.window_refresh_log_checkbox.setChecked(config.enable_window_refresh_log)
        # ...
    
    def save_config(self) -> dict:
        """从控件收集配置（不依赖其他 Tab）"""
        return {
            "enable_ntp_log": self.ntp_log_checkbox.isChecked(),
            "enable_window_refresh_log": self.window_refresh_log_checkbox.isChecked(),
            "enable_window_operation_log": self.window_operation_log_checkbox.isChecked(),
            "enable_debug_log": self.debug_log_checkbox.isChecked(),
        }
```

**步骤2：AboutTab 只负责展示**
```python
# src/ui_about.py
class AboutTab(QWidget):
    # 日志过滤开关移到 SettingsTab
    # AboutTab 只负责：
    # 1. 显示日志内容
    # 2. 提供日志过滤接口
    
    def append_log(self, message: str):
        """追加日志（由外部调用）"""
        self.log_text.append(message)
    
    def should_show_log(self, log_type: str, config: Config) -> bool:
        """根据配置判断是否显示日志"""
        if log_type == "ntp":
            return config.enable_ntp_log
        elif log_type == "window_refresh":
            return config.enable_window_refresh_log
        # ...
```

**收益**：
- UI 结构变化不影响配置保存
- 职责清晰，易于维护

**风险等级**：🟢 低

---

#### 7. 依赖声明统一

**问题描述**：
- 同时维护 `pyproject.toml`、`requirements.txt`、`setup.py` 三处依赖
- 版本可能不一致，维护成本高

**涉及文件**：
- `pyproject.toml`
- `requirements.txt`
- `setup.py`

**解决方案**：

**步骤1：以 pyproject.toml 为唯一来源**
```toml
# pyproject.toml - 唯一依赖声明
[project]
dependencies = [
    "PySide6>=6.10.0",
    "psutil>=5.9.0,<7.0.0",
    "pywin32>=311",
    "pynput>=1.7.6",
]
```

**步骤2：删除或最小化其他文件**
```bash
# 方案A：删除 requirements.txt 和 setup.py
rm requirements.txt setup.py

# 方案B：保留但自动生成
# requirements.txt - 由 pyproject.toml 生成
# 在 CI/CD 或开发时运行：
pip-compile pyproject.toml -o requirements.txt
```

**步骤3：setup.py 简化为兼容层**
```python
# setup.py - 仅用于兼容旧版 pip
from setuptools import setup

# 从 pyproject.toml 读取配置
setup()  # 所有配置在 pyproject.toml 中
```

**收益**：
- 单一来源，避免版本不一致
- 减少维护成本

**风险等级**：🟢 低

---

### P3 - 低优先级（工程化改进）

---

#### 8. 仓库清理

**问题描述**：
- 虽然 `.gitignore` 已配置，但备份目录仍存在于仓库中
- 占用仓库体积，可能干扰开发

**涉及目录**：
- `backup/`
- `backup20260427/`
- `src_backup/`

**解决方案**：

```bash
# 步骤1：从 Git 历史中移除备份目录
git rm -r --cached backup/ backup20260427/ src_backup/

# 步骤2：提交更改
git commit -m "chore: 从仓库中移除备份目录"

# 步骤3：清理 Git 历史（可选，减少仓库体积）
git filter-branch --force --index-filter \
  'git rm -rf --cached --ignore-unmatch backup/ backup20260427/ src_backup/' \
  --prune-empty --tag-name-filter cat -- --all

# 步骤4：强制推送（如果已推送到远程）
git push origin --force --all
```

**收益**：
- 减少仓库体积
- 避免干扰

**风险等级**：🟢 低

------

## 推荐的下一步执行顺序

| 步骤 | 任务 | 预估时间 | 优先级 |
|------|------|----------|--------|
| 1 | 实现 Win32/psutil 降级时的 UI 提示 | 1小时 | 🔴 高 |
| 2 | 收敛资源目录和 spec 文件 | 2小时 | 🔴 高 |
| 3 | 依赖声明统一 | 30分钟 | 🟡 中 |
| 4 | 配置模型与 UI 解耦 | 2小时 | 🟡 中 |
| 5 | 包结构升级 | 半天 | 🟢 低 |
| 6 | 窗口枚举/分类 SSOT 重构 | 1-2天 | 🟢 低 |
| 7 | 仓库备份目录清理 | 30分钟 | 🟢 低 |

------

## 历史修复记录

### 2026-04-27 完成的修复

1. **`src/ui_main.py` 启动即崩问题**
   - 补齐缺失导入：`QFrame`、`QComboBox`、`QApplication`
   - 修复未定义变量：增加 `PSUTIL_AVAILABLE`、`WIN32GUI_AVAILABLE` 可用性探测

2. **`src/window_classifier.py` 状态枚举错误**
   - 修正 `WindowState.VISIBLE/HIDDEN/INVALID` 为 `WindowEntryState.VISIBLE/HIDDEN/INVALID`

3. **跨线程触达 Qt/UI 与配置对象**
   - `src/ui_main.py`：新增信号 `request_refresh`、`request_save_hidden_windows`
   - `src/ui.py`：新增信号 `request_refresh_windows`，后台线程通过 emit 触发主线程刷新

4. **退出时配置可能不落盘**
   - `src/ui.py`：退出保存配置改为 `immediate=True`，调用 `ConfigManager.close()`
   - `src/config.py`：新增 `close()` 方法

5. **依赖策略一致性**
   - `src/manager.py`：`psutil` 改为可选导入

6. **仓库卫生**
   - `.gitignore`：已添加备份目录和运行时产物的忽略规则
