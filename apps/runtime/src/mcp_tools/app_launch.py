from pathlib import Path
from ..engines.app_scanner import AppScanner
from ..engines.process_engine import ProcessEngine
import logging

logger = logging.getLogger("runtime.mcp_tools.app_launch")


def handle_app_launch(app_id: str, args: list[str] | None = None) -> dict:
    """MCP 工具: 启动应用。权限 L2。"""
    scanner = AppScanner()
    app_info = scanner.get_app(app_id)
    if not app_info:
        return {
            "success": False,
            "error": {
                "code": "E5001",
                "message": f"App {app_id} not found",
            },
        }

    process_engine = ProcessEngine()
    exe_name = app_info.executable_path.name

    if process_engine.is_process_running(exe_name):
        windows = process_engine.find_windows_by_title(app_info.display_name)
        if windows:
            process_engine.bring_window_to_front(windows[0]["hwnd"])
            return {
                "success": True,
                "result": {
                    "action": "activated",
                    "hwnd": windows[0]["hwnd"],
                    "pid": windows[0]["pid"],
                },
            }

    result = process_engine.launch_app(app_info.executable_path, args)
    return result
