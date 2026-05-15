# 01 - M0 工程底座搭建

对应总文档第 11 节 M0（第 1 周）
前置文档：[../1-standards/00-project-overview.md](../1-standards/00-project-overview.md)

---

## 0. 本阶段目标

初始化 Monorepo 结构，搭建本地开发脚本、日志/错误码规范落地，定义 MCP Schema v1，实现一条空任务从 UI -> Runtime -> MCP -> 日志的完整贯穿。

---

## 1. 全局规则速查

- MVP 只做 Windows + 三应用 + 三任务
- 安全底线：默认拒绝、L5-L7 需确认、零高风险误执行
- 控制路径优先级：CLI/API > 文件系统 > Accessibility > DOM/CDP > Vision > 鼠标键盘
- 详见：[../1-standards/00-project-overview.md](../1-standards/00-project-overview.md)

---

## 2. 本阶段架构

本阶段只搭建骨架，不涉及实际业务引擎。

```
apps/desktop/          -> 一个输入框 + 提交按钮 + 日志查看面板
apps/runtime/          -> 接收任务 -> 调用 MCP -> 记录日志
crates/mcp-gateway/    -> 接收工具调用 -> 返回模拟响应
```

数据流：
```
UI (输入 "test") -> POST /api/tasks -> Runtime 创建任务
  -> Runtime 调用 MCP tools/call -> MCP 返回 mock
    -> Runtime 记录任务完成 -> UI 显示结果
```

---

## 3. MCP Schema v1

### 3.1 协议

- 传输：HTTP + JSON（MVP 用 HTTP，二期切 stdio/SSE）
- 地址：`http://127.0.0.1:8900`
- 认证：本地开发阶段无需认证，生产阶段加 token

### 3.2 API 端点

```
GET  /mcp/tools          -> 列出已注册工具
POST /mcp/tools/call     -> 调用指定工具
GET  /mcp/health         -> 健康检查
```

### 3.3 请求/响应格式

#### 调用工具

请求：
```json
{
  "tool": "file_read",
  "arguments": {
    "path": "C:\\Users\\Public\\test.txt"
  },
  "task_id": "task_001",
  "step_id": "step_001"
}
```

响应（成功）：
```json
{
  "success": true,
  "result": {
    "content": "file content here",
    "size_bytes": 1024
  },
  "duration_ms": 50
}
```

响应（失败）：
```json
{
  "success": false,
  "error": {
    "code": "E4002",
    "message": "路径不在白名单内"
  },
  "duration_ms": 5
}
```

### 3.4 MVP 工具列表

| 工具名 | 权限级别 | 描述 |
|--------|---------|------|
| `file_read` | L1 | 读取白名单内文件 |
| `file_write` | L5 | 写入白名单内文件 |
| `app_list` | L0 | 列出已安装应用 |
| `app_launch` | L2 | 启动指定应用 |
| `cmd_exec` | L6 | 执行允许名单内命令 |
| `system_info` | L0 | 获取系统基础信息 |

每个工具的注册格式：
```json
{
  "name": "file_read",
  "description": "读取指定路径的文件内容",
  "permission_level": 1,
  "input_schema": {
    "type": "object",
    "properties": {
      "path": { "type": "string", "description": "文件绝对路径" }
    },
    "required": ["path"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "content": { "type": "string" },
      "size_bytes": { "type": "integer" }
    }
  }
}
```

---

## 4. Runtime 空任务实现

### 4.1 LangGraph 状态定义

```python
# apps/runtime/src/state.py

from typing import TypedDict, Optional
from datetime import datetime

class TaskState(TypedDict):
    task_id: str
    user_input: str
    skill_id: Optional[str]
    status: str          # pending/running/success/failed
    steps: list[str]     # 步骤日志
    current_step: int
    error_code: Optional[str]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    recovery_attempted: bool
```

### 4.2 空任务图

```python
# apps/runtime/src/graph.py

from langgraph.graph import StateGraph, END
from .state import TaskState

def parse_intent(state: TaskState) -> TaskState:
    """解析用户意图（MVP 阶段写死路由）。"""
    # MVP: 空任务直接标记成功
    state["steps"].append("intent_parsed: mock_task")
    return state

def execute_step(state: TaskState) -> TaskState:
    """执行步骤（MVP 调用 MCP mock）。"""
    state["steps"].append("step_executed: mock")
    return state

def verify_result(state: TaskState) -> TaskState:
    """验证结果（MVP 直接通过）。"""
    state["steps"].append("result_verified: ok")
    state["status"] = "success"
    return state

# 构建图
workflow = StateGraph(TaskState)
workflow.add_node("parse", parse_intent)
workflow.add_node("execute", execute_step)
workflow.add_node("verify", verify_result)

workflow.set_entry_point("parse")
workflow.add_edge("parse", "execute")
workflow.add_edge("execute", "verify")
workflow.add_edge("verify", END)

app = workflow.compile()
```

### 4.3 HTTP API

