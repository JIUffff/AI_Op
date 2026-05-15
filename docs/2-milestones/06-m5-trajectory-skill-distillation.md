# 06 - M5 轨迹记录与 Skill 蒸馏

对应总文档第 11 节 M5（第 10-11 周）
前置文档：[../1-standards/00-project-overview.md](../1-standards/00-project-overview.md)、[../2-milestones/05-m4-skill-workflow-executor.md](../2-milestones/05-m4-skill-workflow-executor.md)

---

## 0. 本阶段目标

实现 Trajectory Recorder（执行轨迹记录）、候选 Skill 生成器、自动回放评测与晋升机制。交付物：能从成功/失败轨迹生成候选 Skill，并通过回放评测晋升。

---

## 1. 全局规则速查

- 新轨迹进入候选池，不直接覆盖主 Skill
- 候选版本通过回放评测后再晋升
- 每次发布记录成功率变化与风险说明
- 评测驱动开发：先写评测用例，再写实现代码

---

## 2. 本阶段架构

```
apps/runtime/
  src/
    trajectory/
      recorder.py            # 执行轨迹记录器
      distiller.py           # 候选 Skill 生成器（蒸馏）
      replay.py              # 回放评测器
      promotion.py           # 晋升机制
```

---

## 3. Trajectory Recorder

### 3.1 轨迹数据模型

```python
# apps/runtime/src/trajectory/models.py

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass
class TrajectoryEvent:
    """轨迹事件。"""
    timestamp: str
    event_type: str         # step_start/step_end/verify/recovery/error
    step_id: str
    action: str
    args: dict
    result: dict
    duration_ms: int
    error: Optional[str] = None

@dataclass
class Trajectory:
    """完整执行轨迹。"""
    id: str
    task_id: str
    skill_id: str
    user_input: str
    context: dict
    events: list[TrajectoryEvent] = field(default_factory=list)
    success: bool = False
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    total_duration_ms: int = 0
    recovery_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def add_event(self, event: TrajectoryEvent):
        self.events.append(event)
        if event.event_type == "error":
            self.success = False
        elif event.event_type == "step_end" and event.result.get("success"):
            pass  # 保持当前状态
    
    def mark_success(self):
        self.success = True
        self.finished_at = datetime.now().isoformat()
    
    def mark_failed(self, error: str = ""):
        self.success = False
        self.finished_at = datetime.now().isoformat()
```

### 3.2 Recorder 实现

