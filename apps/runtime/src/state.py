from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional, Literal


VALID_STATUSES = {"pending", "running", "success", "failed", "recovered"}


class TaskState(BaseModel):
    task_id: str = Field(..., description="Unique task identifier")
    user_input: str = Field(default="", description="User's task description")
    skill_id: Optional[str] = Field(default=None, description="Associated skill ID")
    status: Literal["pending", "running", "success", "failed", "recovered"] = Field(
        default="pending", description="Current task status"
    )
    steps: list[str] = Field(default_factory=list, description="Executed step log")
    current_step: int = Field(default=0, ge=0, description="Current step index")
    error_code: Optional[str] = Field(default=None, description="Error code if failed")
    started_at: Optional[datetime] = Field(default=None, description="Task start time")
    finished_at: Optional[datetime] = Field(default=None, description="Task end time")
    recovery_attempted: bool = Field(default=False, description="Whether recovery was tried")

    @field_validator("current_step")
    @classmethod
    def step_must_be_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("current_step must be non-negative")
        return v