```python
# apps/runtime/src/api.py

from fastapi import FastAPI
from pydantic import BaseModel
from .graph import app as graph_app
from .state import TaskState
import uuid
from datetime import datetime

api = FastAPI(title="Local Auto Runtime")

class CreateTaskRequest(BaseModel):
    user_input: str

class TaskResponse(BaseModel):
    task_id: str
    status: str
    steps: list[str]

@api.post("/api/tasks", response_model=TaskResponse)
async def create_task(req: CreateTaskRequest):
    state: TaskState = {
        "task_id": f"task_{uuid.uuid4().hex[:8]}",
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
    
    result = await graph_app.ainvoke(state)
    result["finished_at"] = datetime.now()
    
    return TaskResponse(
        task_id=result["task_id"],
        status=result["status"],
        steps=result["steps"],
    )

@api.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    # MVP: 从内存返回，后续接 SQLite
    return {"task_id": task_id, "status": "not_implemented"}
```

---

## 5. 前端空任务 UI

### 5.1 页面结构

```
apps/desktop/src/
  App.tsx              # 主布局
  components/
    TaskInput.tsx      # 输入框 + 提交按钮
    TaskLog.tsx        # 步骤日志面板
    TaskStatus.tsx     # 任务状态显示
  stores/
    taskStore.ts       # Zustand 状态管理
  api/
    client.ts          # HTTP 客户端
```

### 5.2 最小实现

```tsx
// apps/desktop/src/App.tsx
import { TaskInput } from "./components/TaskInput"
import { TaskLog } from "./components/TaskLog"
import { useTaskStore } from "./stores/taskStore"

function App() {
  const status = useTaskStore((s) => s.status)
  return (
    <div className="p-4 max-w-2xl mx-auto">
      <h1 className="text-xl font-bold mb-4">Local AI Skill OS</h1>
      <TaskInput />
      {status && <TaskLog />}
    </div>
  )
}
export default App
```

---

## 6. MCP Gateway 最小实现

```rust
// crates/mcp-gateway/src/main.rs

use axum::{
    routing::{get, post},
    Json, Router,
};
use serde::{Deserialize, Serialize};

#[derive(Deserialize)]
struct ToolCallRequest {
    tool: String,
    arguments: serde_json::Value,
    task_id: String,
    step_id: String,
}

#[derive(Serialize)]
struct ToolCallResponse {
    success: bool,
    result: Option<serde_json::Value>,
    error: Option<ErrorDetail>,
    duration_ms: u64,
}

#[derive(Serialize)]
struct ErrorDetail {
    code: String,
    message: String,
}

async fn health() -> &'static str {
    "ok"
}

async fn list_tools() -> Json<serde_json::Value> {
    // MVP: 返回静态工具列表
    Json(serde_json::json!({
        "tools": ["file_read", "file_write", "app_list", "app_launch", "cmd_exec", "system_info"]
    }))
}

async fn call_tool(Json(req): Json<ToolCallRequest>) -> Json<ToolCallResponse> {
    // MVP: 所有工具返回 mock
    Json(ToolCallResponse {
        success: true,
        result: Some(serde_json::json!({"mock": true, "tool": req.tool})),
        error: None,
        duration_ms: 10,
    })
}

#[tokio::main]
async fn main() {
    let app = Router::new()
        .route("/mcp/health", get(health))
        .route("/mcp/tools", get(list_tools))
        .route("/mcp/tools/call", post(call_tool));

    let listener = tokio::net::TcpListener::bind("127.0.0.1:8900")
        .await
        .unwrap();
    
    println!("MCP Gateway listening on 127.0.0.1:8900");
    axum::serve(listener, app).await.unwrap();
}
```

---

## 7. 日志系统初始化

```python
# apps/runtime/src/logging.py

import logging
import json
from pathlib import Path
from datetime import datetime

LOG_DIR = Path("data/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "task_id"):
            log_entry["task_id"] = record.task_id
        if hasattr(record, "step_id"):
            log_entry["step_id"] = record.step_id
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)

def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # 控制台 handler
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    console.setFormatter(JsonFormatter())
    logger.addHandler(console)
    
    # 文件 handler（按天滚动）
    date_str = datetime.now().strftime("%Y-%m-%d")
    file_handler = logging.FileHandler(
        LOG_DIR / f"runtime-{date_str}.log",
        encoding="utf-8",
    )
    file_handler.setLevel(logging.TRACE if hasattr(logging, "TRACE") else logging.DEBUG)
    file_handler.setFormatter(JsonFormatter())
    logger.addHandler(file_handler)
    
    return logger
```

---

## 8. 数据库初始化

```python
# apps/runtime/src/db.py

import sqlite3
from pathlib import Path

DB_DIR = Path("data/db")
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "local-auto.db"

SCHEMA_SQL = """
-- 见 ../1-standards/00-project-overview.md 第 8 节
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,
  skill_id TEXT,
  status TEXT,
  started_at TEXT,
  finished_at TEXT,
  duration_ms INTEGER,
  error_code TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA_SQL)
    conn.close()
```

