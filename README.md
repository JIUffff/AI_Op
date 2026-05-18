# Superpower — 本地 AI 自动化平台

通过网页界面触发 Skill，AI 自动执行桌面操作。

## 架构

```
┌─────────────────┐     FastAPI      ┌──────────────────┐
│   React 前端     │ ◄──────────────► │  Python Runtime  │
│   (端口 5173)    │                 │   (端口 8000)     │
└─────────────────┘                 └────────┬─────────┘
                                            │
                          ┌─────────────────┼─────────────────┐
                          ▼                 ▼                 ▼
                    ┌──────────┐    ┌──────────────┐   ┌──────────┐
                    │ 引擎层    │    │ Skill 工作流  │   │ 轨迹系统  │
                    │ VSCode   │    │ Executor     │   │ Recorder │
                    │ Chrome   │    │ Registry     │   │ Distiller│
                    │ File     │    │ Recovery     │   │ Promotion│
                    └──────────┘    └──────────────┘   └──────────┘
```

## 快速开始

### 后端

```bash
cd apps/runtime
pip install -e .
uvicorn src.api:api --host 127.0.0.1 --port 8000 --reload
```

### 前端

```bash
cd apps/web
npm install
npm run dev
```

### 测试

```bash
cd apps/runtime
python -m pytest tests/ -v
```

## 里程碑

| 里程碑 | 状态 | 说明 |
|--------|------|------|
| M0 | ✅ | 工程基础：Monorepo、FastAPI、React |
| M1 | ✅ | 应用进程感知：AppScanner、ProcessEngine |
| M2 | ✅ | 文件权限审计：权限分级、审计日志 |
| M3 | ✅ | UI 浏览器控制：前端中文界面 |
| M4 | ✅ | Skill 工作流执行器：YAML 定义、恢复/回滚 |
| M5 | ✅ | 轨迹记录与蒸馏：SQLite+JSON 双存储 |
| M6 | ✅ | 真实引擎：VSCode UIA、Chrome CDP、文件系统 |

## 目录结构

```
├── apps/
│   ├── runtime/          # Python 后端
│   │   ├── src/
│   │   │   ├── api.py          # FastAPI 入口
│   │   │   ├── engines/        # 真实引擎层
│   │   │   ├── skills/         # Skill 系统
│   │   │   ├── trajectory/     # 轨迹系统
│   │   │   └── ...
│   │   ├── data/               # Skill YAML、数据库
│   │   └── tests/              # 单元测试
│   └── web/              # React 前端
│       └── src/
├── docs/                 # 开发规范、里程碑文档
└── .gstack/             # gstack 配置
```

## 技术栈

- **后端**: Python 3.12+, FastAPI, LangGraph, SQLite
- **前端**: React 19, TypeScript, Vite, Zustand
- **引擎**: pywinauto (UIA), websocket-client (CDP)
- **测试**: pytest
