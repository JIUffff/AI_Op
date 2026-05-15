import logging
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .state import TaskState
from .graph import create_workflow
from .engines.app_scanner import AppScanner
from .engines.process_engine import ProcessEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("runtime.api")

api = FastAPI(title="Local Auto Runtime")

api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

workflow = create_workflow()
task_store: dict[str, TaskState] = {}


class CreateTaskRequest(BaseModel):
    user_input: str


class TaskResponse(BaseModel):
    task_id: str
    status: str
    steps: list[str]


class AppInfoResponse(BaseModel):
    app_id: str
    display_name: str
    category: str
    executable_path: str


class LaunchAppRequest(BaseModel):
    app_id: str


class LaunchAppResponse(BaseModel):
    success: bool
    pid: int | None
    error: str | None


@api.post("/api/tasks", response_model=TaskResponse)
async def create_task(req: CreateTaskRequest):
    state: TaskState = {
        "task_id": f"task_{len(task_store) + 1:04d}",
        "user_input": req.user_input,
        "skill_id": None,
        "status": "pending",
        "steps": [],
        "current_step": 0,
        "error_code": None,
        "started_at": datetime.now(),
        "finished_at": None,
        "recovery_attempted": False,
    }

    result = await workflow.ainvoke(state)
    result["finished_at"] = datetime.now()

    task_store[result["task_id"]] = result

    logger.info(f"Task {result['task_id']} completed: {result['status']}")

    return TaskResponse(
        task_id=result["task_id"],
        status=result["status"],
        steps=result["steps"],
    )


@api.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
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


@api.get("/api/apps", response_model=list[AppInfoResponse])
async def list_apps():
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


@api.post("/api/apps/launch", response_model=LaunchAppResponse)
async def launch_app(req: LaunchAppRequest):
    scanner = AppScanner()
    app_info = scanner.get_app(req.app_id)
    if not app_info:
        return LaunchAppResponse(success=False, pid=None, error=f"App not found: {req.app_id}")

    engine = ProcessEngine()
    result = engine.launch_app(app_info.executable_path)

    return LaunchAppResponse(
        success=result["success"],
        pid=result.get("pid"),
        error=result.get("error"),
    )


@api.get("/api/health")
async def health():
    return {"status": "ok"}
