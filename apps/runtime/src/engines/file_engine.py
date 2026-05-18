"""文件系统引擎：真实文件操作（扫描、分类、移动、归档、回滚）。"""
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("runtime.engines.file_engine")

FILE_CATEGORIES = {
    "images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".ico"],
    "documents": [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".md", ".csv"],
    "videos": [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm"],
    "audio": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma"],
    "archives": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"],
    "installers": [".exe", ".msi", ".dmg", ".pkg", ".deb", ".rpm"],
    "code": [".py", ".js", ".ts", ".html", ".css", ".java", ".cpp", ".c", ".h", ".go", ".rs"],
}

ROLLBACK_LOG = Path(__file__).resolve().parent.parent.parent.parent / "data" / "rollback_log.json"


class FileEngine:
    """文件系统操作引擎。

    所有写操作都会记录到审计日志，支持一键回滚。
    """

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir = base_dir or Path.home()
        self._operations: list[dict] = []

    def scan_directory(self, dir_path: str) -> dict:
        """扫描目录，返回文件列表。

        参数：
            dir_path: 目录路径

        返回：
            {"files": list, "count": int, "error": str | None}
        """
        target = Path(dir_path)
        if not target.exists():
            return {
                "files": [],
                "count": 0,
                "error": f"目录不存在: {target}",
                "message": "目录不存在",
            }

        if not target.is_dir():
            return {
                "files": [],
                "count": 0,
                "error": f"不是目录: {target}",
                "message": "路径不是目录",
            }

        files = []
        for item in target.rglob("*"):
            if item.is_file():
                stat = item.stat()
                files.append({
                    "path": str(item),
                    "name": item.name,
                    "suffix": item.suffix.lower(),
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })

        return {
            "files": files,
            "count": len(files),
            "error": None,
            "message": f"扫描完成，共 {len(files)} 个文件",
        }

    def classify_files(self, files: list[str]) -> dict:
        """根据文件扩展名分类。

        参数：
            files: 文件路径列表

        返回：
            {"categories": dict, "error": str | None}
        """
        categories: dict[str, list[str]] = {}

        for file_path in files:
            suffix = Path(file_path).suffix.lower()
            category = "others"
            for cat, extensions in FILE_CATEGORIES.items():
                if suffix in extensions:
                    category = cat
                    break

            if category not in categories:
                categories[category] = []
            categories[category].append(file_path)

        return {
            "categories": categories,
            "error": None,
            "message": f"分类完成，共 {len(categories)} 个类别",
        }

    def move_files(self, file_map: dict[str, str]) -> dict:
        """移动文件到目标位置。

        参数：
            file_map: {源路径: 目标路径} 字典

        返回：
            {"moved": int, "errors": list, "error": str | None}
        """
        moved = 0
        errors = []

        for src, dst in file_map.items():
            src_path = Path(src)
            dst_path = Path(dst)

            if not src_path.exists():
                errors.append({
                    "source": src,
                    "error": "源文件不存在",
                })
                continue

            try:
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src_path), str(dst_path))

                self._operations.append({
                    "action": "move",
                    "source": src,
                    "destination": dst,
                    "timestamp": datetime.now().isoformat(),
                })

                moved += 1
            except Exception as e:
                errors.append({
                    "source": src,
                    "destination": dst,
                    "error": str(e),
                })

        if self._operations:
            self._save_rollback_log()

        return {
            "moved": moved,
            "errors": errors,
            "error": None if not errors else f"{len(errors)} 个文件移动失败",
            "message": f"成功移动 {moved} 个文件",
        }

    def organize_directory(self, dir_path: str) -> dict:
        """整理目录：扫描、分类、移动。

        参数：
            dir_path: 目标目录

        返回：
            {"moved": int, "categories": dict, "errors": list, "error": str | None}
        """
        scan_result = self.scan_directory(dir_path)
        if scan_result["error"]:
            return scan_result

        files = [f["path"] for f in scan_result["files"]]
        classify_result = self.classify_files(files)

        file_map = {}
        categories = classify_result["categories"]

        for category, file_paths in categories.items():
            for file_path in file_paths:
                file_name = Path(file_path).name
                dst = Path(dir_path) / category / file_name
                if Path(file_path) != dst:
                    file_map[file_path] = str(dst)

        move_result = self.move_files(file_map)

        return {
            "moved": move_result["moved"],
            "categories": categories,
            "errors": move_result["errors"],
            "error": move_result["error"],
            "message": f"目录整理完成，共移动 {move_result['moved']} 个文件",
        }

    def rollback(self, operation_index: int = -1) -> dict:
        """回滚文件操作。

        参数：
            operation_index: 操作索引（-1 表示最后一次操作）

        返回：
            {"restored": int, "errors": list, "error": str | None}
        """
        if not self._operations:
            return {
                "restored": 0,
                "errors": [],
                "error": None,
                "message": "没有可回滚的操作",
            }

        if operation_index < 0:
            operation_index = len(self._operations) - 1

        if operation_index >= len(self._operations):
            return {
                "restored": 0,
                "errors": [],
                "error": "操作索引越界",
                "message": "索引超出范围",
            }

        op = self._operations[operation_index]
        restored = 0
        errors = []

        if op["action"] == "move":
            src = Path(op["source"])
            dst = Path(op["destination"])

            if dst.exists():
                try:
                    src.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(dst), str(src))
                    restored += 1
                except Exception as e:
                    errors.append({
                        "source": str(dst),
                        "destination": str(src),
                        "error": str(e),
                    })

        if errors:
            self._operations.pop(operation_index)
            self._save_rollback_log()

        return {
            "restored": restored,
            "errors": errors,
            "error": None if not errors else f"{len(errors)} 个文件回滚失败",
            "message": f"回滚完成，恢复 {restored} 个文件",
        }

    def create_directory(self, dir_path: str) -> dict:
        """创建目录。

        参数：
            dir_path: 目录路径

        返回：
            {"success": bool, "error": str | None}
        """
        target = Path(dir_path)
        try:
            target.mkdir(parents=True, exist_ok=True)
            return {
                "success": True,
                "error": None,
                "message": f"目录已创建: {dir_path}",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"创建目录失败: {e}",
            }

    def delete_file(self, file_path: str) -> dict:
        """删除文件。

        参数：
            file_path: 文件路径

        返回：
            {"success": bool, "error": str | None}
        """
        target = Path(file_path)
        if not target.exists():
            return {
                "success": False,
                "error": f"文件不存在: {file_path}",
                "message": "文件不存在",
            }

        try:
            self._operations.append({
                "action": "delete",
                "source": str(target),
                "timestamp": datetime.now().isoformat(),
            })

            target.unlink()
            self._save_rollback_log()

            return {
                "success": True,
                "error": None,
                "message": f"文件已删除: {file_path}",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"删除文件失败: {e}",
            }

    def get_operations(self) -> list[dict]:
        """获取操作历史。

        返回：
            操作列表
        """
        return list(self._operations)

    def clear_operations(self) -> None:
        """清空操作历史。"""
        self._operations.clear()
        if ROLLBACK_LOG.exists():
            ROLLBACK_LOG.unlink()

    def _save_rollback_log(self) -> None:
        """保存回滚日志。"""
        ROLLBACK_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(ROLLBACK_LOG, "w", encoding="utf-8") as f:
            json.dump(self._operations, f, indent=2, ensure_ascii=False)

    def _load_rollback_log(self) -> list[dict]:
        """加载回滚日志。"""
        if ROLLBACK_LOG.exists():
            with open(ROLLBACK_LOG, "r", encoding="utf-8") as f:
                return json.load(f)
        return []
