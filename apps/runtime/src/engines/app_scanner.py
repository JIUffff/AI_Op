from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import subprocess
import logging
import sys

logger = logging.getLogger("runtime.app_scanner")

KNOWN_APPS = {
    "vscode": {
        "display_name": "Visual Studio Code",
        "executable_names": ["Code.exe"],
        "category": "editor",
        "supports_cli": True,
        "cli_command": "code",
    },
    "chrome": {
        "display_name": "Google Chrome",
        "executable_names": ["chrome.exe"],
        "category": "browser",
        "supports_cdp": True,
        "cdp_port": 9222,
    },
    "file_explorer": {
        "display_name": "File Explorer",
        "executable_names": ["explorer.exe"],
        "category": "file_manager",
        "executable_path": Path(r"C:\Windows\explorer.exe"),
    },
}


@dataclass
class AppInfo:
    app_id: str
    display_name: str
    executable_path: Path
    icon_path: Optional[Path] = None
    install_location: Optional[Path] = None
    version: Optional[str] = None
    launch_args: list[str] = field(default_factory=list)
    category: str = ""
    supports_cli: bool = False
    cli_command: Optional[str] = None
    supports_cdp: bool = False
    cdp_port: Optional[int] = None


class AppScanner:
    def __init__(self):
        self._cache: dict[str, AppInfo] = {}

    def scan(self) -> list[AppInfo]:
        results = []
        for app_id, config in KNOWN_APPS.items():
            info = self._resolve_app(app_id, config)
            if info:
                results.append(info)
                self._cache[app_id] = info
        return results

    def get_app(self, app_id: str) -> Optional[AppInfo]:
        if app_id not in self._cache:
            config = KNOWN_APPS.get(app_id)
            if config:
                self._cache[app_id] = self._resolve_app(app_id, config)
        return self._cache.get(app_id)

    def _resolve_app(self, app_id: str, config: dict) -> Optional[AppInfo]:
        if "executable_path" in config:
            exe = Path(config["executable_path"])
            if exe.exists():
                return AppInfo(
                    app_id=app_id,
                    display_name=config["display_name"],
                    executable_path=exe,
                    install_location=exe.parent,
                    category=config.get("category", ""),
                    supports_cli=config.get("supports_cli", False),
                    cli_command=config.get("cli_command"),
                    supports_cdp=config.get("supports_cdp", False),
                    cdp_port=config.get("cdp_port"),
                )

        for exe_name in config.get("executable_names", []):
            for search_dir in [
                Path(r"C:\Program Files"),
                Path(r"C:\Program Files (x86)"),
                Path.home() / "AppData" / "Local",
            ]:
                if not search_dir.exists():
                    continue
                try:
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
                except (OSError, PermissionError):
                    continue

        logger.warning(f"App not found: {app_id}")
        return None