```python
# apps/runtime/src/trajectory/recorder.py

import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional
from .models import Trajectory, TrajectoryEvent

TRAJECTORY_DIR = Path("data/trajectories")
TRAJECTORY_DIR.mkdir(parents=True, exist_ok=True)

class TrajectoryRecorder:
    """执行轨迹记录器。"""
    
    def __init__(self, db_path: str = "data/db/local-auto.db"):
        self.db_path = db_path
        self._ensure_table()
    
    def _ensure_table(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trajectories (
                id TEXT PRIMARY KEY,
                task_id TEXT,
                skill_id TEXT,
                user_input TEXT,
                context TEXT,
                events TEXT,
                success BOOLEAN,
                started_at TEXT,
                finished_at TEXT,
                total_duration_ms INTEGER,
                recovery_count INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    
    def create_trajectory(self, task_id: str, skill_id: str, user_input: str, context: dict) -> Trajectory:
        """创建新的轨迹记录。"""
        trajectory = Trajectory(
            id=f"traj_{datetime.now().strftime('%Y%m%d%H%M%S')}_{task_id[-6:]}",
            task_id=task_id,
            skill_id=skill_id,
            user_input=user_input,
            context=context,
            started_at=datetime.now().isoformat(),
        )
        return trajectory
    
    def record_event(self, trajectory: Trajectory, event: TrajectoryEvent):
        """记录轨迹事件。"""
        trajectory.add_event(event)
    
    def save_trajectory(self, trajectory: Trajectory):
        """保存轨迹到数据库和文件。"""
        trajectory.total_duration_ms = self._calc_duration(trajectory)
        
        # 保存到 SQLite
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """INSERT INTO trajectories 
               (id, task_id, skill_id, user_input, context, events, success,
                started_at, finished_at, total_duration_ms, recovery_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                trajectory.id,
                trajectory.task_id,
                trajectory.skill_id,
                trajectory.user_input,
                json.dumps(trajectory.context, ensure_ascii=False),
                json.dumps([self._event_to_dict(e) for e in trajectory.events], ensure_ascii=False),
                trajectory.success,
                trajectory.started_at,
                trajectory.finished_at,
                trajectory.total_duration_ms,
                trajectory.recovery_count,
            )
        )
        conn.commit()
        conn.close()
        
        # 同时保存为 JSON 文件（便于后续分析）
        file_path = TRAJECTORY_DIR / f"{trajectory.skill_id.replace('/', '_')}_{trajectory.id}.json"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self._trajectory_to_dict(trajectory), f, indent=2, ensure_ascii=False)
    
    def get_trajectories(self, skill_id: str = None, success: bool = None, limit: int = 100) -> list[dict]:
        """查询轨迹。"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        query = "SELECT * FROM trajectories WHERE 1=1"
        params = []
        
        if skill_id:
            query += " AND skill_id = ?"
            params.append(skill_id)
        if success is not None:
            query += " AND success = ?"
            params.append(success)
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor = conn.execute(query, params)
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows
    
    def get_successful_trajectories(self, skill_id: str, min_count: int = 3) -> list[dict]:
        """获取指定 Skill 的成功轨迹（用于蒸馏）。"""
        return self.get_trajectories(skill_id=skill_id, success=True, limit=min_count * 3)
    
    def _calc_duration(self, trajectory: Trajectory) -> int:
        if trajectory.started_at and trajectory.finished_at:
            start = datetime.fromisoformat(trajectory.started_at)
            finish = datetime.fromisoformat(trajectory.finished_at)
            return int((finish - start).total_seconds() * 1000)
        return 0
    
    def _event_to_dict(self, event: TrajectoryEvent) -> dict:
        return {
            "timestamp": event.timestamp,
            "event_type": event.event_type,
            "step_id": event.step_id,
            "action": event.action,
            "args": event.args,
            "result": event.result,
            "duration_ms": event.duration_ms,
            "error": event.error,
        }
    
    def _trajectory_to_dict(self, trajectory: Trajectory) -> dict:
        return {
            "id": trajectory.id,
            "task_id": trajectory.task_id,
            "skill_id": trajectory.skill_id,
            "user_input": trajectory.user_input,
            "context": trajectory.context,
            "events": [self._event_to_dict(e) for e in trajectory.events],
            "success": trajectory.success,
            "started_at": trajectory.started_at,
            "finished_at": trajectory.finished_at,
            "total_duration_ms": trajectory.total_duration_ms,
            "recovery_count": trajectory.recovery_count,
            "created_at": trajectory.created_at,
        }
```

---

## 4. Skill Distiller（蒸馏器）

### 4.1 蒸馏逻辑

从成功轨迹中提取：
1. 最常见的步骤序列（去掉变化部分）
2. 每个步骤的实际执行参数
3. 触发 recovery 的场景及应对
4. 每步验证的实际结果

### 4.2 实现骨架

