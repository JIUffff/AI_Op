# Personal Local AI Skill OS 项目需求与开发文档（改良版 v2）

版本：v2.0  
日期：2026-05-15  
状态：可执行草案（MVP 可直接开工）

---

## 0. 文档目标

本版文档的目标不是“描述愿景”，而是将项目改造成：

1. 范围收敛、可在 8-12 周内跑通闭环。
2. 评测驱动、可量化验证进展。
3. 安全边界清晰、可审计、可回滚。
4. 对接 2026 年主流 Agent 生态（MCP、Computer Use、A2A 兼容思路）。

---

## 1. 一句话定位

**一个运行在个人电脑上的本地 Agent 执行系统：能理解应用、稳定调用工具、沉淀可复用 Skill，并在失败后自我修复。**

---

## 2. 产品判断（先说结论）

1. 方向正确：`App Understanding + Skill Distillation + Local Runtime` 是核心壁垒。
2. 关键风险不是“能不能点鼠标”，而是“稳定性、权限安全、可恢复、可评测”。
3. 首版必须单平台（建议 Windows）+ 三应用（VSCode/Chrome/文件管理）+ 三任务闭环。
4. 跨平台、全应用、复杂自动学习都放到二期以后。

---

## 3. 目标用户与典型任务

### 3.1 目标用户

1. 本地开发者（主要场景：编码、调试、文档整理）。
2. 高强度知识工作者（主要场景：检索、归档、表格/文档处理）。
3. 注重隐私的高级个人用户（本地优先，不希望上传敏感内容）。

### 3.2 MVP 任务闭环（只做 3 条）

1. `VSCode`：打开项目并运行 `main.py`，验证结果，沉淀 Skill。
2. `Chrome`：检索指定技术文档，提取正文，生成本地 Markdown 笔记。
3. `File Manager`：下载目录按类型归档，生成日志，支持一键回滚。

---

## 4. 范围控制（必须明确）

### 4.1 MVP 包含

1. 本机应用扫描（Windows）。
2. 应用启动/窗口识别/UI Tree 基础读取。
3. 浏览器自动化（Playwright + CDP）。
4. 视觉兜底（Ollama Vision，本地模型）。
5. 文件系统安全读写（目录白名单 + 敏感黑名单）。
6. 权限确认、审计日志、失败恢复、回滚。
7. Skill 创建/检索/执行/版本化更新。
8. 轨迹记录与最小可用蒸馏。

### 4.2 MVP 不包含

1. 全平台同等能力（macOS/Linux 后置）。
2. 全应用通用自动化。
3. 云端多用户协作。
4. 插件市场与生态分发。
5. 完整自治学习（无监督大规模自我优化）。

---

## 5. 核心差异化（相对现有方案）

1. **控制路径优先级固定化**：CLI/API > 文件系统 > Accessibility > DOM/CDP > Vision > 鼠标键盘模拟。
2. **动作后强制验证**：每个步骤有 `expect` 与 `verify`，不允许盲操作链。
3. **失败可恢复**：每个 workflow 必须定义 recovery 分支。
4. **安全默认拒绝**：敏感操作必须二次确认并记审计。
5. **Skill 不是 Prompt**：Skill 是可执行、可验证、可版本化的操作资产。

---

## 6. 架构总览（v2）

```txt
Desktop UI (Tauri + React)
  -> Agent Runtime (Python + LangGraph)
  -> Local MCP Gateway (Rust)
  -> Capability Engines (App/UI/File/Process/Vision/Security/Audit)
  -> OS Adapters (Win UIA, Win32, PowerShell, CDP)
```

### 6.1 分层职责

1. `Desktop UI`：任务输入、权限弹窗、执行可视化、审计查询。
2. `Agent Runtime`：意图解析、Skill 路由、计划执行、验证、恢复、蒸馏。
3. `MCP Gateway`：统一 schema、工具注册、鉴权、限流、幂等与审计钩子。
4. `Capability Engines`：真实执行能力封装（不混入模型推理逻辑）。
5. `OS Adapter`：系统调用适配，隔离平台差异。

### 6.2 兼容策略（面向未来）

1. 保持 MCP 原生接口，便于接入主流 Agent 客户端。
2. 预留 A2A 兼容层（后续多 Agent 协同）。
3. 预留 OpenAI/Anthropic Computer Use 适配器作为可选执行后端。

---

## 7. 技术选型（改良）

### 7.1 前端

1. `Tauri v2 + React + TypeScript`。
2. 状态管理建议 `Zustand`，任务流可视化用 `React Flow`。

### 7.2 Runtime

1. `Python 3.11+`。
2. `LangGraph` 实现可恢复状态机（持久化 checkpoint）。
3. 模型调用抽象成 provider 层：Ollama 本地优先，云模型可选。

### 7.3 本机系统层

1. `Rust` 负责高权限能力与长期守护进程。
2. MCP 子服务拆分维持隔离，避免单点大进程过度膨胀。

### 7.4 数据层

MVP：

1. `SQLite`：任务、权限、审计、Skill 元数据。
2. `sqlite-vec`：轻量向量检索（Skill/文档召回）。

二期：

1. `DuckDB`：轨迹分析与报表。
2. `Qdrant`：大规模向量检索。

---

## 8. 安全与权限模型（强制项）

### 8.1 权限等级

```txt
L0: 系统只读信息
L1: 非敏感文件读取
L2: 启动应用
L3: UI 状态读取
L4: UI 操作
L5: 文件修改
L6: 命令执行
L7: 高风险操作（安装/删除/联网外发/批量修改）
```

