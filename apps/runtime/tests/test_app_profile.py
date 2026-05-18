import pytest
import tempfile
from pathlib import Path
from src.engines.app_profile import AppProfileManager, AppProfile, AutomationStrategy


class TestAppProfileManager:
    def test_load_vscode_profile(self):
        pm = AppProfileManager()
        profile = pm.load("vscode")
        assert profile is not None
        assert profile.app_id == "vscode"
        assert profile.display_name == "Visual Studio Code"
        assert profile.category == "editor"

    def test_load_chrome_profile(self):
        pm = AppProfileManager()
        profile = pm.load("chrome")
        assert profile is not None
        assert profile.app_id == "chrome"
        assert profile.category == "browser"
        assert profile.automation.preferred_method == "cdp"

    def test_load_file_explorer_profile(self):
        pm = AppProfileManager()
        profile = pm.load("file_explorer")
        assert profile is not None
        assert profile.app_id == "file_explorer"
        assert profile.category == "file_manager"
        assert profile.automation.preferred_method == "filesystem"

    def test_load_nonexistent_profile(self):
        pm = AppProfileManager()
        profile = pm.load("nonexistent")
        assert profile is None

    def test_profile_automation_strategy(self):
        pm = AppProfileManager()
        profile = pm.load("vscode")
        assert profile.automation.preferred_method == "cli"
        assert profile.automation.cli_command == "code"
        assert "open_file" in profile.automation.cli_args

    def test_profile_window_patterns(self):
        pm = AppProfileManager()
        profile = pm.load("vscode")
        assert len(profile.window_patterns) > 0
        assert "Visual Studio Code" in profile.window_patterns

    def test_profile_skill_bindings(self):
        pm = AppProfileManager()
        profile = pm.load("vscode")
        assert len(profile.skill_bindings) > 0
        assert "run_file" in profile.skill_bindings

    def test_save_and_load_profile(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = AppProfileManager(profile_dir=Path(tmpdir))
            
            profile = AppProfile(
                app_id="test_app",
                display_name="Test App",
                executable="test.exe",
                category="test",
                automation=AutomationStrategy(
                    preferred_method="cli",
                    cli_command="test",
                ),
                window_patterns=["Test Window"],
            )
            pm.save(profile)
            
            loaded = pm.load("test_app")
            assert loaded is not None
            assert loaded.app_id == "test_app"
            assert loaded.automation.cli_command == "test"

    def test_list_all_profiles(self):
        pm = AppProfileManager()
        profiles = pm.list_all()
        assert isinstance(profiles, list)
        assert len(profiles) >= 3  # vscode, chrome, file_explorer

    def test_profile_caching(self):
        pm = AppProfileManager()
        profile1 = pm.load("vscode")
        profile2 = pm.load("vscode")
        assert profile1 is profile2  # Same object from cache
