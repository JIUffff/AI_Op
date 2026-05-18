import pytest
from src.skills.models import (
    SkillModel,
    SkillStep,
    SkillVerify,
    SkillExpect,
    RecoveryStrategy,
    SkillRecovery,
    RollbackAction,
    SkillPrecondition,
)


class TestSkillModel:
    def test_skill_model_minimal(self):
        skill = SkillModel(
            skill_id="test_skill",
            display_name="Test Skill",
            version="1.0.0",
            steps=[
                SkillStep(
                    step_id="step_1",
                    action="do_something",
                    engine="test_engine",
                )
            ],
        )
        assert skill.skill_id == "test_skill"
        assert skill.version == "1.0.0"
        assert len(skill.steps) == 1

    def test_skill_model_full(self):
        skill = SkillModel(
            skill_id="full_skill",
            display_name="Full Skill",
            version="2.0.0",
            description="A skill with all fields",
            category="editor",
            required_engines=["vscode"],
            preconditions=[
                SkillPrecondition(type="app_installed", value="code"),
            ],
            steps=[
                SkillStep(
                    step_id="step_1",
                    action="open_file",
                    engine="vscode",
                    args={"file_path": "/tmp/test.py"},
                    timeout=10.0,
                    retry_count=2,
                    expect=SkillExpect(
                        description="文件已打开",
                        conditions={"file_loaded": True},
                    ),
                    verify=SkillVerify(
                        type="uia",
                        method="check_active_document",
                        args={"file_path": "/tmp/test.py"},
                    ),
                )
            ],
            recovery=SkillRecovery(
                strategies={
                    "step_1": [
                        RecoveryStrategy(
                            if_condition="file_not_found",
                            then_actions=[{"action": "log_error", "args": {"message": "文件不存在"}}],
                            retry_original=True,
                        )
                    ]
                }
            ),
            rollback=[
                RollbackAction(
                    action="close_application",
                    args={"process_name": "code"},
                    condition="skill_failed",
                )
            ],
            metadata={"author": "test"},
        )
        assert skill.required_engines == ["vscode"]
        assert skill.steps[0].args["file_path"] == "/tmp/test.py"
        assert skill.steps[0].retry_count == 2
        assert skill.metadata["author"] == "test"
        assert skill.preconditions[0].type == "app_installed"
        assert skill.recovery is not None
        assert len(skill.rollback) == 1

    def test_skill_model_validation_empty_steps(self):
        with pytest.raises(ValueError):
            SkillModel(
                skill_id="bad_skill",
                display_name="Bad Skill",
                version="1.0.0",
                steps=[],
            )

    def test_skill_model_validation_negative_timeout(self):
        with pytest.raises(ValueError):
            SkillStep(
                step_id="bad_step",
                action="test",
                engine="test",
                timeout=-1.0,
            )

    def test_skill_model_default_values(self):
        step = SkillStep(
            step_id="default_step",
            action="test_action",
            engine="test_engine",
        )
        assert step.timeout == 30.0
        assert step.retry_count == 0
        assert step.args == {}
        assert step.expect is None
        assert step.verify is None

    def test_skill_precondition(self):
        pc = SkillPrecondition(type="file_exists", value="/tmp/test.py")
        assert pc.type == "file_exists"
        assert pc.value == "/tmp/test.py"

    def test_skill_verify(self):
        v = SkillVerify(
            type="process",
            method="check_process",
            args={"process_name": "code"},
        )
        assert v.type == "process"
        assert v.method == "check_process"
        assert v.args["process_name"] == "code"

    def test_recovery_strategy(self):
        strategy = RecoveryStrategy(
            if_condition="timeout",
            then_actions=[{"action": "retry", "args": {"delay": 1.0}}],
            retry_original=True,
        )
        assert strategy.if_condition == "timeout"
        assert strategy.retry_original is True
        assert len(strategy.then_actions) == 1

    def test_rollback_action(self):
        rb = RollbackAction(
            action="close_app",
            args={"name": "chrome"},
            condition="skill_failed",
        )
        assert rb.action == "close_app"
        assert rb.condition == "skill_failed"
        assert rb.args["name"] == "chrome"

    def test_skill_recovery(self):
        recovery = SkillRecovery(
            strategies={
                "step_1": [
                    RecoveryStrategy(
                        if_condition="error",
                        then_actions=[],
                        retry_original=False,
                    )
                ]
            }
        )
        assert "step_1" in recovery.strategies
        assert len(recovery.strategies["step_1"]) == 1
