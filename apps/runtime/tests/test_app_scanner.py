import pytest
from pathlib import Path
from src.engines.app_scanner import AppScanner, KNOWN_APPS


class TestAppScanner:
    def test_scan_returns_list(self):
        scanner = AppScanner()
        apps = scanner.scan()
        assert isinstance(apps, list)
        assert len(apps) > 0

    def test_scan_includes_file_explorer(self):
        scanner = AppScanner()
        apps = scanner.scan()
        app_ids = [app.app_id for app in apps]
        assert "file_explorer" in app_ids

    def test_get_app_file_explorer(self):
        scanner = AppScanner()
        app = scanner.get_app("file_explorer")
        assert app is not None
        assert app.app_id == "file_explorer"
        assert app.display_name == "File Explorer"
        assert app.executable_path == Path(r"C:\Windows\explorer.exe")

    def test_get_app_not_found(self):
        scanner = AppScanner()
        app = scanner.get_app("nonexistent_app")
        assert app is None

    def test_app_info_fields(self):
        scanner = AppScanner()
        apps = scanner.scan()
        if apps:
            app = apps[0]
            assert app.app_id
            assert app.display_name
            assert app.executable_path
            assert isinstance(app.supports_cli, bool)
            assert isinstance(app.supports_cdp, bool)

    def test_known_apps_structure(self):
        assert "vscode" in KNOWN_APPS
        assert "chrome" in KNOWN_APPS
        assert "file_explorer" in KNOWN_APPS

        for app_id, config in KNOWN_APPS.items():
            assert "display_name" in config
            assert "category" in config
