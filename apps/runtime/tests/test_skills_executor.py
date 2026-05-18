"""M4 工作流执行器单元测试。"""
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
from src.skills.executor import (
    WorkflowExecutor,
    PermissionDeniedError,
    PreconditionFailedError,
    StepVerifyFailedError,
)


def _make_skill(steps=None, preconditions=None, recovery=None, rollback=None):
    """辅助函数：创建 SkillModel。"""
    return SkillModel(
        skill_id="test_skill",
        display_name="Test Skill",
        version="1.0.0",
        description="Test",
        category="test",
        required_engines=["test_engine"],
        preconditions=preconditions or [],
        steps=steps or [
            SkillStep(
                step_id="step_1",
                action="do_something",
                engine="test_engine",
            )
        ],
        recovery=recovery,
        rollback=rollback or [],
    )


class TestWorkflowExecutorBasics:
    def test_register_engine(self):
        executor = WorkflowExecutor()
        engine = object()
        executor.register_engine("test", engine)
        assert executor._engines["test"] is engine

    def test_register_permission_checker(self):
        executor = WorkflowExecutor()
        checker = lambda: True
        executor.register_permission_checker("test_skill", checker)
        assert executor._permission_checkers["test_skill"] is checker

    def test_register_verifier(self):
        executor = WorkflowExecutor()
        verifier = lambda *a: True
        executor.register_verifier("process", verifier)
        assert executor._verifiers["process"] is verifier


class TestWorkflowExecutorExecute:
    def test_execute_without_engine_simulates(self):
        executor = WorkflowExecutor()
        skill = _make_skill()
        result = executor.execute(skill)
        assert result["success"] is True
        assert len(result["steps_executed"]) == 1
        assert result["steps_executed"][0]["success"] is True
        assert result["steps_executed"][0]["result"]["simulated"] is True

    def test_execute_with_engine_calls_method(self):
        class MockEngine:
            def do_something(self, **kwargs):
                return {"called": True}

        executor = WorkflowExecutor()
        executor.register_engine("test_engine", MockEngine())
        skill = _make_skill()
        result = executor.execute(skill)
        assert result["success"] is True
        assert result["steps_executed"][0]["result"]["called"] is True

    def test_execute_with_missing_engine_method(self):
        class MockEngine:
            pass

        executor = WorkflowExecutor()
        executor.register_engine("test_engine", MockEngine())
        skill = _make_skill()
        result = executor.execute(skill)
        # 引擎没有该方法，应该模拟执行
        assert result["success"] is True

    def test_execute_multiple_steps(self):
        executor = WorkflowExecutor()
        skill = _make_skill(
            steps=[
                SkillStep(step_id="s1", action="a1", engine="e1"),
                SkillStep(step_id="s2", action="a2", engine="e2"),
                SkillStep(step_id="s3", action="a3", engine="e3"),
            ]
        )
        result = executor.execute(skill)
        assert result["success"] is True
        assert len(result["steps_executed"]) == 3
        assert result["steps_executed"][0]["step_id"] == "s1"
        assert result["steps_executed"][2]["step_id"] == "s3"


class TestWorkflowExecutorParams:
    def test_merge_params_replaces_template(self):
        executor = WorkflowExecutor()
        skill = _make_skill(
            steps=[
                SkillStep(
                    step_id="s1",
                    action="open",
                    engine="e1",
                    args={"file": "{file_name}", "mode": "r"},
                )
            ]
        )
        result = executor.execute(skill, {"file_name": "test.py"})
        assert result["success"] is True
        assert result["steps_executed"][0]["result"]["params"]["file"] == "test.py"
        assert result["steps_executed"][0]["result"]["params"]["mode"] == "r"

    def test_merge_params_adds_user_params(self):
        executor = WorkflowExecutor()
        skill = _make_skill(
            steps=[
                SkillStep(
                    step_id="s1",
                    action="open",
                    engine="e1",
                    args={"key": "{new_key}"},
                )
            ]
        )
        result = executor.execute(skill, {"new_key": "value"})
        assert result["success"] is True
        assert result["steps_executed"][0]["result"]["params"]["key"] == "value"


class TestWorkflowExecutorPermission:
    def test_execute_permission_denied(self):
        executor = WorkflowExecutor()
        executor.register_permission_checker("test_skill", lambda: False)
        skill = _make_skill()
        result = executor.execute(skill)
        assert result["success"] is False
        assert result["error"]["type"] == "permission_denied"

    def test_execute_permission_granted(self):
        executor = WorkflowExecutor()
        executor.register_permission_checker("test_skill", lambda: True)
        skill = _make_skill()
        result = executor.execute(skill)
        assert result["success"] is True


