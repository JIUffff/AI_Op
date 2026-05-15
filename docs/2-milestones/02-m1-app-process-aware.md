# 02 - M1 应用与进程感知

对应总文档第 11 节 M1（第 2-3 周）
前置文档：[../1-standards/00-project-overview.md](../1-standards/00-project-overview.md)、[../2-milestones/01-m0-engineering-foundation.md](../2-milestones/01-m0-engineering-foundation.md)

---

## 0. 本阶段目标

实现 Windows 应用扫描、进程/窗口引擎、App Profile 系统。交付物：能识别主流应用、正确映射窗口标题与进程、可启动目标应用。

---

## 1. 全局规则速查

- MVP 只做 Windows 平台
- MVP 三应用：VSCode / Chrome / 文件管理器
- 安全底线：默认拒绝、L5-L7 需确认
- 控制路径优先级：CLI/API > 文件系统 > Accessibility > DOM/CDP > Vision > 鼠标键盘

---

## 2. 本阶段架构

```
apps/runtime/
  src/
    engines/
      app_scanner.py       # Windows 应用扫描
      process_engine.py    # 进程与窗口管理
      app_profile.py       # App Profile 系统
    mcp_tools/
      app_list.py          # MCP 工具: 列出应用
      app_launch.py        # MCP 工具: 启动应用
```

数据流：
```
用户: "打开 VSCode"
  -> Runtime 解析意图 -> 查询 App Scanner 找到 VSCode 路径
    -> Process Engine 检查是否已运行
      -> 未运行: 启动 VSCode
      -> 已运行: 激活窗口
    -> 返回结果 + 审计日志
```

---

## 3. Windows App Scanner

### 3.1 扫描策略

按优先级顺序扫描应用安装位置：

| 优先级 | 位置 | 扫描方式 |
|--------|------|---------|
| 1 | 开始菜单快捷方式 | `C:\ProgramData\Microsoft\Windows\Start Menu\Programs\` + `%APPDATA%\Microsoft\Windows\Start Menu\Programs\` |
| 2 | 注册表 Uninstall 项 | `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall` + `HKCU\...` |
| 3 | 常见安装目录 | `C:\Program Files\`、`C:\Program Files (x86)\` |
| 4 | UWP 应用 | `Get-AppxPackage` PowerShell 命令 |

### 3.2 应用数据结构

```python
# apps/runtime/src/engines/app_scanner.py

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import subprocess
import winreg
from pathlib import Path

@dataclass
class AppInfo:
    """应用信息。"""
    app_id: str               # 唯一标识，如 "vscode"、"chrome"
    display_name: str         # 显示名称，如 "Visual Studio Code"
    executable_path: Path     # 可执行文件路径
    icon_path: Optional[Path] # 图标路径
    install_location: Path    # 安装目录
    version: Optional[str]    # 版本号
    launch_args: list[str] = field(default_factory=list)  # 默认启动参数
    category: str = ""        # 分类: editor/browser/file_manager/other
    
    # 用于 Skill 绑定
    supports_cli: bool = False       # 是否有命令行接口
    cli_command: Optional[str] = None
    supports_cdp: bool = False       # 是否支持 CDP（浏览器）
    cdp_port: Optional[int] = None
```

### 3.3 扫描实现骨架

```python
# apps/runtime/src/engines/app_scanner.py

import subprocess
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("runtime.app_scanner")

# MVP 预定义应用列表（可识别的目标应用）
KNOWN_APPS = {
    "vscode": {
        "display_name": "Visual Studio Code",
        "executable_names": ["Code.exe"],
        "category": "editor",
        "supports_cli": True,
        "cli_command": "code",
        "registry_keys": [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{EA457B01-F7ED-44DE-9285-63D0E3285117}_is1"),
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{EA457B01-F7ED-44DE-9285-63D0E3285117}_is1"),
        ],
    },
    "chrome": {
        "display_name": "Google Chrome",
        "executable_names": ["chrome.exe"],
        "category": "browser",
        "supports_cdp": True,
        "cdp_port": 9222,
        "registry_keys": [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Google Chrome"),
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall\Google Chrome"),
        ],
    },
    "file_explorer": {
        "display_name": "File Explorer",
        "executable_names": ["explorer.exe"],
        "category": "file_manager",
        "executable_path": Path(r"C:\Windows\explorer.exe"),  # 系统内置
    },
}

