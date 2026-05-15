# 00 - 项目总览与开发规范

版本：v1.0
日期：2026-05-15
状态：可执行

本文档从总文档 [个人本地 AI Skill OS 项目需求与开发文档.md](../0-specs/00-project-requirements.md) 中提取全局规则，并补充缺失的技术规范。

---

## 0. 一句话定位

一个运行在个人电脑上的本地 Agent 执行系统：能理解应用、稳定调用工具、沉淀可复用 Skill，并在失败后自我修复。

---

## 1. 全局规则（所有阶段必须遵守）

### 1.1 范围红线

- MVP 只做 Windows 平台
- MVP 只做三应用：VSCode / Chrome / 文件管理器
- MVP 只做三任务闭环
- 跨平台、全应用、插件市场全部后置到二期

### 1.2 安全底线

- 默认拒绝，按任务临时授权
- L5-L7 操作必须用户确认
- 高风险误执行 = 0（出厂门槛，不可妥协）
- 所有写操作必须记录可逆元数据，支持回滚
- 敏感目录默认屏蔽：Cookie、密码库、私钥、凭据、认证 Token

### 1.3 控制路径优先级

固定顺序：CLI/API > 文件系统 > Accessibility > DOM/CDP > Vision > 鼠标键盘模拟

### 1.4 Skill 定义

Skill 必须是"可执行资产"，不是自由文本 Prompt。每个 Skill 必须包含：preconditions、steps、expect、verify、recovery、rollback。

---

## 2. 架构总览

```txt
Desktop UI (Tauri + React)
  -> Agent Runtime (Python + LangGraph)
  -> Local MCP Gateway (Rust)
  -> Capability Engines (App/UI/File/Process/Vision/Security/Audit)
  -> OS Adapters (Win UIA, Win32, PowerShell, CDP)
```

详细分层职责见总文档第 6 节。

---

## 3. 技术栈

| 层 | 技术 | 版本 |
|----|------|------|
| 前端 | Tauri v2 + React + TypeScript | - |
| 状态管理 | Zustand | - |
| 任务流可视化 | React Flow | - |
| Runtime | Python + LangGraph | Python 3.11+ |
| MCP Gateway | Rust | - |
| 数据库 | SQLite + sqlite-vec | MVP |
| 浏览器自动化 | Playwright + CDP | - |
| 视觉兜底 | Ollama Vision | 本地模型 |
| 包管理 | pnpm (前端) / pip (Python) / cargo (Rust) | - |

---

## 4. Monorepo 目录结构

```
local-auto/
  apps/
    desktop/            # Tauri + React 前端
    runtime/            # Python Agent Runtime
  crates/
    mcp-gateway/        # Rust MCP 网关
  data/                 # SQLite 数据库、Skill 存储、轨迹数据
    skills/             # skills/{app}/{skill_name}/
    trajectories/       # 执行轨迹记录
    db/                 # SQLite 数据库文件
    backups/            # 数据库备份
  docs/                 # 文档
    0-specs/            # 需求规格
    1-standards/        # 开发规范
    2-milestones/       # 里程碑阶段文档
  scripts/              # 开发/构建/测试脚本
  tests/                # 集成测试与评测基准
    fixtures/           # 测试夹具
    benchmarks/         # 评测脚本
  .github/
    workflows/          # CI/CD
```

---

## 5. 错误码规范

### 5.1 错误码格式

```
E{层级}{模块}{序号}
```

- 层级：1=UI层, 2=Runtime层, 3=MCP层, 4=引擎层, 5=OS适配层
- 模块：两位数字标识
- 序号：两位数字标识

### 5.2 错误码分配

