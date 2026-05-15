import pytest
from src.engines.app_scanner import AppScanner


def test_scanner_returns_at_least_one_app():
    scanner = AppScanner()
    apps = scanner.scan()
    assert len(apps) >= 1
    app_ids = [app.app_id for app in apps]
    assert "file_explorer" in app_ids


def test_get_app_returns_info():
    scanner = AppScanner()
    app = scanner.get_app("file_explorer")
    assert app is not None
    assert app.app_id == "file_explorer"
    assert app.category == "file_manager"


def test_get_unknown_app():
    scanner = AppScanner()
    app = scanner.get_app("nonexistent")
    assert app is None
