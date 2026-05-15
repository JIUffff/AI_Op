from typing import TypedDict, Optional
from datetime import datetime


class TaskState(TypedDict):
    task_id: str
    user_input: str
    skill_id: Optional[str]
    status: str
    steps: list[str]
    current_step: int
    error_code: Optional[str]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    recovery_attempted: bool
