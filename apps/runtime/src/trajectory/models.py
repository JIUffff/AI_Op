"""M5 轨迹模块数据模型。"""
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field


class TrajectoryEvent(BaseModel):
    """单个执行事件。"""
    event_type: str  # step_start, step_end, verify, recovery, error
    skill_id: str
    step_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    details: dict[str, Any] = Field(default_factory=dict)


class Trajectory(BaseModel):
    """完整的执行轨迹。"""
    trajectory_id: str = Field(..., description="唯一轨迹 ID")
    skill_id: str
    skill_version: str
    status: str = "running"  # running, success, failed, recovered
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    events: list[TrajectoryEvent] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    result: Optional[dict[str, Any]] = None
    error: Optional[dict[str, Any]] = None
    duration_ms: Optional[float] = None


class CandidateSkill(BaseModel):
    """候选 Skill 元数据。"""
    skill_id: str
    version: str
    status: str = "candidate"  # candidate, active, archived
    source_trajectories: list[str] = Field(default_factory=list)
    success_rate: Optional[float] = None
    replay_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    promoted_at: Optional[datetime] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
