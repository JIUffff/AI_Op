import logging
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .state import TaskState
from .graph import create_workflow
from .engines.app_scanner import AppScanner
from .engines.process_engine import ProcessEngine
from .engines.app_profile import AppProfileManager
from .engines.vscode_engine import VSCodeEngine
from .engines.chrome_engine import ChromeEngine
from .engines.file_engine import FileEngine
from .skills.registry import SkillRegistry
from .skills.executor import WorkflowExecutor
from .trajectory.recorder import TrajectoryRecorder
from .skills.models import SkillStep

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("runtime.api")

api = FastAPI(
    title="Local Auto Runtime",
    description="本地 AI Skill 自动化运行时 API\n\n提供任务执行、技能管理、应用控制和文件操作等功能。",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "Tasks", "description": "任务创建和查询"},
        {"name": "Skills", "description": "技能列表、详情和执行"},
        {"name": "Apps", "description": "应用扫描、启动和配置查询"},
        {"name": "Health", "description": "服务健康检查"},
    ],
)

api.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

workflow = create_workflow()
task_store: dict[str, TaskState] = {}
skill_registry = SkillRegistry()
trajectory_recorder = TrajectoryRecorder()

# M6 真实引擎
vscode_engine = VSCodeEngine()
chrome_engine = ChromeEngine()
file_engine = FileEngine()

workflow_executor = WorkflowExecutor(recorder=trajectory_recorder)

# 注册引擎
workflow_executor.register_engine("vscode", vscode_engine)
workflow_executor.register_engine("chrome", chrome_engine)
workflow_executor.register_engine("file_engine", file_engine)


class CreateTaskRequest(BaseModel):
    user_input: str


class TaskListResponse(BaseModel):
    tasks: list[dict]
    total: int


class TaskResponse(BaseModel):
    task_id: str
    status: str
    steps: list[str]


class AppInfoResponse(BaseModel):
    app_id: str
    display_name: str
    category: str
    executable_path: str
    supports_cli: bool = False
    supports_cdp: bool = False


class AppProfileResponse(BaseModel):
    app_id: str
    display_name: str
    category: str
    automation_method: str
    cli_command: str | None = None
    window_patterns: list[str] = []


class LaunchAppRequest(BaseModel):
    app_id: str


class LaunchAppResponse(BaseModel):
    success: bool
    pid: int | None
    error: str | None


class ExecuteSkillRequest(BaseModel):
    skill_id: str
    params: dict = {}


class SkillInfoResponse(BaseModel):
    skill_id: str
    display_name: str
    version: str
    description: str
    category: str
    step_count: int


class SkillDetailResponse(BaseModel):
    skill_id: str
    display_name: str
    version: str
    description: str
    category: str
    steps: list[dict]


class SkillExecuteResponse(BaseModel):
    success: bool
    result: dict | None
    error: dict | None
    steps_executed: list[dict] = []


@api.post("/api/tasks", response_model=TaskResponse, tags=["Tasks"], summary="创建并执行任务")
async def create_task(req: CreateTaskRequest):
    """接收用户自然语言输入，通过 LangGraph 工作流执行任务。

    - 解析用户意图并路由到对应技能
    - 执行技能步骤
    - 返回任务结果
    """
    state = TaskState(
        task_id=f"task_{len(task_store) + 1:04d}",
        user_input=req.user_input,
        skill_id=None,
        status="pending",
        steps=[],
        current_step=0,
        error_code=None,
        started_at=datetime.now(),
        finished_at=None,
        recovery_attempted=False,
    )

    result = await workflow.ainvoke(state.model_dump())
    result["finished_at"] = datetime.now()

    task_store[result["task_id"]] = result

    logger.info(f"Task {result['task_id']} completed: {result['status']}")

    return TaskResponse(
        task_id=result["task_id"],
        status=result["status"],
        steps=result["steps"],
    )


@api.get("/api/tasks", response_model=TaskListResponse, tags=["Tasks"], summary="查询任务列表")
async def list_tasks():
    """返回所有已创建任务的摘要列表。"""
    tasks = []
    for task in task_store.values():
        tasks.append({
            "task_id": task["task_id"],
            "status": task["status"],
            "steps": task["steps"],
            "started_at": task["started_at"].isoformat() if task["started_at"] else None,
            "finished_at": task["finished_at"].isoformat() if task["finished_at"] else None,
        })
    return TaskListResponse(tasks=tasks, total=len(tasks))


@api.get("/api/tasks/{task_id}", tags=["Tasks"], summary="查询单个任务详情")
async def get_task(task_id: str):
    """根据 task_id 获取单个任务的详细信息。"""
    task = task_store.get(task_id)
    if not task:
        return {"error": "Task not found"}
    return {
        "task_id": task["task_id"],
        "status": task["status"],
        "steps": task["steps"],
        "started_at": task["started_at"].isoformat() if task["started_at"] else None,
        "finished_at": task["finished_at"].isoformat() if task["finished_at"] else None,
    }


@api.get("/api/apps", response_model=list[AppInfoResponse], tags=["Apps"], summary="列出已安装应用")
async def list_apps():
    """扫描系统已安装的应用，返回应用列表。"""
    scanner = AppScanner()
    apps = scanner.scan()
    return [
        AppInfoResponse(
            app_id=app.app_id,
            display_name=app.display_name,
            category=app.category,
            executable_path=str(app.executable_path),
        )
        for app in apps
    ]


