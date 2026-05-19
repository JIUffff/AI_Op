"""维护模块测试：备份、恢复、日志滚动。"""
import gzip
import json
import tempfile
from pathlib import Path

import pytest

from src.maintenance import (
    MAX_BACKUPS,
    backup_database,
    list_backups,
    maintenance_status,
    restore_database,
    rotate_logs,
)


@pytest.fixture
def temp_project(tmp_path: Path):
    """创建临时项目结构。"""
    db_dir = tmp_path / "data" / "db"
    db_dir.mkdir(parents=True)
    db_file = db_dir / "local-auto.db"
    db_file.write_text("fake db content")

    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(parents=True)

    backups_dir = tmp_path / "data" / "backups"
    backups_dir.mkdir(parents=True)

    data_dir = tmp_path / "data"
    (data_dir / "rollback_log.json").write_text("{}")

    return {
        "root": tmp_path,
        "db": db_file,
        "logs": logs_dir,
        "backups": backups_dir,
        "data": data_dir,
    }


@pytest.fixture(autouse=True)
def patch_paths(monkeypatch, temp_project):
    """重定向维护模块到临时目录。"""
    monkeypatch.setattr("src.maintenance.PROJECT_ROOT", temp_project["root"])
    monkeypatch.setattr("src.maintenance.DATA_DIR", temp_project["data"])
    monkeypatch.setattr("src.maintenance.DB_PATH", temp_project["db"])
    monkeypatch.setattr("src.maintenance.BACKUP_DIR", temp_project["backups"])
    monkeypatch.setattr("src.maintenance.LOG_DIR", temp_project["logs"])
    monkeypatch.setattr("src.maintenance.ROLLBACK_LOG", temp_project["data"] / "rollback_log.json")


class TestBackupDatabase:
    def test_backup_creates_gzip_file(self, temp_project):
        result = backup_database(temp_project["backups"])

        assert result["success"] is True
        assert result["backup_path"] is not None
        assert result["size_bytes"] > 0
        assert result["error"] is None

        backup_path = Path(result["backup_path"])
        assert backup_path.exists()
        assert backup_path.suffix == ".gz"

    def test_backup_compresses_content(self, temp_project):
        result = backup_database(temp_project["backups"])
        backup_path = Path(result["backup_path"])

        with gzip.open(backup_path, "rb") as f:
            content = f.read()
        assert content == b"fake db content"

    def test_backup_nonexistent_db(self, temp_project, monkeypatch):
        fake_db = temp_project["root"] / "nonexistent.db"
        monkeypatch.setattr("src.maintenance.DB_PATH", fake_db)

        result = backup_database(temp_project["backups"])
        assert result["success"] is False
        assert "不存在" in result["error"]

    def test_backup_cleanup_old_backups(self, temp_project):
        for i in range(MAX_BACKUPS + 3):
            backup_database(temp_project["backups"])

        remaining = list(temp_project["backups"].glob("*.db.gz"))
        assert len(remaining) <= MAX_BACKUPS


class TestRestoreDatabase:
    def test_restore_from_backup(self, temp_project):
        backup_result = backup_database(temp_project["backups"])
        original_content = temp_project["db"].read_text()

        temp_project["db"].write_text("corrupted")
        assert temp_project["db"].read_text() == "corrupted"

        result = restore_database(backup_result["backup_path"])
        assert result["success"] is True
        assert temp_project["db"].read_text() == original_content

    def test_restore_nonexistent_backup(self):
        result = restore_database("/nonexistent/path.db.gz")
        assert result["success"] is False
        assert "不存在" in result["error"]


class TestListBackups:
    def test_list_empty(self, temp_project):
        assert list_backups(temp_project["backups"]) == []

    def test_list_after_backup(self, temp_project):
        backup_database(temp_project["backups"])
        backups = list_backups(temp_project["backups"])

        assert len(backups) == 1
        assert backups[0]["filename"].endswith(".db.gz")
        assert backups[0]["size_bytes"] > 0
        assert "created" in backups[0]


class TestMaintenanceStatus:
    def test_status_returns_all_keys(self, temp_project):
        status = maintenance_status()

        assert "database" in status
        assert "backups" in status
        assert "logs" in status
        assert "rollback_log" in status

        assert isinstance(status["database"]["exists"], bool)
        assert isinstance(status["backups"]["count"], int)
        assert isinstance(status["logs"]["count"], int)


class TestRotateLogs:
    def test_rotate_small_logs_noop(self, temp_project):
        log_file = temp_project["logs"] / "app.log"
        log_file.write_text("small log content")

        result = rotate_logs(temp_project["logs"], max_size_mb=10)
        assert result["rotated"] == 0
        assert result["deleted"] == 0

    def test_rotate_large_log(self, temp_project):
        log_file = temp_project["logs"] / "app.log"
        large_content = "x" * (1024 * 1024 * 11)
        log_file.write_text(large_content)

        result = rotate_logs(temp_project["logs"], max_size_mb=10)
        assert result["rotated"] == 1
        assert result["total_size_after"] < result["total_size_before"]

        gz_files = list(temp_project["logs"].glob("*.log.gz"))
        assert len(gz_files) == 1

    def test_rotate_deletes_oldest(self, temp_project):
        for i in range(7):
            log_file = temp_project["logs"] / f"old_{i}.log.gz"
            log_file.write_text(f"old log {i}")

        result = rotate_logs(temp_project["logs"], max_files=5)
        remaining = list(temp_project["logs"].glob("*.log.gz"))
        assert len(remaining) == 5
        assert result["deleted"] == 2
