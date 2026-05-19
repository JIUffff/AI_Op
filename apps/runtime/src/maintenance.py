"""运维工具：数据库备份和日志滚动。"""
import gzip
import json
import logging
import shutil
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("runtime.maintenance")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "db" / "local-auto.db"
BACKUP_DIR = DATA_DIR / "backups"
LOG_DIR = PROJECT_ROOT / "logs"
ROLLBACK_LOG = DATA_DIR / "rollback_log.json"

MAX_BACKUPS = 7
MAX_LOG_SIZE_MB = 10
MAX_LOG_FILES = 5


def backup_database(backup_dir: Path = BACKUP_DIR, max_backups: int = MAX_BACKUPS) -> dict:
    """备份 SQLite 数据库到带时间戳的 gzip 文件。

    参数：
        backup_dir: 备份存储目录
        max_backups: 保留的最大备份数量

    返回：
        {"success": bool, "backup_path": str, "size_bytes": int, "error": str | None}
    """
    backup_dir.mkdir(parents=True, exist_ok=True)

    if not DB_PATH.exists():
        return {
            "success": False,
            "backup_path": None,
            "size_bytes": 0,
            "error": f"数据库不存在: {DB_PATH}",
        }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"local-auto_{timestamp}.db.gz"
    backup_path = backup_dir / backup_name

    try:
        with open(DB_PATH, "rb") as f_in:
            with gzip.open(backup_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

        size = backup_path.stat().st_size
        logger.info(f"Database backed up: {backup_path} ({size} bytes)")

        _cleanup_old_backups(backup_dir, max_backups)

        return {
            "success": True,
            "backup_path": str(backup_path),
            "size_bytes": size,
            "error": None,
        }
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        return {
            "success": False,
            "backup_path": None,
            "size_bytes": 0,
            "error": str(e),
        }


def restore_database(backup_path: str) -> dict:
    """从备份恢复数据库。

    参数：
        backup_path: 备份文件路径（.gz 格式）

    返回：
        {"success": bool, "restored_path": str, "error": str | None}
    """
    backup_file = Path(backup_path)
    if not backup_file.exists():
        return {
            "success": False,
            "restored_path": None,
            "error": f"备份文件不存在: {backup_path}",
        }

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    try:
        with gzip.open(backup_file, "rb") as f_in:
            with open(DB_PATH, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

        logger.info(f"Database restored from {backup_path}")
        return {
            "success": True,
            "restored_path": str(DB_PATH),
            "error": None,
        }
    except Exception as e:
        logger.error(f"Restore failed: {e}")
        return {
            "success": False,
            "restored_path": None,
            "error": str(e),
        }


def list_backups(backup_dir: Path = BACKUP_DIR) -> list[dict]:
    """列出所有可用备份。"""
    if not backup_dir.exists():
        return []

    backups = []
    for f in sorted(backup_dir.glob("*.db.gz"), reverse=True):
        stat = f.stat()
        backups.append({
            "filename": f.name,
            "path": str(f),
            "size_bytes": stat.st_size,
            "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        })
    return backups


def rotate_logs(log_dir: Path = LOG_DIR, max_size_mb: int = MAX_LOG_SIZE_MB, max_files: int = MAX_LOG_FILES) -> dict:
    """滚动日志文件，超过大小限制时压缩旧日志。

    参数：
        log_dir: 日志目录
        max_size_mb: 单个日志文件最大大小（MB）
        max_files: 保留的最大日志文件数量

    返回：
        {"rotated": int, "deleted": int, "total_size_before": int, "total_size_after": int}
    """
    log_dir.mkdir(parents=True, exist_ok=True)

    rotated = 0
    deleted = 0
    total_size_before = 0
    total_size_after = 0

    max_size_bytes = max_size_mb * 1024 * 1024

    for log_file in log_dir.glob("*.log"):
        total_size_before += log_file.stat().st_size

        if log_file.stat().st_size > max_size_bytes:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            rotated_name = f"{log_file.stem}_{timestamp}.log.gz"
            rotated_path = log_dir / rotated_name

            try:
                with open(log_file, "rb") as f_in:
                    with gzip.open(rotated_path, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)

                log_file.write_text("")
                rotated += 1
                logger.info(f"Rotated {log_file} -> {rotated_path}")
            except Exception as e:
                logger.error(f"Failed to rotate {log_file}: {e}")

    all_logs = sorted(log_dir.glob("*.log.gz"), key=lambda f: f.stat().st_mtime)
    while len(all_logs) > max_files:
        oldest = all_logs.pop(0)
        oldest.unlink()
        deleted += 1
        logger.info(f"Deleted old log: {oldest}")

    for f in log_dir.glob("*.log*"):
        total_size_after += f.stat().st_size

    return {
        "rotated": rotated,
        "deleted": deleted,
        "total_size_before": total_size_before,
        "total_size_after": total_size_after,
    }


def maintenance_status() -> dict:
    """返回维护状态摘要。"""
    backups = list_backups()
    total_backup_size = sum(b["size_bytes"] for b in backups)

    log_files = list(LOG_DIR.glob("*.log*")) if LOG_DIR.exists() else []
    total_log_size = sum(f.stat().st_size for f in log_files)

    db_size = DB_PATH.stat().st_size if DB_PATH.exists() else 0

    return {
        "database": {
            "path": str(DB_PATH),
            "size_bytes": db_size,
            "exists": DB_PATH.exists(),
        },
        "backups": {
            "count": len(backups),
            "total_size_bytes": total_backup_size,
            "latest": backups[0] if backups else None,
        },
        "logs": {
            "count": len(log_files),
            "total_size_bytes": total_log_size,
        },
        "rollback_log": {
            "exists": ROLLBACK_LOG.exists(),
            "size_bytes": ROLLBACK_LOG.stat().st_size if ROLLBACK_LOG.exists() else 0,
        },
    }


def _cleanup_old_backups(backup_dir: Path, max_backups: int) -> None:
    """删除旧备份，保留最新的 max_backups 个。"""
    backups = sorted(backup_dir.glob("*.db.gz"), key=lambda f: f.stat().st_mtime)
    while len(backups) > max_backups:
        oldest = backups.pop(0)
        oldest.unlink()
        logger.info(f"Deleted old backup: {oldest}")