| 错误码 | 含义 | 级别 |
|--------|------|------|
| E1001 | UI 渲染失败 | ERROR |
| E1002 | 用户拒绝授权 | USER_REJECT |
| E1003 | 前端状态同步失败 | ERROR |
| E2001 | Agent 意图解析失败 | ERROR |
| E2002 | Skill 未找到 | NOT_FOUND |
| E2003 | Skill 版本不匹配 | VERSION_MISMATCH |
| E2004 | Workflow 执行超时 | TIMEOUT |
| E2005 | Workflow 验证失败 | VERIFY_FAILED |
| E2006 | Recovery 执行失败 | RECOVERY_FAILED |
| E2007 | Checkpoint 恢复失败 | ERROR |
| E3001 | MCP 服务未启动 | ERROR |
| E3002 | MCP 工具未注册 | NOT_FOUND |
| E3003 | MCP 调用鉴权失败 | PERMISSION_DENIED |
| E3004 | MCP 限流触发 | RATE_LIMITED |
| E4001 | 文件操作被安全策略拦截 | PERMISSION_DENIED |
| E4002 | 文件路径不在白名单 | PERMISSION_DENIED |
| E4003 | 文件操作回滚失败 | ROLLBACK_FAILED |
| E4004 | UIA 元素定位失败 | NOT_FOUND |
| E4005 | UIA 操作超时 | TIMEOUT |
| E4006 | Playwright 页面加载失败 | ERROR |
| E4007 | Vision 模型推理失败 | ERROR |
| E4008 | Vision 响应超时 | TIMEOUT |
| E5001 | 应用启动失败 | ERROR |
| E5002 | 窗口未找到 | NOT_FOUND |
| E5003 | PowerShell 执行失败 | ERROR |
| E5004 | CDP 连接失败 | ERROR |

### 5.3 错误响应格式

```json
{
  "code": "E2005",
  "level": "VERIFY_FAILED",
  "message": "步骤 'click_submit' 验证失败：期望元素 '#result' 存在，实际未找到",
  "task_id": "task_001",
  "step_id": "step_003",
  "skill_id": "skills/chrome/search_doc_v1",
  "timestamp": "2026-05-15T10:30:00Z",
  "context": {
    "expected": {"selector": "#result", "state": "visible"},
    "actual": {"selector": "#result", "state": "not_found"}
  },
  "recovery_suggestion": "尝试执行 recovery 分支: retry_with_scroll"
}
```

---

## 6. 日志规范

### 6.1 日志级别

| 级别 | 用途 | 示例 |
|------|------|------|
| TRACE | 每个执行步骤的输入/输出 | 点击坐标 (120, 340) |
| DEBUG | 内部状态变化 | Skill 路由决策过程 |
| INFO | 关键业务事件 | 任务开始/结束、Skill 创建 |
| WARN | 可恢复的异常 | Vision 超时降级、重试触发 |
| ERROR | 不可恢复的错误 | 引擎崩溃、数据库写入失败 |
| AUDIT | 安全审计事件（独立日志流） | L5 操作被授权、文件被修改 |

### 6.2 日志格式

```json
{
  "timestamp": "2026-05-15T10:30:00.123Z",
  "level": "INFO",
  "logger": "runtime.workflow",
  "task_id": "task_001",
  "step_id": "step_003",
  "skill_id": "skills/chrome/search_doc_v1",
  "event": "step_verify_passed",
  "message": "步骤 'click_submit' 验证通过",
  "duration_ms": 450,
  "context": {}
}
```

### 6.3 日志输出规则

- 控制台输出：DEBUG 及以上
- 文件输出：TRACE 及以上，按天滚动，保留 30 天
- AUDIT 日志：独立文件，永久保留，只追加不修改
- 敏感信息：密码、Token、密钥一律脱敏为 `***`
- 日志文件路径：`data/logs/runtime-{YYYY-MM-DD}.log`、`data/logs/audit-{YYYY-MM-DD}.log`

### 6.4 日志示例

```txt
[2026-05-15T10:30:00.123Z] INFO  [runtime.workflow] [task_001] 任务开始: skill=chrome/search_doc_v1
[2026-05-15T10:30:00.456Z] DEBUG [runtime.workflow] [task_001/step_001] 路由决策: 使用 CDP 路径
[2026-05-15T10:30:01.789Z] AUDIT [security.audit] [task_001/step_002] L4 操作已授权: user_confirm=true
[2026-05-15T10:30:02.100Z] WARN  [engine.vision] [task_001/step_003] Vision 推理超时(30s)，降级为 UIA 兜底
[2026-05-15T10:30:03.500Z] ERROR [runtime.workflow] [task_001/step_005] 验证失败: E2005，触发 recovery
```

---

## 7. 测试策略

### 7.1 测试分层

