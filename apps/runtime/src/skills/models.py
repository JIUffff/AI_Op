from pydantic import BaseModel, Field
from typing import Optional


class SkillVerify(BaseModel):
    """步骤验证配置。"""
    type: str = Field(..., description="验证类型：uia/process/assertion")
    method: str = Field(..., description="验证方法名")
    args: dict = Field(default_factory=dict, description="验证参数")


class SkillExpect(BaseModel):
    """步骤期望结果。"""
    description: str = Field(default="", description="期望描述")
    conditions: dict = Field(default_factory=dict, description="期望条件键值对")


class SkillStep(BaseModel):
    """Skill 工作流中的单个步骤。"""
    step_id: str = Field(..., description="唯一步骤 ID")
    action: str = Field(..., description="引擎动作")
    engine: str = Field(default="unknown", description="目标引擎名称")
    args: dict = Field(default_factory=dict, description="动作参数")
    params: dict = Field(default_factory=dict, description="兼容旧版参数")
    timeout: float = Field(default=30.0, ge=0, description="步骤超时（秒）")
    retry_count: int = Field(default=0, ge=0, description="重试次数")
    expect: Optional[SkillExpect] = Field(default=None, description="期望结果")
    verify: Optional[SkillVerify] = Field(default=None, description="验证配置")


class RecoveryStrategy(BaseModel):
    """恢复策略。"""
    if_condition: str = Field(..., description="触发条件")
    then_actions: list[dict] = Field(default_factory=list, description="恢复动作列表")
    retry_original: bool = Field(default=False, description="是否重试原始步骤")


class SkillRecovery(BaseModel):
    """步骤失败时的恢复配置。"""
    strategies: dict[str, list[RecoveryStrategy]] = Field(default_factory=dict, description="按步骤 ID 索引的恢复策略")


class RollbackAction(BaseModel):
    """回滚动作。"""
    action: str = Field(..., description="回滚动作名")
    args: dict = Field(default_factory=dict, description="回滚参数")
    condition: str = Field(default="", description="回滚条件")


class SkillPrecondition(BaseModel):
    """Skill 前置条件。"""
    type: str = Field(..., description="条件类型：app_installed/file_exists/directory_exists")
    value: str = Field(..., description="条件值")


class SkillModel(BaseModel):
    """完整的 Skill 定义（从 YAML 加载）。"""
    skill_id: str = Field(..., description="唯一 Skill ID")
    display_name: str = Field(..., description="人类可读名称")
    version: str = Field(..., description="语义化版本号")
    description: str = Field(default="", description="Skill 描述")
    category: str = Field(default="general", description="Skill 分类")
    required_engines: list[str] = Field(default_factory=list, description="依赖的引擎列表")

    # 工作流定义
    preconditions: list[SkillPrecondition] = Field(default_factory=list, description="前置条件列表")
    steps: list[SkillStep] = Field(..., min_length=1, description="有序步骤列表")
    recovery: Optional[SkillRecovery] = Field(default=None, description="恢复策略")
    rollback: list[RollbackAction] = Field(default_factory=list, description="回滚动作列表")

    # 元数据
    metadata: dict = Field(default_factory=dict, description="附加元数据")
