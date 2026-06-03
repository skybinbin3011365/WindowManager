# WinHide - Windows 窗口管理器

一款功能强大的 Windows 窗口管理器，支持窗口隐藏/显示、全局热键操作、时间校准等功能。

## ✨ 功能特性

- **窗口隐藏/显示**：通过热键快速隐藏或显示指定窗口
- **全局热键**：支持自定义鼠标+键盘组合热键
- **窗口切换**：快速将指定进程窗口恢复到前台
- **时间同步**：内置 NTP 时间校准功能
- **智能窗口分类**：自动区分应用窗口和后台进程
- **配置持久化**：所有配置自动保存

## 📦 安装与运行

### 运行打包版本

1. 解压 `WinHide.zip` 到任意目录
2. 双击运行 `WinHide.exe`

### 开发环境运行

```powershell
# 激活虚拟环境
.\.venv\Scripts\Activate.ps1

# 运行主程序
python src/app.py
```

## ⌨️ 默认热键配置

| 热键 | 功能 |
|------|------|
| `鼠标中键 + 鼠标右键` | 隐藏窗口 |
| `Shift + 鼠标右键` | 显示窗口 |
| `Ctrl + 鼠标右键` | 切换窗口（将指定进程窗口恢复到前台） |

## 📁 配置文件说明

### 配置文件存储位置

配置文件根据运行模式自动选择存储位置：

#### 打包版本（发布模式）
```
WinHide.exe 所在目录/config.json
```

#### 开发版本（调试模式）
```
项目根目录/config.json
```

### 配置文件结构

```json
{
  "version": "2.0.0",
  "hide_hotkey": "MBUTTON+RBUTTON",
  "show_hotkey": "SHIFT+RBUTTON",
  "switch_hotkey": "CTRL+RBUTTON",
  "keywords": ["读书", "book"],
  "process_whitelist": ["book.exe"],
  "switch_processes": ["book.exe"],
  "auto_start": false,
  "auto_refresh_interval": 10.0,
  "log_level": "INFO"
}
```

### 配置项说明

| 配置项 | 类型 | 说明 |
|--------|------|------|
| `version` | string | 配置文件版本 |
| `hide_hotkey` | string | 隐藏窗口热键 |
| `show_hotkey` | string | 显示窗口热键 |
| `switch_hotkey` | string | 切换窗口热键 |
| `keywords` | array | 自动选择窗口的关键字列表 |
| `process_whitelist` | array | 进程白名单 |
| `switch_processes` | array | 切换窗口的进程名列表 |
| `auto_start` | bool | 是否开机自启 |
| `auto_refresh_interval` | float | 窗口刷新间隔（秒） |
| `log_level` | string | 日志级别 |

## 🎯 使用方法

### 1. 添加窗口到管理列表

1. 打开软件主界面
2. 在"窗口列表"中找到目标窗口
3. 右键点击窗口，选择"添加到管理"

### 2. 配置自动切换窗口

1. 进入"设置" -> "热键"
2. 在"切换窗口"部分添加进程名
3. 使用 `Ctrl + 鼠标右键` 即可快速切换到该进程窗口

### 3. 设置开机自启

1. 进入"设置" -> "通用"
2. 勾选"开机自动启动"
3. 重启电脑后自动生效

## 🛠️ 开发与打包

### 安装依赖

```powershell
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 打包命令

```powershell
# 使用 PyInstaller（推荐）
pyinstaller WinHide.spec

# 使用 Nuitka（单目录模式）
python -m nuitka --standalone --enable-plugin=pyside6 src/app.py
```

## 📝 日志文件

日志文件存储位置：
- 打包版本：`WinHide.exe 所在目录/logs/`
- 开发版本：`项目根目录/logs/`

## 🐛 常见问题

### Q1: 热键不生效？

A: 请确保软件以管理员权限运行，某些窗口需要管理员权限才能捕获热键。

### Q2: 窗口隐藏后无法显示？

A: 请检查目标窗口进程是否仍在运行，可以在任务管理器中确认。

### Q3: 配置文件丢失？

A: 配置文件存储在 `WinHide.exe` 同目录下的 `config.json` 文件中，请确保该目录有写入权限。

## 📄 许可证

MIT License

---

**版本**: 2.0.0  
**平台**: Windows 10/11  
**Python**: 3.9+
