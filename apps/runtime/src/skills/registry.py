import yaml
import logging
from pathlib import Path
from typing import Optional
from .models import (
    SkillModel,
    SkillStep,
    SkillVerify,
    SkillExpect,
    RecoveryStrategy,
    SkillRecovery,
    RollbackAction,
    SkillPrecondition,
)

logger = logging.getLogger("runtime.skills.registry")

SKILLS_DIR = Path(__file__).parents[2] / "data" / "skills"


class SkillRegistry:
    """Loads skill definitions from YAML files."""

    def __init__(self, skills_dir: Path = None):
        self.skills_dir = skills_dir or SKILLS_DIR
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, SkillModel] = {}

    def load(self, skill_id: str) -> Optional[SkillModel]:
        if skill_id in self._cache:
            return self._cache[skill_id]

        yaml_path = self.skills_dir / f"{skill_id}.yaml"
        if not yaml_path.exists():
            yaml_path = self.skills_dir / f"{skill_id.replace('/', '_')}.yaml"

        if not yaml_path.exists():
            logger.warning(f"Skill not found: {yaml_path}")
            return None

        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        steps_data = data.get("steps", [])
        steps = []
        for step_data in steps_data:
            # 解析 verify
            verify = None
            if step_data.get("verify"):
                v = step_data["verify"]
                verify = SkillVerify(
                    type=v.get("type", "unknown"),
                    method=v.get("method", ""),
                    args=v.get("args", {}),
                )

            # 解析 expect
            expect = None
            if step_data.get("expect"):
                e = step_data["expect"]
                expect = SkillExpect(
                    description=e.get("description", ""),
                    conditions=e.get("conditions", {}),
                )

            step = SkillStep(
                step_id=step_data["step_id"],
                action=step_data["action"],
                engine=step_data.get("engine", "unknown"),
                args=step_data.get("args", {}),
                params=step_data.get("params", {}),
                timeout=step_data.get("timeout", 30.0),
                retry_count=step_data.get("retry_count", 0),
                expect=expect,
                verify=verify,
            )
            steps.append(step)

        # 解析 preconditions
        preconditions = []
        for pc_data in data.get("preconditions", []):
            preconditions.append(
                SkillPrecondition(
                    type=pc_data.get("type", ""),
                    value=pc_data.get("value", ""),
                )
            )

        # 解析 recovery
        recovery = None
        recovery_data = data.get("recovery")
        if recovery_data:
            strategies = {}
            for step_id, strat_list in recovery_data.get("strategies", {}).items():
                strategies[step_id] = [
                    RecoveryStrategy(
                        if_condition=s.get("if_condition", ""),
                        then_actions=s.get("then_actions", []),
                        retry_original=s.get("retry_original", False),
                    )
                    for s in strat_list
                ]
            recovery = SkillRecovery(strategies=strategies)

        # 解析 rollback
        rollback = []
        for rb_data in data.get("rollback", []):
            rollback.append(
                RollbackAction(
                    action=rb_data.get("action", ""),
                    args=rb_data.get("args", {}),
                    condition=rb_data.get("condition", ""),
                )
            )

        skill = SkillModel(
            skill_id=data["skill_id"],
            display_name=data["display_name"],
            version=data["version"],
            description=data.get("description", ""),
            category=data.get("category", "general"),
            required_engines=data.get("required_engines", []),
            preconditions=preconditions,
            steps=steps,
            recovery=recovery,
            rollback=rollback,
            metadata=data.get("metadata", {}),
        )
        self._cache[skill_id] = skill
        return skill

    def list_all(self) -> list[SkillModel]:
        skills = []
        for yaml_file in self.skills_dir.glob("*.yaml"):
            skill_id = yaml_file.stem
            skill = self.load(skill_id)
            if skill:
                skills.append(skill)
        return skills

    def get_skill_ids(self) -> list[str]:
        return [s.skill_id for s in self.list_all()]
