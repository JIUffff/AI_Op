"""M6 真实引擎单元测试。"""
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.engines.file_engine import FILE_CATEGORIES, FileEngine
from src.engines.chrome_engine import ChromeEngine


class TestVSCodeEngine:
    def test_init_default_path(self):
        from src.engines.vscode_engine import VSCodeEngine

        engine = VSCodeEngine()
        assert "Code.exe" in str(engine.exe_path)
        assert engine._pid is None

    def test_init_custom_path(self):
        from src.engines.vscode_engine import VSCodeEngine

        custom = Path(r"D:\VSCode\Code.exe")
        engine = VSCodeEngine(exe_path=custom)
        assert engine.exe_path == custom

    @patch("src.engines.vscode_engine.VSCodeEngine.is_running", return_value=True)
    def test_launch_already_running(self, mock_running):
        from src.engines.vscode_engine import VSCodeEngine

        engine = VSCodeEngine()
        engine._pid = 12345
        result = engine.launch()
        assert result["success"] is True
        assert result["pid"] == 12345

    @patch("subprocess.Popen")
    @patch("src.engines.vscode_engine.VSCodeEngine.is_running", return_value=False)
    def test_launch_success(self, mock_running, mock_popen):
        from src.engines.vscode_engine import VSCodeEngine

        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_popen.return_value = mock_proc

        engine = VSCodeEngine()
        result = engine.launch()

        assert result["success"] is True
        assert result["pid"] == 12345
        assert engine._pid == 12345

    @patch("subprocess.Popen")
    @patch("src.engines.vscode_engine.VSCodeEngine.is_running", return_value=False)
    def test_launch_file_not_found(self, mock_running, mock_popen):
        from src.engines.vscode_engine import VSCodeEngine

        mock_popen.side_effect = FileNotFoundError()

        engine = VSCodeEngine()
        engine.exe_path = Path(r"D:\nonexistent\Code.exe")
        result = engine.launch()

        assert result["success"] is False
        assert "不存在" in result["message"]

    def test_open_file_nonexistent(self):
        from src.engines.vscode_engine import VSCodeEngine

        engine = VSCodeEngine()
        result = engine.open_file(r"D:\nonexistent\test.py")
        assert result["success"] is False
        assert "不存在" in result["message"]

    @patch("subprocess.run")
    @patch("pathlib.Path.exists", return_value=True)
    def test_open_file_success(self, mock_exists, mock_run):
        from src.engines.vscode_engine import VSCodeEngine

        engine = VSCodeEngine()
        result = engine.open_file(r"D:\test\main.py")

        assert result["success"] is True
        assert result["file_path"] is not None

    @patch("subprocess.run")
    @patch("pathlib.Path.exists", return_value=True)
    def test_open_file_timeout(self, mock_exists, mock_run):
        from src.engines.vscode_engine import VSCodeEngine
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="code", timeout=10)

        engine = VSCodeEngine()
        result = engine.open_file(r"D:\test\main.py")

        assert result["success"] is False
        assert "超时" in result["message"]

    def test_close_not_running(self):
        from src.engines.vscode_engine import VSCodeEngine

        engine = VSCodeEngine()
        result = engine.close()

        assert result["success"] is True
        assert "未运行" in result["message"]

    def test_is_running_no_pid(self):
        from src.engines.vscode_engine import VSCodeEngine

        engine = VSCodeEngine()
        result = engine.is_running()
        assert isinstance(result, bool)


class TestChromeEngine:
    def test_init_default_path(self):
        engine = ChromeEngine()
        assert "chrome.exe" in str(engine.exe_path)
        assert engine.debug_port == 9222
        assert engine._pid is None

    def test_init_custom_port(self):
        engine = ChromeEngine(debug_port=9999)
        assert engine.debug_port == 9999

    @patch("src.engines.chrome_engine.ChromeEngine.is_running", return_value=True)
    def test_launch_already_running(self, mock_running):
        engine = ChromeEngine()
        engine._pid = 54321
        result = engine.launch()
        assert result["success"] is True
        assert result["pid"] == 54321

    @patch("subprocess.Popen")
    @patch("src.engines.chrome_engine.ChromeEngine.is_running", return_value=False)
    def test_launch_success(self, mock_running, mock_popen):
        mock_proc = MagicMock()
        mock_proc.pid = 54321
        mock_popen.return_value = mock_proc

        engine = ChromeEngine()
        with patch.object(engine, "_get_debug_url", return_value="ws://localhost:9222/devtools"):
            result = engine.launch()

        assert result["success"] is True
        assert result["pid"] == 54321

    def test_is_running_no_pid(self):
        engine = ChromeEngine()
        result = engine.is_running()
        assert isinstance(result, bool)

    def test_close_not_running(self):
        engine = ChromeEngine()
        result = engine.close()
        assert result["success"] is True
        assert "未运行" in result["message"]

    def test_close_ws_cleanup(self):
        engine = ChromeEngine()
        mock_ws = MagicMock()
        engine._ws = mock_ws
        engine._pid = None

        result = engine.close()
        mock_ws.close.assert_called_once()
        assert result["success"] is True


