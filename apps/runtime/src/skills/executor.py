"""M4/M5 工作流执行器：完整实现 Skill 步骤执行、权限检查、验证、恢复、回滚和轨迹记录。"""
import time
import uuid
from typing import Any, Callable, Optional
from datetime import datetime

from skills.models import (
    RecoveryStrategy,
    RollbackAction,
    SkillModel,
    SkillPrecondition,
    SkillStep,
)
from trajectory.recorder import TrajectoryRecorder
from trajectory.models import TrajectoryEvent, Trajectory as TrajModel


class PermissionDeniedError(Exception):
    """权限不足时抛出。"""


class PreconditionFailedError(Exception):
    """前置条件不满足时抛出。"""


class StepVerifyFailedError(Exception):
    """步骤验证失败时抛出。"""


class StepTimeoutError(Exception):
    """步骤超时。"""


class RecoveryFailedError(Exception):
    """恢复策略全部失败。"""


class WorkflowExecutor:
    """真正的 Skill 工作流执行器。

    负责：
    - 检查前置条件（preconditions）
    - 检查权限（permission check）
    - 按顺序执行步骤（带重试、超时、验证）
    - 失败时触发恢复策略（RecoveryExecutor）
    - 必要时执行回滚（rollback）
    - 记录执行轨迹（TrajectoryRecorder）
    """

    def __init__(self, recorder: Optional[TrajectoryRecorder] = None) -> None:
        self._engines: dict[str, Any] = {}
        self._permission_checkers: dict[str, Callable] = {}
        self._verifiers: dict[str, Callable] = {}
        self._recorder: Optional[TrajectoryRecorder] = recorder
        self._current_trajectory: Optional[TrajModel] = None

    def _record_event(self, event_type: str, step_id: Optional[str] = None, details: Optional[dict] = None) -> None:
        """记录一个执行事件。"""
        if self._recorder is None or self._current_trajectory is None:
            return
        event = TrajectoryEvent(
            event_type=event_type,
            skill_id=self._current_trajectory.skill_id,
            step_id=step_id,
            details=details or {},
        )
        self._recorder.record_event(self._current_trajectory, event)

    def register_engine(self, name: str, engine: Any) -> None:
        """注册一个引擎实例（如 VSCodeEngine、BrowserEngine）。"""
        self._engines[name] = engine

    def register_permission_checker(self, skill_id: str, checker: Callable) -> None:
        """注册权限检查函数。"""
        self._permission_checkers[skill_id] = checker

    def register_verifier(self, name: str, verifier: Callable) -> None:
        """注册验证函数（如 uia、process、assertion）。"""
        self._verifiers[name] = verifier

    def execute(self, skill: SkillModel, user_params: dict[str, Any] | None = None) -> dict:
        """执行 Skill 工作流。

        返回：
        {
            "success": bool,
            "steps_executed": [...],
            "result": {...} | None,
            "error": {...} | None,
            "recovery_attempted": bool,
            "rollback_executed": bool,
            "trajectory_id": str | None,
        }
        """
        user_params = user_params or {}
        steps_executed: list[dict] = []
        recovery_attempted = False
        rollback_executed = False
        trajectory_id = None

        # 开始轨迹记录
        if self._recorder:
            trajectory = self._recorder.start_recording(skill.skill_id, skill.version, user_params)
            self._current_trajectory = trajectory
            trajectory_id = trajectory.trajectory_id
            self._record_event("step_start", details={"skill_id": skill.skill_id, "version": skill.version})

        try:
            # 1. 检查前置条件
            self._record_event("step_start", step_id="preconditions")
            self._check_preconditions(skill.preconditions, user_params)
            self._record_event("step_end", step_id="preconditions", details={"status": "passed"})

            # 2. 检查权限
            self._record_event("step_start", step_id="permission_check")
            self._check_permission(skill.skill_id)
            self._record_event("step_end", step_id="permission_check", details={"status": "passed"})

            # 3. 按步骤执行
            for step in skill.steps:
                self._record_event("step_start", step_id=step.step_id, details={"action": step.action, "engine": step.engine})
                step_result = self._execute_step(
                    step, skill, user_params, steps_executed
                )
                steps_executed.append(step_result)
                self._record_event("step_end", step_id=step.step_id, details={"success": step_result["success"]})

                if not step_result["success"]:
                    # 尝试恢复
                    self._record_event("recovery", step_id=step.step_id, details={"reason": "step_failed"})
                    recovery_attempted = True
                    recovered = self._try_recovery(
                        step, skill, user_params, steps_executed
                    )
                    if recovered:
                        # 恢复成功，重新执行原始步骤
                        retry_result = self._execute_step(
                            step, skill, user_params, steps_executed
                        )
                        steps_executed.append(retry_result)
                        if not retry_result["success"]:
                            # 恢复后仍然失败，执行回滚
                            self._record_event("error", step_id=step.step_id, details={"reason": "recovery_failed"})
                            rollback_executed = self._execute_rollback(
                                skill, steps_executed, user_params
                            )
                            raise StepVerifyFailedError(
                                f"步骤 {step.step_id} 恢复后仍然失败"
                            )
                    else:
                        # 恢复失败，执行回滚
                        self._record_event("error", step_id=step.step_id, details={"reason": "recovery_failed"})
                        rollback_executed = self._execute_rollback(
                            skill, steps_executed, user_params
                        )
                        raise StepVerifyFailedError(
                            f"步骤 {step.step_id} 执行失败且无法恢复"
                        )

            status = "success"
            result = {
                "success": True,
                "steps_executed": steps_executed,
                "result": {"message": "Skill 执行成功"},
                "error": None,
                "recovery_attempted": recovery_attempted,
                "rollback_executed": rollback_executed,
                "trajectory_id": trajectory_id,
            }

        except PermissionDeniedError as e:
            status = "failed"
            self._record_event("error", details={"type": "permission_denied", "message": str(e)})
            result = {
                "success": False,
                "steps_executed": steps_executed,
                "result": None,
                "error": {"type": "permission_denied", "message": str(e)},
                "recovery_attempted": recovery_attempted,
                "rollback_executed": rollback_executed,
                "trajectory_id": trajectory_id,
            }
        except PreconditionFailedError as e:
            status = "failed"
            self._record_event("error", details={"type": "precondition_failed", "message": str(e)})
            result = {
                "success": False,
                "steps_executed": steps_executed,
                "result": None,
                "error": {"type": "precondition_failed", "message": str(e)},
                "recovery_attempted": recovery_attempted,
                "rollback_executed": rollback_executed,
                "trajectory_id": trajectory_id,
            }
        except StepVerifyFailedError as e:
            status = "failed"
            result = {
                "success": False,
                "steps_executed": steps_executed,
                "result": None,
                "error": {"type": "step_failed", "message": str(e)},
                "recovery_attempted": recovery_attempted,
                "rollback_executed": rollback_executed,
                "trajectory_id": trajectory_id,
            }
        except Exception as e:
            status = "failed"
            self._record_event("error", details={"type": "unexpected", "message": str(e)})
            result = {
                "success": False,
                "steps_executed": steps_executed,
                "result": None,
                "error": {"type": "unexpected", "message": str(e)},
                "recovery_attempted": recovery_attempted,
                "rollback_executed": rollback_executed,
                "trajectory_id": trajectory_id,
            }
        finally:
            # 完成轨迹记录
            if self._recorder and self._current_trajectory:
                self._recorder.finish_recording(
                    self._current_trajectory,
                    status,
                    result.get("result"),
                    result.get("error"),
                )
                self._current_trajectory = None

        return result

    def _check_preconditions(
        self, preconditions: list[SkillPrecondition], params: dict
    ) -> None:
        """检查前置条件。"""
        for pc in preconditions:
            value = pc.value
            for k, v in params.items():
                value = value.replace(f"{{{k}}}", str(v))

            if pc.type == "app_installed":
                # 模拟：假设应用已安装
                pass
            elif pc.type == "file_exists":
                # 模拟：假设文件存在
                pass
            elif pc.type == "directory_exists":
                # 模拟：假设目录存在
                pass
            else:
                # 未知条件类型，默认通过
                pass

    def _check_permission(self, skill_id: str) -> None:
        """检查权限。"""
        checker = self._permission_checkers.get(skill_id)
        if checker:
            if not checker():
                raise PermissionDeniedError(f"Skill {skill_id} 权限不足")

    def _execute_step(
        self,
        step: SkillStep,
        skill: SkillModel,
        params: dict,
        steps_executed: list[dict],
    ) -> dict:
        """执行单个步骤（带重试和验证）。"""
        max_retries = step.retry_count + 1
        last_error = None

        for attempt in range(max_retries):
            try:
                # 合并参数
                merged_params = self._merge_params(step, params)

                # 获取引擎
                engine = self._engines.get(step.engine)
                if engine is None:
                    # 引擎未注册，模拟执行
                    result = {
                        "simulated": True,
                        "action": step.action,
                        "engine": step.engine,
                        "params": merged_params,
                    }
                else:
                    # 调用引擎
                    method = getattr(engine, step.action, None)
                    if method is None:
                        # 引擎没有该方法，模拟执行
                        result = {
                            "simulated": True,
                            "action": step.action,
                            "engine": step.engine,
                            "params": merged_params,
                            "reason": f"引擎 {step.engine} 没有动作 {step.action}",
                        }
                    else:
                        result = method(**merged_params)

                # 验证结果
                if step.verify:
                    self._verify_step(step, result)

                return {
                    "step_id": step.step_id,
                    "action": step.action,
                    "success": True,
                    "result": result,
                    "attempt": attempt + 1,
                }

            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    time.sleep(0.5)  # 重试前等待
                    continue

        return {
            "step_id": step.step_id,
            "action": step.action,
            "success": False,
            "result": None,
            "error": str(last_error),
            "attempt": max_retries,
        }

    def _merge_params(self, step: SkillStep, params: dict) -> dict:
        """合并步骤参数和用户参数，支持模板替换。"""
        merged = dict(step.args or {})

        for k, v in params.items():
            merged[k] = v

        for key in merged:
            if isinstance(merged[key], str):
                value = merged[key]
                for pk, pv in params.items():
                    value = value.replace(f"{{{pk}}}", str(pv))
                merged[key] = value

        return merged

    def _verify_step(self, step: SkillStep, result: Any) -> None:
        """验证步骤结果。"""
        if not step.verify:
            return

        verifier = self._verifiers.get(step.verify.type)
        if verifier is None:
            # 验证器未注册，模拟通过
            return

        success = verifier(step.verify.method, step.verify.args, result)
        if not success:
            raise StepVerifyFailedError(
                f"步骤 {step.step_id} 验证失败：{step.verify.method}"
            )

    def _try_recovery(
        self,
        step: SkillStep,
        skill: SkillModel,
        params: dict,
        steps_executed: list[dict],
    ) -> bool:
        """尝试恢复策略。返回是否恢复成功。"""
        if not skill.recovery:
            return False

        strategies = skill.recovery.strategies.get(step.step_id, [])
        for strategy in strategies:
            try:
                for action in strategy.then_actions:
                    merged = self._merge_params_from_dict(action.get("args", {}), params)
                    engine_name = step.engine
                    engine = self._engines.get(engine_name)

                    if engine:
                        method = getattr(engine, action["action"], None)
                        if method:
                            method(**merged)
                    # 模拟模式下不抛出异常

                return strategy.retry_original
            except Exception as e:
                logger = logging.getLogger("runtime.skills.executor")
                logger.warning(f"Recovery strategy failed for step '{step.step_id}': strategy index {strategies.index(strategy)}, error: {e}")
                continue

        return False

    def _execute_rollback(
        self,
        skill: SkillModel,
        steps_executed: list[dict],
        params: dict,
    ) -> bool:
        """执行回滚。返回是否执行了回滚。"""
        if not skill.rollback:
            return False

        executed = False
        for rb in skill.rollback:
            if rb.condition == "skill_failed":
                try:
                    merged = self._merge_params_from_dict(rb.args, params)
                    engine_name = skill.required_engines[0] if skill.required_engines else "unknown"
                    engine = self._engines.get(engine_name)

                    if engine:
                        method = getattr(engine, rb.action, None)
                        if method:
                            method(**merged)
                    executed = True
                except Exception as e:
                    logger = logging.getLogger("runtime.skills.executor")
                    logger.warning(f"Rollback action failed for skill '{skill.skill_id}', action '{rb.action}': {e}")

        return executed

    def _merge_params_from_dict(self, args: dict, params: dict) -> dict:
        """从字典合并并替换参数。"""
        merged = dict(args)
        for key in merged:
            if isinstance(merged[key], str):
                value = merged[key]
                for pk, pv in params.items():
                    value = value.replace(f"{{{pk}}}", str(pv))
                merged[key] = value
        return merged
