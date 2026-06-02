# 项目打包指南
# ==============

## 环境要求

1. 使用 `env2` 虚拟环境
2. Python 3.12+
3. 已安装 PyInstaller

## 依赖说明

### 当前必须的依赖 (3个核心包)
```
PySide6==6.10.2      # 界面框架
psutil==7.2.2         # 进程管理
pywin32==311          # Windows API
```

### 可选依赖 (开发工具)
```
black==24.8.0         # 代码格式化
flake8==7.1.0         # 代码检查
```

## 安装打包工具

```powershell
cd e:\Python\Python3.12\my_python_project\windowmanager
.\env2\Scripts\Activate.ps1
pip install pyinstaller
```

## 打包命令

### 方式1: 单文件版本 (推荐，使用优化配置)
```powershell
pyinstaller WinHide_OneFile.spec
```

### 方式2: 目录版本 (开发调试用)
```powershell
pyinstaller WinHide.spec
```

## 打包优化措施

### 已实现的优化
1. **排除未使用的Qt模块** (节省约60MB)
   - Qt 3D, Qt Bluetooth, Qt Charts, Qt Multimedia 等
   - Qt WebEngine, Qt QML, Qt Quick 等

2. **排除未使用的Python标准库**
   - tkinter, unittest, email, http, urllib, xml, multiprocessing

3. **排除开发工具**
   - pip, setuptools, wheel, black, flake8

4. **最高级别优化**
   - optimize=2 (去除断言，优化字节码)

5. **UPX压缩** (已启用)

## 打包产物

输出在 `dist/` 目录:
- `WinHide/` (目录版本)
- `WinHide_OneFile.exe` (单文件版本)

## 文件清单

打包前确保存在以下文件:
```
config.json           # 配置文件
WinHide2.png          # 程序图标(PNG)
WinHide2.ico          # 程序图标(ICO)
```

## 减小体积的进一步建议

1. **UPX压缩**: 使用最新版UPX工具
2. **单文件模式**: 优先使用单文件版本
3. **移除调试信息**: 保持 console=False
4. **预编译优化**: 使用 --onefile --windowed

## 测试打包后的程序

```powershell
cd dist
.\WinHide_OneFile.exe
```

## 当前虚拟环境 (env2) 已安装的包

- Python 3.12.10
- PySide6 6.10.2
- psutil 7.2.2
- pywin32 311
- black 24.8.0
- flake8 7.1.0
- pip 26.0.1