class AppScanner:
    """Windows 应用扫描器。"""
    
    def __init__(self):
        self._cache: dict[str, AppInfo] = {}
    
    def scan(self) -> list[AppInfo]:
        """扫描所有已知应用。"""
        results = []
        for app_id, config in KNOWN_APPS.items():
            info = self._resolve_app(app_id, config)
            if info:
                results.append(info)
                self._cache[app_id] = info
        return results
    
    def get_app(self, app_id: str) -> Optional[AppInfo]:
        """获取指定应用信息。"""
        if app_id not in self._cache:
            self._cache[app_id] = self._resolve_app(app_id, KNOWN_APPS.get(app_id, {}))
        return self._cache.get(app_id)
    
    def _resolve_app(self, app_id: str, config: dict) -> Optional[AppInfo]:
        """解析单个应用路径。"""
        # 优先从注册表获取
        for key_path in config.get("registry_keys", []):
            try:
                hkey, subkey = key_path
                with winreg.OpenKey(hkey, subkey) as key:
                    exe_path = winreg.QueryValueEx(key, "DisplayIcon")[0]
                    if exe_path:
                        return AppInfo(
                            app_id=app_id,
                            display_name=config["display_name"],
                            executable_path=Path(exe_path.split(",")[0]),
                            install_location=Path(exe_path).parent,
                            version=config.get("version"),
                            category=config.get("category", ""),
                            supports_cli=config.get("supports_cli", False),
                            cli_command=config.get("cli_command"),
                            supports_cdp=config.get("supports_cdp", False),
                            cdp_port=config.get("cdp_port"),
                        )
            except (FileNotFoundError, OSError):
                continue
        
        # 回退：在常见路径中搜索
        for exe_name in config.get("executable_names", []):
            for search_dir in [
                Path(r"C:\Program Files"),
                Path(r"C:\Program Files (x86)"),
                Path.home() / "AppData" / "Local",
            ]:
                found = list(search_dir.glob(f"**/{exe_name}"))
                if found:
                    return AppInfo(
                        app_id=app_id,
                        display_name=config["display_name"],
                        executable_path=found[0],
                        install_location=found[0].parent,
                        category=config.get("category", ""),
                        supports_cli=config.get("supports_cli", False),
                        cli_command=config.get("cli_command"),
                        supports_cdp=config.get("supports_cdp", False),
                        cdp_port=config.get("cdp_port"),
                    )
        
        # 系统内置应用
        if "executable_path" in config:
            return AppInfo(
                app_id=app_id,
                display_name=config["display_name"],
                executable_path=config["executable_path"],
                install_location=config["executable_path"].parent,
                category=config.get("category", ""),
            )
        
        logger.warning(f"未找到应用: {app_id}")
        return None
    
    def scan_start_menu(self) -> list[AppInfo]:
        """扫描开始菜单快捷方式（扩展扫描）。"""
        start_menu_dirs = [
            Path(r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs"),
            Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        ]
        results = []
        for dir_path in start_menu_dirs:
            if dir_path.exists():
                for lnk in dir_path.rglob("*.lnk"):
                    # 使用 PowerShell 解析 .lnk 文件
                    results.append(self._parse_shortcut(lnk))
        return results
    
    def _parse_shortcut(self, lnk_path: Path) -> Optional[AppInfo]:
        """解析快捷方式文件。"""
        try:
            # PowerShell 解析 .lnk
            ps_script = f"""
            $shell = New-Object -ComObject WScript.Shell
            $shortcut = $shell.CreateShortcut('{lnk_path}')
            $shortcut.TargetPath
            """
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True, text=True, timeout=5
            )
            target = result.stdout.strip()
            if target and Path(target).suffix.lower() == ".exe":
                return AppInfo(
                    app_id=Path(target).stem.lower(),
                    display_name=lnk_path.stem,
                    executable_path=Path(target),
                    install_location=Path(target).parent,
                    category="other",
                )
        except Exception:
            pass
        return None
```

---

## 4. Process & Window Engine

### 4.1 功能

| 功能 | 实现方式 | 权限级别 |
|------|---------|---------|
| 列出运行中的进程 | `psutil` 或 `win32process` | L0 |
| 查找窗口 | `pywin32` EnumWindows | L0 |
| 启动应用 | `subprocess.Popen` | L2 |
| 激活窗口 | `SetForegroundWindow` | L3 |
| 关闭进程 | `taskkill` | L6 |
| 获取窗口标题 | `GetWindowText` | L0 |

### 4.2 实现骨架

```python
# apps/runtime/src/engines/process_engine.py

import subprocess
import logging
import time
from pathlib import Path
from typing import Optional
import win32gui
import win32process
import psutil

logger = logging.getLogger("runtime.process_engine")