---

## 9. 开发脚本

```bash
# scripts/dev.sh - 一键启动开发环境

#!/bin/bash
set -e

echo "=== Local Auto Dev Environment ==="

# 1. 初始化数据库
echo "[1/3] Initializing database..."
python apps/runtime/src/db.py

# 2. 启动 MCP Gateway
echo "[2/3] Starting MCP Gateway..."
(cd crates/mcp-gateway && cargo run &)
MCP_PID=$!

# 3. 启动 Runtime
echo "[3/3] Starting Runtime..."
(cd apps/runtime && uvicorn src.api:api --reload --port 8800 &)
RUNTIME_PID=$!

# 4. 启动前端（需要用户手动在新终端运行）
echo "MCP Gateway: http://127.0.0.1:8900"
echo "Runtime API: http://127.0.0.1:8800"
echo "Frontend:    cd apps/desktop && pnpm dev"

trap "kill $MCP_PID $RUNTIME_PID" EXIT

# 等待中断
wait
```

---

## 10. 实现步骤

| 序号 | 任务 | 预计耗时 | 依赖 |
|------|------|---------|------|
| 1 | 创建 Monorepo 目录结构 | 30min | 无 |
| 2 | 初始化 Python Runtime（FastAPI + LangGraph） | 2h | 无 |
| 3 | 初始化 Rust MCP Gateway（Axum） | 2h | 无 |
| 4 | 初始化 Tauri 前端 | 2h | 无 |
| 5 | 实现空任务贯穿流程 | 2h | 2,3,4 |
| 6 | 实现日志系统 | 1h | 2 |
| 7 | 实现数据库初始化 | 1h | 2 |
| 8 | 编写开发脚本 | 30min | 2,3 |
| 9 | 编写单元测试 | 2h | 2,3,5 |
| 10 | E2E 验证空任务流程 | 1h | 5,6,7 |

---

## 11. 测试与验收标准

### 11.1 单元测试

- Runtime: `parse_intent`、`execute_step`、`verify_result` 各 1 个测试
- MCP: `/health` 返回 "ok"、`/tools/call` 返回 mock
- 前端: TaskInput 提交后调用 API

### 11.2 验收标准

- [ ] `cargo run` 启动 MCP Gateway，`curl http://127.0.0.1:8900/mcp/health` 返回 "ok"
- [ ] `uvicorn` 启动 Runtime，`curl -X POST http://127.0.0.1:8800/api/tasks -d '{"user_input":"test"}'` 返回成功
- [ ] 前端输入 "test" 点击提交，页面显示任务成功日志
- [ ] `data/logs/runtime-{date}.log` 包含任务完整执行链路
- [ ] `data/db/local-auto.db` 包含 tasks 表，有一条记录
- [ ] 一条空任务可贯穿 UI -> Runtime -> MCP -> 日志

### 11.3 测试命令

```bash
# Python 测试
cd apps/runtime && pytest -v

# Rust 测试
cd crates/mcp-gateway && cargo test

# TypeScript 测试
cd apps/desktop && pnpm test
```

---

## 12. 交付物清单

| 交付物 | 路径 | 状态 |
|--------|------|------|
| Monorepo 结构 | 项目根目录 | - |
| Runtime 空任务实现 | apps/runtime/src/ | - |
| MCP Gateway 最小实现 | crates/mcp-gateway/src/ | - |
| 前端输入框 + 日志面板 | apps/desktop/src/ | - |
| 日志系统 | apps/runtime/src/logging.py | - |
| 数据库初始化 | apps/runtime/src/db.py | - |
| 开发脚本 | scripts/dev.sh | - |
| MCP Schema v1 | docs/mcp-schema-v1.json | - |
| 单元测试 | apps/runtime/tests/、crates/mcp-gateway/tests/ | - |

---

## 13. 风险与注意事项

| 风险 | 级别 | 应对 |
|------|------|------|
| Rust/Python/TS 三环境配置复杂 | HIGH | 使用版本管理工具（rustup/pyenv/nvm），写入 README |
| Tauri v2 在 Windows 上可能有兼容性问题 | MEDIUM | 提前安装 Visual Studio Build Tools |
| LangGraph 持久化 checkpoint 方案未定 | MEDIUM | M0 先用内存状态，M1 再实现 SQLite 持久化 |
| 前端与 Runtime 跨域问题 | LOW | 开发阶段用 proxy，Tauri 原生无此问题 |

---

## 14. 相关文档

- [../1-standards/00-project-overview.md](../1-standards/00-project-overview.md) - 全局规范
- [../1-standards/01-dev-conventions.md](../1-standards/01-dev-conventions.md) - 代码/提交/CI 规范
- [../1-standards/02-evaluation-handbook.md](../1-standards/02-evaluation-handbook.md) - 评测流程
- [../0-specs/00-project-requirements.md](../0-specs/00-project-requirements.md) - 总文档