```python
# apps/runtime/src/trajectory/distiller.py

import yaml
from pathlib import Path
from typing import Optional
from datetime import datetime
from .recorder import TrajectoryRecorder

class SkillDistiller:
    """候选 Skill 生成器（从轨迹蒸馏）。"""
    
    def __init__(self, recorder: TrajectoryRecorder = None):
        self.recorder = recorder or TrajectoryRecorder()
    
    def distill(self, skill_id: str, min_successful_trajectories: int = 3) -> Optional[dict]:
        """从成功轨迹蒸馏候选 Skill。
        
        Args:
            skill_id: Skill 标识
            min_successful_trajectories: 最少成功轨迹数
        
        Returns:
            候选 Skill 描述字典
        """
        trajectories = self.recorder.get_successful_trajectories(
            skill_id, min_successful_trajectories
        )
        
        if len(trajectories) < min_successful_trajectories:
            return None
        
        # 分析轨迹，提取通用 workflow
        workflow = self._extract_workflow(trajectories)
        recovery = self._extract_recovery(trajectories)
        
        # 生成候选 Skill 目录
        candidate_dir = Path(f"data/skills/{skill_id.replace('/', '/')}_candidate")
        candidate_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成 workflow.yaml
        with open(candidate_dir / "workflow.yaml", "w", encoding="utf-8") as f:
            yaml.safe_dump(workflow, f, default_flow_style=False, allow_unicode=True)
        
        # 生成 recovery.yaml
        with open(candidate_dir / "recovery.yaml", "w", encoding="utf-8") as f:
            yaml.safe_dump(recovery, f, default_flow_style=False, allow_unicode=True)
        
        # 生成 metadata.json
        import json
        meta = {
            "skill_id": f"{skill_id}_candidate",
            "app": skill_id.split("/")[0],
            "name": f"{skill_id.split('/')[1]}_candidate",
            "version": "0.1.0-candidate",
            "description": f"从 {len(trajectories)} 条成功轨迹蒸馏的候选 Skill",
            "status": "candidate",
            "source_trajectories": len(trajectories),
            "created_at": datetime.now().isoformat(),
            "success_rate": 0.0,
            "execution_count": 0,
        }
        with open(candidate_dir / "metadata.json", "w") as f:
            json.dump(meta, f, indent=2)
        
        return {
            "skill_id": meta["skill_id"],
            "directory": str(candidate_dir),
            "source_count": len(trajectories),
            "workflow": workflow,
            "recovery": recovery,
        }
    
    def _extract_workflow(self, trajectories: list[dict]) -> dict:
        """从轨迹提取通用 workflow。"""
        # 简化实现：取第一条成功轨迹的步骤序列
        # 实际应该做序列对齐、可变参数泛化等
        if not trajectories:
            return {}
        
        first = trajectories[0]
        events = yaml.safe_load(first["events"]) if isinstance(first["events"], str) else first["events"]
        
        steps = []
        for event in events:
            if event.get("event_type") == "step_end" and event.get("result", {}).get("success"):
                steps.append({
                    "id": event["step_id"],
                    "action": event["action"],
                    "args": event.get("args", {}),
                    "expect": {},  # 从 result 推断
                    "verify": {},  # 从后续 verify 事件推断
                })
        
        return {
            "skill_id": first["skill_id"],
            "version": "0.1.0-candidate",
            "preconditions": [],
            "steps": steps,
        }
    
    def _extract_recovery(self, trajectories: list[dict]) -> dict:
        """从轨迹提取 recovery 策略。"""
        recovery = {}
        
        for traj in trajectories:
            events = yaml.safe_load(traj["events"]) if isinstance(traj["events"], str) else traj["events"]
            
            for event in events:
                if event.get("event_type") == "error":
                    step_id = event.get("step_id", "")
                    error_msg = event.get("error", "")
                    
                    if step_id not in recovery:
                        recovery[step_id] = []
                    
                    recovery[step_id].append({
                        "if": error_msg,
                        "then": [],  # 从后续事件推断恢复动作
                    })
        
        return {"strategies": recovery}
```

---

## 5. Replay Evaluator（回放评测器）

### 5.1 实现骨架