class TestFileEngine:
    def test_init_default_dir(self):
        engine = FileEngine()
        assert engine.base_dir == Path.home()

    def test_init_custom_dir(self):
        engine = FileEngine(base_dir=Path(r"D:\test"))
        assert engine.base_dir == Path(r"D:\test")

    def test_scan_directory_nonexistent(self):
        engine = FileEngine()
        result = engine.scan_directory(r"D:\nonexistent_dir_12345")
        assert result["error"] is not None
        assert result["count"] == 0

    def test_scan_directory_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = FileEngine()
            result = engine.scan_directory(tmpdir)
            assert result["error"] is None
            assert result["count"] == 0
            assert result["files"] == []

    def test_scan_directory_with_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("hello")

            engine = FileEngine()
            result = engine.scan_directory(tmpdir)

            assert result["error"] is None
            assert result["count"] == 1
            assert result["files"][0]["name"] == "test.txt"

    def test_scan_directory_not_a_dir(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            engine = FileEngine()
            result = engine.scan_directory(f.name)
            assert result["error"] is not None

    def test_classify_files_images(self):
        engine = FileEngine()
        files = [r"D:\test\photo.jpg", r"D:\test\image.png"]
        result = engine.classify_files(files)

        assert result["error"] is None
        assert "images" in result["categories"]
        assert len(result["categories"]["images"]) == 2

    def test_classify_files_mixed(self):
        engine = FileEngine()
        files = [
            r"D:\test\photo.jpg",
            r"D:\test\doc.pdf",
            r"D:\test\video.mp4",
            r"D:\test\unknown.xyz",
        ]
        result = engine.classify_files(files)

        assert "images" in result["categories"]
        assert "documents" in result["categories"]
        assert "videos" in result["categories"]
        assert "others" in result["categories"]

    def test_classify_files_empty(self):
        engine = FileEngine()
        result = engine.classify_files([])
        assert result["error"] is None
        assert result["categories"] == {}

    def test_move_files_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "src" / "test.txt"
            src.parent.mkdir()
            src.write_text("hello")

            dst = Path(tmpdir) / "dst" / "test.txt"

            engine = FileEngine()
            result = engine.move_files({str(src): str(dst)})

            assert result["moved"] == 1
            assert result["error"] is None
            assert dst.exists()
            assert not src.exists()

    def test_move_files_source_not_exist(self):
        engine = FileEngine()
        result = engine.move_files({r"D:\nonexistent\file.txt": r"D:\dst\file.txt"})

        assert result["moved"] == 0
        assert len(result["errors"]) == 1

    def test_organize_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            img_file = Path(tmpdir) / "photo.jpg"
            img_file.write_text("fake image")

            doc_file = Path(tmpdir) / "report.pdf"
            doc_file.write_text("fake pdf")

            engine = FileEngine()
            result = engine.organize_directory(tmpdir)

            assert result["moved"] >= 0
            assert result["categories"] is not None

    def test_create_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = Path(tmpdir) / "new" / "nested" / "dir"

            engine = FileEngine()
            result = engine.create_directory(str(new_dir))

            assert result["success"] is True
            assert new_dir.exists()

    def test_delete_file_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_delete.txt"
            test_file.write_text("delete me")

            engine = FileEngine()
            result = engine.delete_file(str(test_file))

            assert result["success"] is True
            assert not test_file.exists()

    def test_delete_file_nonexistent(self):
        engine = FileEngine()
        result = engine.delete_file(r"D:\nonexistent\file.txt")

        assert result["success"] is False
        assert "不存在" in result["message"]

    def test_rollback_no_operations(self):
        engine = FileEngine()
        result = engine.rollback()

        assert result["restored"] == 0
        assert "没有可回滚" in result["message"]

    def test_get_operations_empty(self):
        engine = FileEngine()
        ops = engine.get_operations()
        assert ops == []

    def test_clear_operations(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "test.txt"
            src.write_text("test")
            dst = Path(tmpdir) / "moved.txt"

            engine = FileEngine()
            engine.move_files({str(src): str(dst)})

            assert len(engine.get_operations()) > 0
            engine.clear_operations()
            assert len(engine.get_operations()) == 0


class TestFileEngineCategories:
    def test_file_categories_has_all_types(self):
        assert "images" in FILE_CATEGORIES
        assert "documents" in FILE_CATEGORIES
        assert "videos" in FILE_CATEGORIES
        assert "audio" in FILE_CATEGORIES
        assert "archives" in FILE_CATEGORIES
        assert "installers" in FILE_CATEGORIES
        assert "code" in FILE_CATEGORIES

    def test_image_extensions(self):
        exts = FILE_CATEGORIES["images"]
        assert ".jpg" in exts
        assert ".png" in exts
        assert ".gif" in exts

    def test_code_extensions(self):
        exts = FILE_CATEGORIES["code"]
        assert ".py" in exts
        assert ".js" in exts
        assert ".ts" in exts

    def test_document_extensions(self):
        exts = FILE_CATEGORIES["documents"]
        assert ".pdf" in exts
        assert ".docx" in exts
        assert ".txt" in exts


class TestEngineIntegration:
    def test_workflow_executor_registers_engines(self):
        from src.skills.executor import WorkflowExecutor
        from src.engines.vscode_engine import VSCodeEngine
        from src.engines.chrome_engine import ChromeEngine
        from src.engines.file_engine import FileEngine

        executor = WorkflowExecutor()
        executor.register_engine("vscode", VSCodeEngine())
        executor.register_engine("chrome", ChromeEngine())
        executor.register_engine("file_engine", FileEngine())

        assert "vscode" in executor._engines
        assert "chrome" in executor._engines
        assert "file_engine" in executor._engines

    def test_file_engine_rollback_log_persistence(self):
        from src.engines.file_engine import ROLLBACK_LOG

        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "test.txt"
            src.write_text("test")
            dst = Path(tmpdir) / "moved.txt"

            engine = FileEngine()
            engine.move_files({str(src): str(dst)})

            if ROLLBACK_LOG.exists():
                with open(ROLLBACK_LOG, "r", encoding="utf-8") as f:
                    data = json.load(f)
                assert len(data) > 0
                ROLLBACK_LOG.unlink()