@api.post("/api/apps/launch", response_model=LaunchAppResponse, tags=["Apps"], summary="启动应用")
async def launch_app(req: LaunchAppRequest):
    """启动指定应用。如果应用已在运行，则将其窗口前置。"""
    scanner = AppScanner()
    app_info = scanner.get_app(req.app_id)
    if not app_info:
        return LaunchAppResponse(success=False, pid=None, error=f"App not found: {req.app_id}")

    engine = ProcessEngine()
    exe_name = app_info.executable_path.name

    if engine.is_process_running(exe_name):
        windows = engine.find_windows_by_title(app_info.display_name)
        if windows:
            engine.bring_window_to_front(windows[0]["hwnd"])
            return LaunchAppResponse(
                success=True,
                pid=windows[0]["pid"],
                error=None,
            )

    result = engine.launch_app(app_info.executable_path)

    return LaunchAppResponse(
        success=result["success"],
        pid=result.get("pid"),
        error=result.get("error"),
    )


@api.get("/api/apps/{app_id}/profile", response_model=AppProfileResponse | None, tags=["Apps"], summary="查询应用配置")
async def get_app_profile(app_id: str):
    """获取指定应用的自动化配置信息，包括自动化方法、CLI 命令和窗口匹配模式。"""
    profile_manager = AppProfileManager()
    profile = profile_manager.load(app_id)
    if not profile:
        return None
    return AppProfileResponse(
        app_id=profile.app_id,
        display_name=profile.display_name,
        category=profile.category,
        automation_method=profile.automation.preferred_method,
        cli_command=profile.automation.cli_command,
        window_patterns=profile.window_patterns,
    )


@api.get("/api/health", tags=["Health"], summary="服务健康检查")
async def health():
    """检查服务是否正常运行。"""
    return {"status": "ok"}


@api.get("/api/skills", response_model=list[SkillInfoResponse], tags=["Skills"], summary="列出所有可用技能")
async def list_skills():
    """返回所有已注册的技能列表，包含基本信息和步骤数量。"""
    skills = skill_registry.list_all()
    return [
        SkillInfoResponse(
            skill_id=s.skill_id,
            display_name=s.display_name,
            version=s.version,
            description=s.description,
            category=s.category,
            step_count=len(s.steps),
        )
        for s in skills
    ]


@api.get("/api/skills/{skill_id}", response_model=SkillDetailResponse, tags=["Skills"], summary="获取技能详情")
async def get_skill(skill_id: str):
    """根据 skill_id 获取技能的详细信息，包括完整步骤列表。"""
    skill = skill_registry.load(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")
    return SkillDetailResponse(
        skill_id=skill.skill_id,
        display_name=skill.display_name,
        version=skill.version,
        description=skill.description,
        category=skill.category,
        steps=[s.model_dump() for s in skill.steps],
    )


@api.post("/api/skills/execute", response_model=SkillExecuteResponse, tags=["Skills"], summary="执行技能")
async def execute_skill(req: ExecuteSkillRequest):
    """执行指定技能，可传入自定义参数。

    - 技能必须在注册表中存在
    - 参数将合并到技能步骤的模板参数中
    - 返回执行结果和已执行的步骤
    """
    skill = skill_registry.load(req.skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill not found: {req.skill_id}")
    result = workflow_executor.execute(skill, req.params)
    return SkillExecuteResponse(
        success=result["success"],
        result=result.get("result"),
        error=result.get("error"),
        steps_executed=result.get("steps_executed", []),
    )


class MaintenanceResponse(BaseModel):
    database: dict
    backups: dict
    logs: dict
    rollback_log: dict


class BackupResponse(BaseModel):
    success: bool
    backup_path: str | None
    size_bytes: int
    error: str | None


class RestoreRequest(BaseModel):
    backup_path: str


class RestoreResponse(BaseModel):
    success: bool
    restored_path: str | None
    error: str | None


class RotateResponse(BaseModel):
    rotated: int
    deleted: int
    total_size_before: int
    total_size_after: int


@api.get("/api/maintenance/status", response_model=MaintenanceResponse, tags=["Health"], summary="查看维护状态")
async def get_maintenance_status():
    """返回数据库、备份、日志的当前状态摘要。"""
    from src.maintenance import maintenance_status
    status = maintenance_status()
    return MaintenanceResponse(**status)


@api.post("/api/maintenance/backup", response_model=BackupResponse, tags=["Health"], summary="备份数据库")
async def backup_database():
    """创建 SQLite 数据库的 gzip 压缩备份，自动清理超过 7 天的旧备份。"""
    from src.maintenance import backup_database
    result = backup_database()
    return BackupResponse(**result)


@api.post("/api/maintenance/restore", response_model=RestoreResponse, tags=["Health"], summary="恢复数据库")
async def restore_database(req: RestoreRequest):
    """从指定的备份文件恢复数据库。"""
    from src.maintenance import restore_database
    result = restore_database(req.backup_path)
    return RestoreResponse(**result)


@api.post("/api/maintenance/rotate-logs", response_model=RotateResponse, tags=["Health"], summary="滚动日志文件")
async def rotate_logs():
    """压缩超过 10MB 的日志文件，删除超过 5 个的旧日志。"""
    from src.maintenance import rotate_logs
    result = rotate_logs()
    return RotateResponse(**result)