```python
# apps/runtime/src/trajectory/replay.py

import asyncio
from pathlib import Path
from ..skill.loader import SkillLoader
from ..skill.executor import WorkflowExecutor

class ReplayEvaluator:
    """回放评测器。"""
    
    def __init__(self, executor: WorkflowExecutor = None):
        self.executor = executor or WorkflowExecutor()
        self.loader = SkillLoader()
    
    async def evaluate(self, candidate_skill_dir: Path, times: int = 10, context: dict = None) -> dict:
        """回放评测候选 Skill。
        
        Args:
            candidate_skill_dir: 候选 Skill 目录
            times: 回放次数
            context: 评测上下文
        
        Returns:
            评测结果
        """
        manifest = self.loader.load(candidate_skill_dir)
        if not manifest:
            return {"success": False, "error": "无法加载候选 Skill"}
        
        results = []
        for i in range(times):
            task_id = f"replay_{candidate_skill_dir.name}_{i}"
            result = await self.executor.execute(manifest, context or {}, task_id)
            results.append(result)
        
        success_count = sum(1 for r in results if r.get("success"))
        avg_duration = sum(r.get("duration_ms", 0) for r in results) // max(len(results), 1)
        
        failure_reasons = [
            r.get("error", {}).get("message", "unknown")
            for r in results
            if not r.get("success")
        ]
        
        return {
            "skill_id": manifest.skill_id,
            "attempts": times,
            "success_count": success_count,
            "success_rate": success_count / times,
            "avg_duration_ms": avg_duration,
            "failure_reasons": failure_reasons,
            "promoted": success_count / times >= 0.8,
        }
```

---

## 6. Promotion Mechanism（晋升机制）

```python
# apps/runtime/src/trajectory/promotion.py

import shutil
import json
from pathlib import Path
from datetime import datetime
from .replay import ReplayEvaluator
from ..skill.registry import SkillRegistry

class PromotionEngine:
    """Skill 晋升引擎。"""
    
    def __init__(self, evaluator: ReplayEvaluator = None, registry: SkillRegistry = None):
        self.evaluator = evaluator or ReplayEvaluator()
        self.registry = registry or SkillRegistry()
    
    async def try_promote(self, candidate_dir: Path, replay_times: int = 10) -> dict:
        """尝试晋升候选 Skill。
        
        流程:
        1. 回放评测 10 次
        2. 成功率 >= 80% -> 晋升
        3. 否则 -> 附改进建议
        
        Returns:
            晋升结果
        """
        # 步骤 1: 回放评测
        eval_result = await self.evaluator.evaluate(candidate_dir, times=replay_times)
        
        if eval_result["promoted"]:
            # 步骤 2: 晋升 - 复制文件到正式目录
            app_name = candidate_dir.parent.name
            skill_name = candidate_dir.name.replace("_candidate", "")
            target_dir = Path(f"data/skills/{app_name}/{skill_name}")
            
            if target_dir.exists():
                # 备份旧版本
                backup_dir = Path(f"data/skills/{app_name}/{skill_name}_v{datetime.now().strftime('%Y%m%d')}")
                shutil.copytree(target_dir, backup_dir)
            
            # 复制候选文件
            shutil.copytree(candidate_dir, target_dir, dirs_exist_ok=True)
            
            # 更新 metadata
            meta_path = target_dir / "metadata.json"
            with open(meta_path, "r") as f:
                meta = json.load(f)
            meta["status"] = "active"
            meta["version"] = meta["version"].replace("-candidate", "")
            meta["promotion_date"] = datetime.now().isoformat()
            meta["promotion_eval"] = eval_result
            with open(meta_path, "w") as f:
                json.dump(meta, f, indent=2)
            
            # 更新 Registry 缓存
            self.registry._load_all()
            
            return {
                "action": "promoted",
                "skill_id": meta["skill_id"],
                "eval_result": eval_result,
            }
        else:
            return {
                "action": "rejected",
                "skill_id": eval_result["skill_id"],
                "reason": f"成功率 {eval_result['success_rate']:.0%} < 80%",
                "failure_reasons": eval_result["failure_reasons"],
                "eval_result": eval_result,
            }
```

