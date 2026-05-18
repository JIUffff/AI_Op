"""M5 回放评测器：回放候选 Skill 计算成功率。"""
import time
from typing import Optional, Any
from .models import Trajectory, TrajectoryEvent


class ReplayEvaluator:
    """回放评测器。

    职责：
    - 将候选 Skill 回放执行 N 次
    - 计算成功率、平均耗时、失败原因列表
    - 成功率 >= 80% 才允许晋升
    """

    def __init__(self, executor: Optional[Any] = None) -> None:
        self._executor = executor

    def evaluate(
        self,
        candidate: dict,
        iterations: int = 10,
        params: Optional[dict] = None,
    ) -> dict:
        """回放候选 Skill。

        参数：
        - candidate: 候选 Skill 描述（包含 skill_id, version, steps 等）
        - iterations: 回放次数（默认 10）
        - params: 每次回放的参数

        返回：
        {
            "success_count": int,
            "failure_count": int,
            "success_rate": float,
            "avg_duration_ms": float,
            "can_promote": bool,
            "failures": [...],
        }
        """
        success_count = 0
        failure_count = 0
        failures: list[dict] = []
        total_duration_ms = 0.0

        for i in range(iterations):
            start = time.time()
            result = self._run_once(candidate, params or {})
            duration_ms = (time.time() - start) * 1000
            total_duration_ms += duration_ms

            if result.get("success"):
                success_count += 1
            else:
                failure_count += 1
                failures.append({
                    "iteration": i + 1,
                    "error": result.get("error"),
                    "duration_ms": duration_ms,
                })

        success_rate = success_count / iterations if iterations > 0 else 0.0
        avg_duration_ms = total_duration_ms / iterations if iterations > 0 else 0.0

        return {
            "success_count": success_count,
            "failure_count": failure_count,
            "success_rate": success_rate,
            "avg_duration_ms": avg_duration_ms,
            "can_promote": success_rate >= 0.8,
            "failures": failures,
            "replay_count": iterations,
        }

    def _run_once(self, candidate: dict, params: dict) -> dict:
        """执行单次回放。

        MVP 阶段：模拟执行（假设成功）。
        当 executor 就绪后，使用真实执行器。
        """
        if self._executor is None:
            # 模拟模式：假设成功
            return {
                "success": True,
                "result": {"simulated": True},
            }

        # 使用真实执行器
        try:
            result = self._executor.execute(candidate, params)
            return result
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
