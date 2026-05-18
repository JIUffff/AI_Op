"""M5 Skill 蒸馏器：从成功轨迹中生成候选 Skill。"""
import json
import yaml
from pathlib import Path
from collections import Counter
from typing import Optional
from .models import CandidateSkill


class SkillDistiller:
    """蒸馏器。

    职责：
    - 从 3+ 条成功轨迹中提取最常见的步骤序列
    - 生成候选 Skill 目录（workflow.yaml、recovery.yaml、metadata.json）
    - 状态标记为 candidate，版本号含 -candidate 后缀
    """

    def __init__(self, skills_dir: str = "data/skills") -> None:
        self.skills_dir = Path(skills_dir)
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    def distill(
        self,
        skill_id: str,
        trajectories: list[dict],
        output_dir: Optional[Path] = None,
    ) -> CandidateSkill:
        """从成功轨迹中蒸馏候选 Skill。

        参数：
        - skill_id: 目标 Skill ID
        - trajectories: 成功轨迹列表（至少 3 条）
        - output_dir: 候选 Skill 输出目录（默认为 data/skills/{skill_id}-candidate）

        返回：
        - CandidateSkill 元数据
        """
        if len(trajectories) < 3:
            raise ValueError(f"至少需要 3 条成功轨迹，当前只有 {len(trajectories)} 条")

        if output_dir is None:
            output_dir = self.skills_dir / f"{skill_id}-candidate"
        output_dir.mkdir(parents=True, exist_ok=True)

        # 提取步骤序列
        steps_sequences = self._extract_step_sequences(trajectories)

        # 找出最常见的步骤序列
        common_steps = self._find_most_common_sequence(steps_sequences)

        # 提取参数
        params = self._extract_params(trajectories)

        # 提取 recovery 场景
        recovery_scenarios = self._extract_recovery_scenarios(trajectories)

        # 生成 workflow.yaml
        self._write_workflow_yaml(output_dir / "workflow.yaml", skill_id, common_steps, params)

        # 生成 recovery.yaml
        self._write_recovery_yaml(output_dir / "recovery.yaml", recovery_scenarios)

        # 生成 metadata.json
        version = self._generate_version(skill_id)
        candidate = CandidateSkill(
            skill_id=skill_id,
            version=version,
            status="candidate",
            source_trajectories=[t.get("trajectory_id", "") for t in trajectories],
            success_rate=1.0,  # 蒸馏自成功轨迹
            metadata={
                "distilled_from": len(trajectories),
                "common_steps_count": len(common_steps),
            },
        )
        self._write_metadata(output_dir / "metadata.json", candidate)

        return candidate

    def _extract_step_sequences(self, trajectories: list[dict]) -> list[list[dict]]:
        """从轨迹中提取步骤序列。"""
        sequences = []
        for t in trajectories:
            steps = []
            for event in t.get("events", []):
                if event.get("event_type") == "step_end":
                    steps.append({
                        "step_id": event.get("step_id", ""),
                        "action": event.get("details", {}).get("action", ""),
                        "engine": event.get("details", {}).get("engine", ""),
                        "params": event.get("details", {}).get("params", {}),
                        "result": event.get("details", {}).get("result"),
                    })
            if steps:
                sequences.append(steps)
        return sequences

    def _find_most_common_sequence(self, sequences: list[list[dict]]) -> list[dict]:
        """找出最常见的步骤序列。

        MVP 策略：取第一条轨迹的步骤序列作为模板。
        二期可改为序列对齐和参数泛化。
        """
        if not sequences:
            return []

        # MVP：返回第一条
        # 二期改进：使用序列对齐算法找出最频繁的公共子序列
        return sequences[0]

    def _extract_params(self, trajectories: list[dict]) -> dict:
        """从轨迹中提取参数。"""
        params = {}
        for t in trajectories:
            params.update(t.get("params", {}))
        return params

    def _extract_recovery_scenarios(self, trajectories: list[dict]) -> list[dict]:
        """提取 recovery 场景。"""
        scenarios = []
        for t in trajectories:
            for event in t.get("events", []):
                if event.get("event_type") == "recovery":
                    scenarios.append(event.get("details", {}))
        return scenarios

    def _write_workflow_yaml(self, filepath: Path, skill_id: str, steps: list[dict], params: dict) -> None:
        """生成 workflow.yaml。"""
        workflow = {
            "skill_id": skill_id,
            "steps": steps,
            "params": list(params.keys()),
        }
        with open(filepath, "w", encoding="utf-8") as f:
            yaml.dump(workflow, f, default_flow_style=False, allow_unicode=True)

    def _write_recovery_yaml(self, filepath: Path, scenarios: list[dict]) -> None:
        """生成 recovery.yaml。"""
        recovery = {
            "scenarios": scenarios,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            yaml.dump(recovery, f, default_flow_style=False, allow_unicode=True)

    def _write_metadata(self, filepath: Path, candidate: CandidateSkill) -> None:
        """生成 metadata.json。"""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(candidate.model_dump(mode="json"), f, indent=2, ensure_ascii=False)

    def _generate_version(self, skill_id: str) -> str:
        """生成候选版本号。"""
        # 检查现有版本
        candidate_dirs = list(self.skills_dir.glob(f"{skill_id}*"))
        version_num = len(candidate_dirs) + 1
        return f"{version_num}.0.0-candidate"