class TestWorkflowExecutorPreconditions:
    def test_preconditions_pass(self):
        executor = WorkflowExecutor()
        skill = _make_skill(
            preconditions=[
                SkillPrecondition(type="app_installed", value="code"),
                SkillPrecondition(type="file_exists", value="/tmp/test.txt"),
            ]
        )
        result = executor.execute(skill)
        assert result["success"] is True

    def test_unknown_precondition_type_passes(self):
        executor = WorkflowExecutor()
        skill = _make_skill(
            preconditions=[
                SkillPrecondition(type="unknown_condition", value="something"),
            ]
        )
        result = executor.execute(skill)
        assert result["success"] is True


class TestWorkflowExecutorVerification:
    def test_verify_passes(self):
        executor = WorkflowExecutor()
        executor.register_verifier("process", lambda method, args, result: True)
        skill = _make_skill(
            steps=[
                SkillStep(
                    step_id="s1",
                    action="start",
                    engine="e1",
                    verify=SkillVerify(
                        type="process",
                        method="check_process",
                        args={"name": "code"},
                    ),
                )
            ]
        )
        result = executor.execute(skill)
        assert result["success"] is True

    def test_verify_fails(self):
        executor = WorkflowExecutor()
        executor.register_verifier("process", lambda method, args, result: False)
        skill = _make_skill(
            steps=[
                SkillStep(
                    step_id="s1",
                    action="start",
                    engine="e1",
                    verify=SkillVerify(
                        type="process",
                        method="check_process",
                        args={"name": "code"},
                    ),
                )
            ]
        )
        result = executor.execute(skill)
        assert result["success"] is False
        assert result["error"]["type"] == "step_failed"

    def test_no_verifier_simulates_pass(self):
        executor = WorkflowExecutor()
        skill = _make_skill(
            steps=[
                SkillStep(
                    step_id="s1",
                    action="start",
                    engine="e1",
                    verify=SkillVerify(
                        type="process",
                        method="check_process",
                        args={},
                    ),
                )
            ]
        )
        result = executor.execute(skill)
        assert result["success"] is True


class TestWorkflowExecutorRecovery:
    def test_recovery_attempts_on_failure(self):
        class FailingEngine:
            def do_something(self, **kwargs):
                raise RuntimeError("失败")

        executor = WorkflowExecutor()
        executor.register_engine("test_engine", FailingEngine())

        recovery = SkillRecovery(
            strategies={
                "step_1": [
                    RecoveryStrategy(
                        if_condition="process_not_found",
                        then_actions=[{"action": "log_error", "args": {"message": "恢复中"}}],
                        retry_original=True,
                    )
                ]
            }
        )

        skill = _make_skill(recovery=recovery)
        result = executor.execute(skill)
        # 恢复后重试，仍然失败，所以执行回滚
        assert result["success"] is False
        assert result["recovery_attempted"] is True

    def test_recovery_not_configured_passes(self):
        executor = WorkflowExecutor()
        skill = _make_skill()
        result = executor.execute(skill)
        assert result["success"] is True
        assert result["recovery_attempted"] is False


class TestWorkflowExecutorRollback:
    def test_rollback_executed_on_failure(self):
        class FailingEngine:
            def do_something(self, **kwargs):
                raise RuntimeError("失败")

            def close_application(self, **kwargs):
                return {"closed": True}

        executor = WorkflowExecutor()
        executor.register_engine("test_engine", FailingEngine())

        rollback = [
            RollbackAction(
                action="close_application",
                args={"process_name": "code"},
                condition="skill_failed",
            )
        ]

        skill = _make_skill(rollback=rollback)
        result = executor.execute(skill)
        assert result["rollback_executed"] is True

    def test_no_rollback_when_no_config(self):
        executor = WorkflowExecutor()
        skill = _make_skill()
        result = executor.execute(skill)
        assert result["rollback_executed"] is False


class TestWorkflowExecutorResult:
    def test_result_structure(self):
        executor = WorkflowExecutor()
        skill = _make_skill()
        result = executor.execute(skill)
        assert "success" in result
        assert "steps_executed" in result
        assert "result" in result
        assert "error" in result
        assert "recovery_attempted" in result
        assert "rollback_executed" in result

    def test_error_structure_on_failure(self):
        executor = WorkflowExecutor()
        executor.register_permission_checker("test_skill", lambda: False)
        skill = _make_skill()
        result = executor.execute(skill)
        assert result["error"] is not None
        assert "type" in result["error"]
        assert "message" in result["error"]
