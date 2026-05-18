"""VSCode UIA 引擎：通过 Windows UI Automation 控制 VSCode。"""
import logging
import subprocess
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("runtime.engines.vscode_engine")

DEFAULT_VSCODE_PATH = Path(
    r"C:\Users\Admin\AppData\Local\Programs\Microsoft VS Code\Code.exe"
)
DEFAULT_CODE_CLI = Path(
    r"C:\Users\Admin\AppData\Local\Programs\Microsoft VS Code\bin\code.cmd"
)


class VSCodeEngine:
    """VSCode 控制引擎。

    优先使用 CLI（code.cmd）进行文件操作，UIA 作为辅助手段。
    """

    def __init__(self, exe_path: Optional[Path] = None) -> None:
        self.exe_path = exe_path or DEFAULT_VSCODE_PATH
        self._pid: Optional[int] = None

    def _find_vscode_window(self) -> Optional[int]:
        """查找 VSCode 窗口句柄。"""
        try:
            import win32gui
            import win32process

            results = []

            def callback(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if "Visual Studio Code" in title or title.endswith(" - Visual Studio Code"):
                        _, pid = win32process.GetWindowThreadProcessId(hwnd)
                        if pid == self._pid:
                            results.append(hwnd)
                return True

            win32gui.EnumWindows(callback, None)
            return results[0] if results else None
        except ImportError:
            logger.warning("pywin32 not available")
            return None

    def _bring_window_to_front(self, hwnd: int) -> bool:
        """将窗口前置。"""
        try:
            import win32gui

            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, 9)
            win32gui.SetForegroundWindow(hwnd)
            return True
        except Exception as e:
            logger.error(f"Failed to bring window to front: {e}")
            return False

    def launch(self, folder: str = "") -> dict:
        """启动 VSCode。

        参数：
            folder: 可选，打开的文件夹路径

        返回：
            {"pid": int, "success": bool, "error": str | None}
        """
        if self.is_running():
            logger.info("VSCode is already running")
            return {
                "pid": self._pid,
                "success": True,
                "error": None,
                "message": "VSCode 已在运行中",
            }

        cmd = [str(self.exe_path)]
        if folder:
            cmd.append(folder)

        logger.info(f"Launching VSCode: {' '.join(cmd)}")
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._pid = proc.pid
            time.sleep(2)
            return {
                "pid": self._pid,
                "success": True,
                "error": None,
                "message": "VSCode 启动成功",
            }
        except FileNotFoundError:
            return {
                "pid": None,
                "success": False,
                "error": f"VSCode 未找到: {self.exe_path}",
                "message": "VSCode 可执行文件不存在",
            }
        except Exception as e:
            return {
                "pid": None,
                "success": False,
                "error": str(e),
                "message": f"VSCode 启动失败: {e}",
            }

    def open_file(self, file_path: str) -> dict:
        """在 VSCode 中打开文件。

        使用 CLI（code.cmd）方式打开，更可靠。

        参数：
            file_path: 文件绝对路径

        返回：
            {"success": bool, "error": str | None, "message": str}
        """
        resolved = Path(file_path).resolve()
        if not resolved.exists():
            return {
                "success": False,
                "error": f"文件不存在: {resolved}",
                "message": "文件不存在",
            }

        cli_path = DEFAULT_CODE_CLI
        if cli_path.exists():
            cmd = [str(cli_path), str(resolved)]
            if self._pid:
                cmd.extend(["--reuse-window"])
        else:
            cmd = [str(self.exe_path), str(resolved), "--reuse-window"]

        logger.info(f"Opening file in VSCode: {resolved}")
        try:
            subprocess.run(
                cmd,
                timeout=10,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(1)

            hwnd = self._find_vscode_window()
            if hwnd:
                self._bring_window_to_front(hwnd)

            return {
                "success": True,
                "error": None,
                "message": f"文件已打开: {resolved.name}",
                "file_path": str(resolved),
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "打开文件超时",
                "message": "操作超时",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"打开文件失败: {e}",
            }

    def run_file(self) -> dict:
        """运行当前打开的文件。

        注意：依赖 VSCode 的 Code Runner 插件（快捷键 Ctrl+Alt+N）。
        如果未安装插件，此方法将静默触发快捷键但可能无输出。

        返回：
            {"success": bool, "output": str, "error": str | None}
        """
        try:
            import pywinauto
            from pywinauto.keyboard import send_keys

            hwnd = self._find_vscode_window()
            if not hwnd:
                return {
                    "success": False,
                    "output": "",
                    "error": "未找到 VSCode 窗口",
                    "message": "请先打开文件",
                }

            self._bring_window_to_front(hwnd)
            time.sleep(0.5)

            send_keys("^%n")
            time.sleep(2)

            output = self.get_output()

            return {
                "success": True,
                "output": output.get("output", ""),
                "error": None,
                "message": "文件执行已触发",
            }
        except ImportError:
            return {
                "success": False,
                "output": "",
                "error": "pywinauto 未安装",
                "message": "请安装 pywinauto",
            }
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": str(e),
                "message": f"运行文件失败: {e}",
            }

    def get_output(self) -> dict:
        """获取终端输出。

        使用 UIA 获取终端面板内容。

        返回：
            {"output": str, "success": bool, "error": str | None}
        """
        try:
            import pywinauto
            from pywinauto import Desktop

            app = pywinauto.Application(backend="uia").connect(process=self._pid)
            window = app.window()

            terminal = window.child_window(
                control_type="Pane",
                title_re=".*TERMINAL.*|.*终端.*",
            )

            if terminal.exists(timeout=2):
                text = terminal.window_text()
                return {
                    "output": text,
                    "success": True,
                    "error": None,
                }

            return {
                "output": "",
                "success": True,
                "error": None,
                "message": "终端面板未找到",
            }
        except ImportError:
            return {
                "output": "",
                "success": False,
                "error": "pywinauto 未安装",
            }
        except Exception as e:
            return {
                "output": "",
                "success": True,
                "error": None,
                "message": f"获取输出失败: {e}",
            }

    def is_running(self) -> bool:
        """检查 VSCode 是否正在运行。"""
        try:
            import psutil

            if self._pid:
                try:
                    proc = psutil.Process(self._pid)
                    return proc.is_running() and proc.name().lower() == "code.exe"
                except psutil.NoSuchProcess:
                    return False

            for proc in psutil.process_iter(["name", "exe"]):
                try:
                    exe = proc.info.get("exe", "")
                    if exe and "code.exe" in str(exe).lower():
                        self._pid = proc.pid
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return False
        except ImportError:
            return False

    def close(self) -> dict:
        """关闭 VSCode。

        返回：
            {"success": bool, "error": str | None}
        """
        if not self._pid:
            return {
                "success": True,
                "error": None,
                "message": "VSCode 未运行",
            }

        try:
            import psutil

            proc = psutil.Process(self._pid)
            proc.terminate()
            proc.wait(timeout=5)
            self._pid = None
            return {
                "success": True,
                "error": None,
                "message": "VSCode 已关闭",
            }
        except psutil.NoSuchProcess:
            self._pid = None
            return {
                "success": True,
                "error": None,
                "message": "VSCode 已关闭",
            }
        except psutil.TimeoutExpired:
            try:
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(self._pid)],
                    capture_output=True,
                    timeout=5,
                )
                self._pid = None
                return {
                    "success": True,
                    "error": None,
                    "message": "VSCode 已强制关闭",
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "message": f"关闭 VSCode 失败: {e}",
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"关闭 VSCode 失败: {e}",
            }
