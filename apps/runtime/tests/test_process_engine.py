import pytest
from pathlib import Path
from src.engines.process_engine import ProcessEngine


class TestProcessEngine:
    def test_list_processes_returns_list(self):
        engine = ProcessEngine()
        procs = engine.list_processes()
        assert isinstance(procs, list)
        assert len(procs) > 0

    def test_list_processes_has_required_fields(self):
        engine = ProcessEngine()
        procs = engine.list_processes()
        if procs:
            proc = procs[0]
            assert "pid" in proc
            assert "name" in proc

    def test_find_process_by_name_explorer(self):
        engine = ProcessEngine()
        procs = engine.find_process_by_name("explorer.exe")
        assert len(procs) > 0

    def test_is_process_running_explorer(self):
        engine = ProcessEngine()
        assert engine.is_process_running("explorer.exe") is True

    def test_is_process_running_nonexistent(self):
        engine = ProcessEngine()
        assert engine.is_process_running("definitely_not_running_app_xyz.exe") is False

    def test_find_windows_by_title(self):
        engine = ProcessEngine()
        windows = engine.find_windows_by_title("")
        assert isinstance(windows, list)
        assert len(windows) > 0

    def test_find_windows_by_title_structure(self):
        engine = ProcessEngine()
        windows = engine.find_windows_by_title("")
        if windows:
            win = windows[0]
            assert "hwnd" in win
            assert "title" in win
            assert "pid" in win

    def test_launch_app_invalid_path(self):
        engine = ProcessEngine()
        result = engine.launch_app(Path(r"C:\nonexistent\app.exe"))
        assert result["success"] is False
        assert "error" in result
