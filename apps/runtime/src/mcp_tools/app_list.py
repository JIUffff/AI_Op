from ..engines.app_scanner import AppScanner
from ..engines.process_engine import ProcessEngine
import logging

logger = logging.getLogger("runtime.mcp_tools.app_list")


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
                    "supports_cli": app.supports_cli,
                    "supports_cdp": app.supports_cdp,
                }
                for app in apps
            ],
            "count": len(apps),
        }
    }