class ProcessEngine:
    """进程与窗口管理引擎。"""
    
    def list_processes(self) -> list[dict]:
        """列出所有运行中的进程。"""
        processes = []
        for proc in psutil.process_iter(["pid", "name", "exe"]):
            try:
                processes.append({
                    "pid": proc.info["pid"],
                    "name": proc.info["name"],
                    "exe": str(proc.info["exe"]) if proc.info["exe"] else None,
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return processes
    
    def find_process_by_name(self, name: str) -> list[dict]:
        """根据名称查找进程。"""
        return [p for p in self.list_processes() if p.get("name") and name.lower() in p["name"].lower()]
    
    def find_windows_by_title(self, title_contains: str) -> list[dict]:
        """根据窗口标题查找窗口。"""
        results = []
        def callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                window_title = win32gui.GetWindowText(hwnd)
                if title_contains.lower() in window_title.lower():
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    results.append({
                        "hwnd": hwnd,
                        "title": window_title,
                        "pid": pid,
                    })
            return True
        win32gui.EnumWindows(callback, None)
        return results
    
    def launch_app(self, exe_path: Path, args: list[str] = None, wait_seconds: float = 3.0) -> dict:
        """启动应用。
        
        Args:
            exe_path: 可执行文件路径
            args: 启动参数
            wait_seconds: 等待应用启动的时间（秒）
        
        Returns:
            {"pid": int, "success": bool, "error": str}
        """
        cmd = [str(exe_path)]
        if args:
            cmd.extend(args)
        
        logger.info(f"启动应用: {' '.join(cmd)}")
        
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(wait_seconds)
            
            # 验证进程是否仍在运行
            if proc.poll() is not None:
                return {
                    "pid": proc.pid,
                    "success": False,
                    "error": f"进程已退出，返回码 {proc.returncode}",
                }
            
            return {
                "pid": proc.pid,
                "success": True,
                "error": None,
            }
        except FileNotFoundError:
            return {"pid": None, "success": False, "error": f"可执行文件不存在: {exe_path}"}
        except Exception as e:
            return {"pid": None, "success": False, "error": str(e)}
    
    def bring_window_to_front(self, hwnd: int) -> bool:
        """将窗口置于前台。"""
        try:
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, 9)  # SW_RESTORE
            win32gui.SetForegroundWindow(hwnd)
            return True
        except Exception as e:
            logger.error(f"激活窗口失败: {e}")
            return False
    
    def is_process_running(self, exe_name: str) -> bool:
        """检查进程是否正在运行。"""
        return len(self.find_process_by_name(exe_name)) > 0
    
    def kill_process(self, pid: int) -> dict:
        """终止进程。权限 L6。"""
        try:
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], check=True, capture_output=True)
            return {"success": True, "error": None}
        except subprocess.CalledProcessError as e:
            return {"success": False, "error": e.stderr.decode()}
```

---

## 5. App Profile 系统

App Profile 是应用的元数据描述，用于：
- Skill 与特定应用版本绑定
- 自动化策略（CLI 优先还是 UIA 优先）
- 元素定位器版本管理

### 5.1 Profile 数据结构

```yaml
# data/app_profiles/vscode.yaml
app_id: vscode
display_name: "Visual Studio Code"
executable: "Code.exe"
category: editor

# 自动化策略
automation:
  preferred_method: cli     # cli > filesystem > uia > vision
  cli_command: code
  cli_args:
    open_file: ["--goto", "{file}:{line}"]
    open_folder: ["{folder}"]

# 版本兼容性
version_compatibility:
  min_version: "1.80.0"
  known_breaking_versions: []

# 窗口特征
window_patterns:
  - "Visual Studio Code"
  - "* - Visual Studio Code"

# 关联 Skill 版本
skill_bindings:
  run_file: "vscode/run_file_v1"
  open_project: "vscode/open_project_v1"
```

### 5.2 Profile 管理器

```python
# apps/runtime/src/engines/app_profile.py

import yaml
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

@dataclass
class AutomationStrategy:
    preferred_method: str = "cli"
    cli_command: Optional[str] = None
    cli_args: dict = field(default_factory=dict)

@dataclass
class AppProfile:
    app_id: str
    display_name: str
    executable: str
    category: str
    automation: AutomationStrategy = field(default_factory=AutomationStrategy)
    min_version: Optional[str] = None
    known_breaking_versions: list[str] = field(default_factory=list)
    window_patterns: list[str] = field(default_factory=list)
    skill_bindings: dict[str, str] = field(default_factory=dict)

