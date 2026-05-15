import subprocess
import logging
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("runtime.process_engine")


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

    def launch_app(self, exe_path: Path, args: list[str] | None = None, wait_seconds: float = 3.0) -> dict:
        cmd = [str(exe_path)]
        if args:
            cmd.extend(args)

        logger.info(f"Launching app: {' '.join(cmd)}")

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(wait_seconds)

            if proc.poll() is not None:
                return {
                    "pid": proc.pid,
                    "success": False,
                    "error": f"Process exited with code {proc.returncode}",
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