### 8.2 策略规则

1. 默认拒绝，按任务临时授权。
2. `L5-L7` 必须用户确认。
3. 命令执行允许名单 + 参数约束。
4. 默认屏蔽敏感目录：Cookie、密码库、私钥、凭据、认证 Token。
5. 所有写操作记录可逆元数据，支持回滚。

### 8.3 审计字段（最小集合）

1. `task_id`、`step_id`、`skill_id`。
2. `actor`（agent/user/tool）。
3. `action`、`resource`、`before_hash`、`after_hash`。
4. `permission_level`、`approval_event`。
5. `result`、`error_code`、`duration_ms`。

---

## 9. Skill 标准（v2）

Skill 必须是“可执行资产”，而不是自由文本说明。

### 9.1 目录结构

```txt
skills/{app}/{skill_name}/
  SKILL.md
  metadata.json
  workflow.yaml
  permissions.yaml
  recovery.yaml
  eval_cases.yaml
  changelog.md
```

### 9.2 workflow 强约束字段

1. `preconditions`：前置条件。
2. `steps`：可执行步骤。
3. `expect`：每步期望状态。
4. `verify`：验证方法。
5. `recovery`：失败恢复树。
6. `rollback`：回滚动作。

### 9.3 Skill 升级机制

1. 新轨迹进入候选池，不直接覆盖主 Skill。
2. 候选版本通过回放评测后再晋升。
3. 每次发布记录成功率变化与风险说明。

---

## 10. 评测体系（必须前置）

### 10.1 评测来源

1. 外部基准：OSWorld、WindowsAgentArena（可映射子任务）。
2. 内部基准：你的 30 条高频真实任务集（必须可复现）。

### 10.2 核心指标

1. Task Success Rate（端到端成功率）。
2. Step Success Rate（步骤成功率）。
3. Recovery Success Rate（恢复成功率）。
4. P50/P95 总耗时。
5. 人工接管率。
6. 危险动作拦截率。
7. 回滚成功率。

### 10.3 MVP 出厂门槛

1. 三大场景端到端成功率 `>= 80%`。
2. 高风险误执行 `= 0`。
3. 恢复成功率 `>= 60%`。
4. 可回滚动作覆盖率 `>= 90%`。

---

## 11. 开发里程碑（12 周版本）

## M0（第 1 周）：工程底座

交付：

1. Monorepo 初始化（apps/crates/python/data/docs）。
2. 本地开发脚本、日志规范、错误码规范。
3. MCP schema 初版。

验收：

1. 一条空任务可贯穿 UI -> Runtime -> MCP -> 日志。

## M1（第 2-3 周）：应用与进程感知

交付：

1. Windows App Scanner。
2. Process & Window Engine。
3. App manifest 与基础 App Profile。

验收：

1. 识别主流应用并可启动。
2. 窗口标题/进程映射准确率达标。

## M2（第 4-5 周）：文件、权限、审计

交付：

1. File System Engine（白名单读写）。
2. Permission Engine。
3. Audit Engine + 回滚元数据。

验收：

1. L5/L6 操作必须触发确认。
2. 所有写操作可追踪。

## M3（第 6-7 周）：UI 感知 + 浏览器控制 + 视觉兜底

交付：

1. UIA 基础读取与元素定位。
2. Playwright + CDP 工具链。
3. Ollama Vision 接口（describe/compare/ocr）。

验收：

1. 三类基础 UI 操作稳定执行。
2. 视觉只作兜底且可验证。

## M4（第 8-9 周）：Skill Registry + Workflow Executor

交付：

1. Skill 存储/检索/版本管理。
2. workflow 执行器与 recovery 执行器。
3. VSCode/Chrome/FileManager 初版 Skill。

验收：

1. 三个 Skill 可执行且有验证步骤。

## M5（第 10-11 周）：轨迹与蒸馏

交付：

1. Trajectory Recorder。
2. 候选 Skill 生成器。
3. 自动回放评测与晋升机制。

验收：

1. 能从成功/失败轨迹生成候选 Skill。

## M6（第 12 周）：MVP 闭环验收

交付：

1. 三大场景完整演示。
2. 评测报告与审计报告。
3. 风险清单与 v3 规划。

验收：

1. 达到“10.3 出厂门槛”。

---

## 12. 高风险点与应对

1. UI 自动化脆弱：元素定位必须组合 `语义 + 层级 + 相对位置 + 验证`。
2. 模型幻觉：动作前后都做状态校验，不通过则拒绝继续。
3. 应用升级破坏 Skill：App Profile 与 Skill 强制版本绑定。
4. 安全事故：高风险动作双确认 + 审计 + 回滚 + 速断开关。
5. 范围失控：坚持“单平台、三应用、三任务”红线。

---

## 13. 项目管理机制

1. 每周固定评测日，输出基线变化。
2. 每次合并必须附带新增/回归用例。
3. 所有重大策略改动必须更新 `risk register`。
4. 所有 Skill 变更必须带版本说明与回放结果。

---

## 14. v3 展望（不进入 MVP）

1. macOS 支持。
2. Linux 支持。
3. 多 Agent 协同（A2A）。
4. 云端协同与设备同步。
5. 插件生态与第三方 Skill 市场。

---

## 15. 改良后的一句话总结

你要做的不是“会点击鼠标的 AI”，而是“**可验证、可恢复、可审计、可持续进化**”的本地 Agent 操作系统。  
先把 Windows 三场景闭环做到高成功率，再扩平台和生态，才是正确的产品节奏。