class AppProfileManager:
    """App Profile 管理器。"""
    
    def __init__(self, profile_dir: Path = None):
        self.profile_dir = profile_dir or Path("data/app_profiles")
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, AppProfile] = {}
    
    def load(self, app_id: str) -> Optional[AppProfile]:
        """加载应用 Profile。"""
        if app_id in self._cache:
            return self._cache[app_id]
        
        profile_path = self.profile_dir / f"{app_id}.yaml"
        if not profile_path.exists():
            return None
        
        with open(profile_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        profile = AppProfile(
            app_id=data["app_id"],
            display_name=data["display_name"],
            executable=data["executable"],
            category=data["category"],
            automation=AutomationStrategy(**data.get("automation", {})),
            min_version=data.get("version_compatibility", {}).get("min_version"),
            window_patterns=data.get("window_patterns", []),
            skill_bindings=data.get("skill_bindings", {}),
        )
        self._cache[app_id] = profile
        return profile
    
    def save(self, profile: AppProfile):
        """保存应用 Profile。"""
        profile_path = self.profile_dir / f"{profile.app_id}.yaml"
        with open(profile_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(self._to_dict(profile), f, default_flow_style=False, allow_unicode=True)
        self._cache[profile.app_id] = profile
    
    def _to_dict(self, profile: AppProfile) -> dict:
        return {
            "app_id": profile.app_id,
            "display_name": profile.display_name,
            "executable": profile.executable,
            "category": profile.category,
            "automation": {
                "preferred_method": profile.automation.preferred_method,
                "cli_command": profile.automation.cli_command,
                "cli_args": profile.automation.cli_args,
            },
            "version_compatibility": {
                "min_version": profile.min_version,
                "known_breaking_versions": profile.known_breaking_versions,
            },
            "window_patterns": profile.window_patterns,
            "skill_bindings": profile.skill_bindings,
        }
```

---

## 6. MCP 工具实现

### 6.1 app_list 工具

```python
# apps/runtime/src/mcp_tools/app_list.py

from ..engines.app_scanner import AppScanner

def handle_app_list() -> dict:
    """MCP 工具: 列出已安装应用。权限 L0。"""
    scanner = AppScanner()
    apps = scanner.scan()
    return {
        "success": True,
        "result": {
            "apps": [
                {
                    "app_id": app.app_id,
                    "display_name": app.display_name,
                    "category": app.category,
                    "version": app.version,
                }
                for app in apps
            ],
            "count": len(apps),
        }
    }
```

### 6.2 app_launch 工具

```python
# apps/runtime/src/mcp_tools/app_launch.py

from pathlib import Path
from ..engines.app_scanner import AppScanner
from ..engines.process_engine import ProcessEngine
from ..engines.app_profile import AppProfileManager

def handle_app_launch(app_id: str, args: list[str] = None) -> dict:
    """MCP 工具: 启动应用。权限 L2。"""
    scanner = AppScanner()
    app_info = scanner.get_app(app_id)
    if not app_info:
        return {"success": False, "error": {"code": "E5001", "message": f"应用 {app_id} 未找到"}}
    
    process_engine = ProcessEngine()
    
    # 检查是否已在运行
    if process_engine.is_process_running(app_info.executable_path.name):
        # 已在运行，激活窗口
        windows = process_engine.find_windows_by_title(app_info.display_name)
        if windows:
            process_engine.bring_window_to_front(windows[0]["hwnd"])
            return {"success": True, "result": {"action": "activated", "hwnd": windows[0]["hwnd"]}}
    
    # 启动应用
    result = process_engine.launch_app(app_info.executable_path, args)
    return result
```

---

## 7. MVP 预置 Profile

### 7.1 VSCode Profile

```yaml
# data/app_profiles/vscode.yaml
app_id: vscode
display_name: "Visual Studio Code"
executable: "Code.exe"
category: editor

automation:
  preferred_method: cli
  cli_command: code
  cli_args:
    open_file: ["--goto", "{file}:{line}"]
    open_folder: ["{folder}"]

window_patterns:
  - "Visual Studio Code"
  - "* - Visual Studio Code"

skill_bindings:
  run_file: "vscode/run_file_v1"
  open_project: "vscode/open_project_v1"
```

### 7.2 Chrome Profile

```yaml
# data/app_profiles/chrome.yaml
app_id: chrome
display_name: "Google Chrome"
executable: "chrome.exe"
category: browser

automation:
  preferred_method: cdp
  cli_command: null
  cli_args: {}

version_compatibility:
  min_version: "120.0"

window_patterns:
  - "Google Chrome"
  - "* - Google Chrome"

skill_bindings:
  search_doc: "chrome/search_doc_v1"
  extract_content: "chrome/extract_content_v1"
```

### 7.3 File Explorer Profile

```yaml
# data/app_profiles/file_explorer.yaml
app_id: file_explorer
display_name: "File Explorer"
executable: "explorer.exe"
category: file_manager

automation:
  preferred_method: filesystem
  cli_command: null
  cli_args: {}

window_patterns:
  - "File Explorer"
  - "*"

skill_bindings:
  archive_downloads: "file_explorer/archive_downloads_v1"
```

---

## 8. 实现步骤

| 序号 | 任务 | 预计耗时 | 依赖 |
|------|------|---------|------|
| 1 | 实现 AppScanner（注册表 + 快捷方式扫描） | 3h | M0 底座 |
| 2 | 实现 ProcessEngine | 3h | M0 底座 |
| 3 | 实现 AppProfileManager | 2h | 无 |
| 4 | 编写 MCP 工具: app_list | 1h | 1 |
| 5 | 编写 MCP 工具: app_launch | 1h | 1,2 |
| 6 | 编写 VSCode/Chrome/FileExplorer Profile | 1h | 3 |
| 7 | 单元测试（Scanner + ProcessEngine） | 2h | 1,2 |
| 8 | 集成测试（app_list + app_launch 贯穿） | 1h | 4,5 |
| 9 | 前端应用列表 UI | 2h | 4 |

---

## 9. 测试与验收标准

### 9.1 单元测试

- AppScanner: `test_scan_vscode`、`test_scan_chrome`、`test_scan_file_explorer`
- ProcessEngine: `test_find_process`、`test_find_window`、`test_launch_app`
- AppProfileManager: `test_load_profile`、`test_save_profile`

### 9.2 验收标准

- [ ] `AppScanner.scan()` 返回包含 VSCode/Chrome/FileExplorer 的列表
- [ ] `ProcessEngine.launch_app()` 可启动 VSCode 并返回 pid
- [ ] `ProcessEngine.is_process_running("Code.exe")` 在 VSCode 运行时返回 True
- [ ] `AppProfileManager.load("vscode")` 返回正确的 Profile
- [ ] MCP `app_list` 返回 JSON 格式的应用列表
- [ ] MCP `app_launch` 可启动 Chrome 并返回成功
- [ ] 窗口标题/进程映射准确率 >= 90%（3 个目标应用）

### 9.3 测试命令

```bash
cd apps/runtime && pytest -v -k "app_scanner or process_engine"
```

---

## 10. 交付物清单

| 交付物 | 路径 | 状态 |
|--------|------|------|
| AppScanner | apps/runtime/src/engines/app_scanner.py | - |
| ProcessEngine | apps/runtime/src/engines/process_engine.py | - |
| AppProfileManager | apps/runtime/src/engines/app_profile.py | - |
| MCP 工具: app_list | apps/runtime/src/mcp_tools/app_list.py | - |
| MCP 工具: app_launch | apps/runtime/src/mcp_tools/app_launch.py | - |
| VSCode Profile | data/app_profiles/vscode.yaml | - |
| Chrome Profile | data/app_profiles/chrome.yaml | - |
| File Explorer Profile | data/app_profiles/file_explorer.yaml | - |
| 单元测试 | apps/runtime/tests/test_app_*.py | - |

---

## 11. 风险与注意事项

| 风险 | 级别 | 应对 |
|------|------|------|
| 注册表权限不足（需管理员） | MEDIUM | 读取 Uninstall 项通常不需要管理员，如遇问题用快捷方式回退 |
| VSCode 安装路径多变（User Installer vs System） | MEDIUM | 扫描多个路径：Program Files、AppData/Local、注册表 |
| Chrome 多实例进程（每个 tab 一个进程） | LOW | 通过父进程 ID 和窗口标题判断主进程 |
| 高分屏/多显示器窗口坐标计算 | LOW | M1 暂不涉及窗口操作，M3 再处理 |
| pywin32 在虚拟环境中可能缺少 DLL | LOW | 使用 `pip install pywin32` 后运行 `python Scripts/pywin32_postinstall.py -install` |

---

## 12. 相关文档

- [../1-standards/00-project-overview.md](../1-standards/00-project-overview.md) - 全局规范
- [../2-milestones/01-m0-engineering-foundation.md](../2-milestones/01-m0-engineering-foundation.md) - 前置阶段
- [../2-milestones/03-m2-file-permission-audit.md](../2-milestones/03-m2-file-permission-audit.md) - 下一阶段
- [../0-specs/00-project-requirements.md](../0-specs/00-project-requirements.md) - 总文档
