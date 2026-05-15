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

        exe = self._find_via_registry(config)
        if exe and exe.exists():
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
                for top_dir in search_dir.iterdir():
                    if not top_dir.is_dir():
                        continue
                    try:
                        found = list(top_dir.glob(exe_name))
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

    def _find_via_registry(self, config: dict) -> Optional[Path]:
        if sys.platform != "win32":
            return None

        try:
            import winreg
        except ImportError:
            return None

        exe_names = config.get("executable_names", [])

        registry_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]

        for hkey, subkey in registry_paths:
            try:
                key = winreg.OpenKey(hkey, subkey)
                i = 0
                while True:
                    try:
                        app_key_name = winreg.EnumKey(key, i)
                        i += 1
                    except OSError:
                        break

                    try:
                        app_key = winreg.OpenKey(key, app_key_name)
                        display_name = winreg.QueryValueEx(app_key, "DisplayName")[0]
                        install_loc = winreg.QueryValueEx(app_key, "InstallLocation")[0]

                        if any(name.lower() in display_name.lower() for name in exe_names):
                            winreg.CloseKey(app_key)
                            install_path = Path(install_loc)
                            for exe_name in exe_names:
                                exe_path = install_path / exe_name
                                if exe_path.exists():
                                    return exe_path
                        winreg.CloseKey(app_key)
                    except (OSError, FileNotFoundError):
                        continue

                winreg.CloseKey(key)
            except OSError:
                continue

        return None
