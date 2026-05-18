import pytest
import tempfile
from pathlib import Path
from src.skills.registry import SkillRegistry
from src.skills.models import SkillModel, SkillStep


class TestSkillRegistry:
    def test_load_vscode_skill(self):
        registry = SkillRegistry()
        skill = registry.load("vscode_run_file_v1")
        assert skill is not None
        assert skill.skill_id == "vscode_run_file_v1"
        assert "VSCode" in skill.display_name
        assert skill.category == "editor"
        assert len(skill.steps) == 3
        assert skill.preconditions is not None
        assert skill.recovery is not None
        assert len(skill.rollback) > 0

    def test_load_chrome_skill(self):
        registry = SkillRegistry()
        skill = registry.load("chrome_search_v1")
        assert skill is not None
        assert skill.skill_id == "chrome_search_v1"
        assert skill.category == "browser"
        assert len(skill.steps) == 3
        assert skill.recovery is not None
        assert "Chrome" in skill.display_name or "浏览器" in skill.display_name

    def test_load_file_skill(self):
        registry = SkillRegistry()
        skill = registry.load("file_archive_v1")
        assert skill is not None
        assert skill.skill_id == "file_archive_v1"
        assert skill.category == "file"
        assert len(skill.steps) == 3

    def test_load_nonexistent_skill(self):
        registry = SkillRegistry()
        skill = registry.load("nonexistent_skill")
        assert skill is None

    def test_list_all_skills(self):
        registry = SkillRegistry()
        skills = registry.list_all()
        assert len(skills) >= 3
        skill_ids = [s.skill_id for s in skills]
        assert "vscode_run_file_v1" in skill_ids
        assert "chrome_search_v1" in skill_ids
        assert "file_archive_v1" in skill_ids

    def test_get_skill_ids(self):
        registry = SkillRegistry()
        ids = registry.get_skill_ids()
        assert isinstance(ids, list)
        assert len(ids) >= 3

    def test_skill_caching(self):
        registry = SkillRegistry()
        skill1 = registry.load("vscode_run_file_v1")
        skill2 = registry.load("vscode_run_file_v1")
        assert skill1 is skill2

    def test_load_skill_steps(self):
        registry = SkillRegistry()
        skill = registry.load("vscode_run_file_v1")
        assert skill is not None
        assert skill.steps[0].step_id == "open_vscode"
        assert skill.steps[0].engine == "vscode"
        assert skill.steps[0].action == "launch"
        assert skill.steps[0].timeout > 0
        assert skill.steps[0].expect is not None
        assert skill.steps[0].verify is not None

    def test_custom_skills_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = SkillRegistry(skills_dir=Path(tmpdir))
            assert registry.list_all() == []
            assert registry.load("test") is None