---

## 7. 与 M4 Workflow Executor 集成

在 M4 的 `WorkflowExecutor.execute()` 方法末尾添加轨迹记录：

```python
# 在 executor.py 的 execute() 方法末尾
async def execute(self, skill: SkillManifest, context: dict, task_id: str) -> dict:
    # ... 原有执行逻辑 ...
    
    # M5 新增: 记录轨迹
    from ..trajectory.recorder import TrajectoryRecorder
    recorder = TrajectoryRecorder()
    
    trajectory = recorder.create_trajectory(task_id, skill.skill_id, "", context)
    for event in self._execution_events:  # 执行过程中收集的事件
        recorder.record_event(trajectory, event)
    
    if result["success"]:
        trajectory.mark_success()
    else:
        trajectory.mark_failed(result.get("error", {}).get("message", ""))
    
    recorder.save_trajectory(trajectory)
    
    return result
```

---

## 8. 实现步骤

| 序号 | 任务 | 预计耗时 | 依赖 |
|------|------|---------|------|
| 1 | 实现 TrajectoryRecorder | 3h | M4 Executor |
| 2 | 实现 SkillDistiller | 3h | 1 |
| 3 | 实现 ReplayEvaluator | 2h | M4 Executor |
| 4 | 实现 PromotionEngine | 2h | 2,3 |
| 5 | 修改 Executor 集成轨迹记录 | 1h | 1 |
| 6 | 端到端测试：运行 Skill -> 记录轨迹 -> 蒸馏 -> 回放 -> 晋升 | 3h | 1-5 |

---

## 9. 测试与验收标准

- [ ] `TrajectoryRecorder` 可记录并查询轨迹
- [ ] 轨迹保存为 JSON 文件到 `data/trajectories/`
- [ ] `SkillDistiller.distill()` 从 3+ 条成功轨迹生成候选 Skill
- [ ] 候选 Skill 目录包含 workflow.yaml + recovery.yaml + metadata.json
- [ ] `ReplayEvaluator.evaluate()` 可回放候选 Skill 10 次
- [ ] `PromotionEngine.try_promote()` 在成功率 >= 80% 时晋升
- [ ] 晋升后旧版本被备份
- [ ] 成功率 < 80% 时返回拒绝原因

---

## 10. 交付物清单

| 交付物 | 路径 | 状态 |
|--------|------|------|
| TrajectoryRecorder | apps/runtime/src/trajectory/recorder.py | - |
| SkillDistiller | apps/runtime/src/trajectory/distiller.py | - |
| ReplayEvaluator | apps/runtime/src/trajectory/replay.py | - |
| PromotionEngine | apps/runtime/src/trajectory/promotion.py | - |
| 端到端测试 | tests/test_trajectory_e2e.py | - |

---

## 11. 风险与注意事项

| 风险 | 级别 | 应对 |
|------|------|------|
| 蒸馏算法过于简单（只取第一条轨迹） | HIGH | M5 MVP 接受简化实现，二期做序列对齐和参数泛化 |
| 回放环境不一致导致评测不准确 | MEDIUM | 使用隔离环境，回放前重置测试夹具 |
| 轨迹数据膨胀 | LOW | 定期归档旧轨迹，保留最近 30 天 |
| 晋升后的 Skill 与旧版本不兼容 | MEDIUM | 晋升前做 diff 分析，标注变更点 |

---

## 12. 相关文档

- [../1-standards/00-project-overview.md](../1-standards/00-project-overview.md) - 全局规范
- [../2-milestones/05-m4-skill-workflow-executor.md](../2-milestones/05-m4-skill-workflow-executor.md) - 前置阶段
- [../1-standards/02-evaluation-handbook.md](../1-standards/02-evaluation-handbook.md) - 评测流程
- [../2-milestones/07-m6-mvp-closure.md](../2-milestones/07-m6-mvp-closure.md) - 下一阶段
