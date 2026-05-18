"""M5 晋升引擎：备份旧版本，晋升候选 Skill。"""
import shutil
import json
from pathlib import Path
from datetime import datetime
from typing import Optional


class PromotionEngine:
    """晋升引擎。

    职责：
    - 备份旧版本到带日期的目录
    - 复制候选文件到正式目录
    - 更新 metadata（status 改为 active，去掉 -candidate 后缀）
    - 记录晋升评测结果
    - 成功率 < 80% 时返回拒绝原因
    """

    def __init__(self, skills_dir: str = "data/skills", backups_dir: str = "data/backups") -> None:
        self.skills_dir = Path(skills_dir)
        self.backups_dir = Path(backups_dir)
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)

    def try_promote(
        self,
        candidate_dir: Path,
        replay_result: dict,
    ) -> dict:
        """尝试晋升候选 Skill。

        参数：
        - candidate_dir: 候选 Skill 目录
        - replay_result: ReplayEvaluator.evaluate() 的结果

        返回：
        {
            "promoted": bool,
            "reason": str,
            "backup_path": str | None,
            "new_path": str | None,
        }
        """
        # 检查成功率
        success_rate = replay_result.get("success_rate", 0.0)
        if success_rate < 0.8:
            return {
                "promoted": False,
                "reason": f"成功率 {success_rate:.0%} < 80%，拒绝晋升",
                "backup_path": None,
                "new_path": None,
            }

        # 读取候选 metadata
        metadata_path = candidate_dir / "metadata.json"
        if not metadata_path.exists():
            return {
                "promoted": False,
                "reason": "候选目录缺少 metadata.json",
                "backup_path": None,
                "new_path": None,
            }

        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        skill_id = metadata.get("skill_id", candidate_dir.name.replace("-candidate", ""))
        target_dir = self.skills_dir / skill_id

        # 备份旧版本
        backup_path = None
        if target_dir.exists():
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_path = self.backups_dir / f"{skill_id}_backup_{timestamp}"
            shutil.copytree(target_dir, backup_path)

        # 复制候选文件到正式目录
        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.copytree(candidate_dir, target_dir)

        # 更新 metadata
        new_metadata_path = target_dir / "metadata.json"
        with open(new_metadata_path, "r", encoding="utf-8") as f:
            new_metadata = json.load(f)

        new_metadata["status"] = "active"
        new_metadata["version"] = new_metadata["version"].replace("-candidate", "")
        new_metadata["promoted_at"] = datetime.utcnow().isoformat()
        new_metadata["promotion_result"] = {
            "success_rate": success_rate,
            "replay_count": replay_result.get("replay_count", 0),
        }

        with open(new_metadata_path, "w", encoding="utf-8") as f:
            json.dump(new_metadata, f, indent=2, ensure_ascii=False)

        return {
            "promoted": True,
            "reason": f"成功率 {success_rate:.0%} >= 80%，晋升成功",
            "backup_path": str(backup_path) if backup_path else None,
            "new_path": str(target_dir),
        }
