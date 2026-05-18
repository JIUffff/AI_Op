import subprocess
import logging
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("runtime.process_engine")

LAUNCH_TIMEOUT = 15.0
POLL_INTERVAL = 0.5


class ProcessEngine:
    def list_processes(self) -> list[dict]:
        try:
            import psutil
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
        except ImportError:
            return []

    def find_process_by_name(self, name: str) -> list[dict]:
        return [p for p in self.list_processes() if p.get("name") and name.lower() in p["name"].lower()]

    def find_windows_by_title(self, title_contains: str) -> list[dict]:
        try:
            import win32gui
            import win32process
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
        except ImportError:
            logger.warning("pywin32 not available, window search disabled")
            return []

    def bring_window_to_front(self, hwnd: int) -> bool:
        try:
            import win32gui
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, 9)  # SW_RESTORE
            win32gui.SetForegroundWindow(hwnd)
            return True
        except (ImportError, Exception) as e:
            logger.error(f"Failed to bring window to front: {e}")
            return False

    def launch_app(self, exe_path: Path, args: list[str] | None = None, wait_seconds: float = 3.0) -> dict:
        cmd = [str(exe_path)]
        if args:
            cmd.extend(args)

        exe_name = exe_path.name.lower()
        logger.info(f"Launching app: {' '.join(cmd)}")

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            actual_wait = min(wait_seconds, LAUNCH_TIMEOUT)
            elapsed = 0.0
            while elapsed < actual_wait:
                time.sleep(POLL_INTERVAL)
                elapsed += POLL_INTERVAL
                if proc.poll() is not None:
                    if exe_name == "explorer.exe" and proc.returncode == 1:
                        logger.info("explorer.exe spawned successfully (exit code 1 is normal)")
                        return {
                            "pid": proc.pid,
                            "success": True,
                            "error": None,
                        }
                    return {
                        "pid": proc.pid,
                        "success": False,
                        "error": f"Process exited with code {proc.returncode} after {elapsed:.1f}s",
                    }

            return {
                "pid": proc.pid,
                "success": True,
                "error": None,
            }
        except FileNotFoundError:
            return {"pid": None, "success": False, "error": f"Executable not found: {exe_path}"}
        except Exception as e:
            return {"pid": None, "success": False, "error": str(e)}

    def is_process_running(self, exe_name: str) -> bool:
        return len(self.find_process_by_name(exe_name)) > 0

    def kill_process(self, pid: int) -> dict:
        try:
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], check=True, capture_output=True)
            return {"success": True, "error": None}
        except subprocess.CalledProcessError as e:
            return {"success": False, "error": e.stderr.decode()}