| 层级 | 类型 | 工具 | 覆盖率要求 | 执行时机 |
|------|------|------|-----------|---------|
| L0 | 单元测试 | pytest / vitest / cargo test | >= 80% | 每次提交 |
| L1 | 集成测试 | pytest + fixtures | 核心路径 100% | 每次提交 |
| L2 | E2E 测试 | Playwright | 三大场景 100% | PR 合并前 |
| L3 | 评测基准 | 自定义评测脚本 | - | 每周评测日 |

### 7.2 测试文件命名

- Python：`test_{module_name}.py`
- TypeScript：`{module_name}.test.ts`
- Rust：模块内 `#[cfg(test)]` 或 `tests/integration_test.rs`

### 7.3 Mock 策略

- 模型调用：使用 Ollama mock server 或录制的响应 fixture
- 浏览器操作：使用 Playwright 录制/回放
- 文件系统：使用 temp 目录 + 夹具
- UIA：使用 mock 元素树 fixture

### 7.4 测试数据管理

- 测试夹具统一放在 `tests/fixtures/`
- 数据库测试使用内存 SQLite
- 测试后自动清理 temp 文件

---

## 8. 数据库规范

### 8.1 SQLite 配置

- 单文件模式，路径 `data/db/local-auto.db`
- WAL 模式开启（提升并发读写性能）
- 每日自动备份到 `data/backups/`

### 8.2 核心表（MVP）

```sql
-- 任务表
CREATE TABLE tasks (
  id TEXT PRIMARY KEY,
  skill_id TEXT,
  status TEXT,          -- pending/running/success/failed/recovered
  started_at TEXT,
  finished_at TEXT,
  duration_ms INTEGER,
  error_code TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 步骤表
CREATE TABLE steps (
  id TEXT PRIMARY KEY,
  task_id TEXT REFERENCES tasks(id),
  step_index INTEGER,
  action TEXT,
  resource TEXT,
  status TEXT,          -- pending/running/success/failed/retried
  duration_ms INTEGER,
  error_code TEXT
);

-- 权限授权记录
CREATE TABLE permissions (
  id TEXT PRIMARY KEY,
  task_id TEXT REFERENCES tasks(id),
  level INTEGER,        -- L0-L7
  resource TEXT,
  action TEXT,
  approved BOOLEAN,
  approved_at TEXT,
  approved_by TEXT      -- user/agent/auto
);

-- 审计日志
CREATE TABLE audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id TEXT,
  step_id TEXT,
  skill_id TEXT,
  actor TEXT,           -- agent/user/tool
  action TEXT,
  resource TEXT,
  before_hash TEXT,
  after_hash TEXT,
  permission_level INTEGER,
  approval_event TEXT,
  result TEXT,
  error_code TEXT,
  duration_ms INTEGER,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Skill 元数据
CREATE TABLE skills (
  id TEXT PRIMARY KEY,
  app TEXT,
  name TEXT,
  version TEXT,
  status TEXT,          -- active/candidate/archived
  success_rate REAL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 执行轨迹
CREATE TABLE trajectories (
  id TEXT PRIMARY KEY,
  task_id TEXT REFERENCES tasks(id),
  skill_id TEXT,
  events TEXT,          -- JSON array of events
  success BOOLEAN,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

---

## 9. 相关文档

| 文档 | 路径 |
|------|------|
| 总文档 | [0-specs/00-project-requirements.md](../0-specs/00-project-requirements.md) |
| 开发规范 | [01-dev-conventions.md](./01-dev-conventions.md) |
| 评测体系手册 | [02-evaluation-handbook.md](./02-evaluation-handbook.md) |
| M0 阶段文档 | [01-m0-engineering-foundation.md](../2-milestones/01-m0-engineering-foundation.md) |
| M1 阶段文档 | [02-m1-app-process-aware.md](../2-milestones/02-m1-app-process-aware.md) |
| M2 阶段文档 | [03-m2-file-permission-audit.md](../2-milestones/03-m2-file-permission-audit.md) |
| M3 阶段文档 | [04-m3-ui-browser-control.md](../2-milestones/04-m3-ui-browser-control.md) |
| M4 阶段文档 | [05-m4-skill-workflow-executor.md](../2-milestones/05-m4-skill-workflow-executor.md) |
| M5 阶段文档 | [06-m5-trajectory-skill-distillation.md](../2-milestones/06-m5-trajectory-skill-distillation.md) |
| M6 阶段文档 | [07-m6-mvp-closure.md](../2-milestones/07-m6-mvp-closure.md) |
