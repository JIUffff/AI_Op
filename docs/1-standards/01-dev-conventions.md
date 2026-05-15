# 开发规范

版本：v1.0
日期：2026-05-15
适用范围：全项目所有开发者

---

## 1. 代码风格

### 1.1 Python

- 遵循 PEP 8，使用 `ruff` 进行 lint 和格式化
- 类型注解：所有函数签名必须标注类型
- 文档字符串：Google 风格
- 行长度：88（与 Black/Ruff 默认一致）
- 引号：双引号

```python
# 示例
def parse_skill_manifest(path: str) -> SkillManifest:
    """解析 Skill 描述文件。
    
    Args:
        path: SKILL.md 文件路径。
    
    Returns:
        SkillManifest 对象。
    
    Raises:
        FileNotFoundError: 文件不存在时抛出。
        ValueError: 格式不合法时抛出。
    """
    ...
```

### 1.2 TypeScript

- 使用 ESLint + Prettier 格式化
- 严格模式：`strict: true` in tsconfig
- 组件命名：PascalCase
- 文件命名：kebab-case
- 接口命名：PascalCase，前缀 `I` 不使用

```typescript
// 示例
interface TaskState {
  id: string;
  skillId: string;
  status: TaskStatus;
  steps: StepState[];
}

function TaskCard({ task }: { task: TaskState }) {
  // ...
}
```

### 1.3 Rust

- 使用 `cargo fmt` 格式化
- 使用 `clippy` 检查 lint
- 遵循 Rust API Guidelines
- 错误处理：使用 `thiserror` / `anyhow`

---

## 2. Git 分支策略

### 2.1 分支模型

```
main               # 主分支，始终可部署
  ├── feature/*    # 功能分支
  ├── fix/*        # 修复分支
  └── milestone/*  # 里程碑集成分支（如 milestone/m3）
```

- `main` 分支禁止直接 push，必须通过 PR 合并
- 功能分支命名：`feature/{模块}-{简述}`，如 `feature/mcp-gateway-init`
- 修复分支命名：`fix/{问题简述}`，如 `fix/skill-version-mismatch`

### 2.2 Commit Message 规范

采用 Conventional Commits：

```
<type>(<scope>): <subject>

<body>

<footer>
```

Type 取值：
- `feat`: 新功能
- `fix`: 修复 bug
- `refactor`: 重构（非功能性改动）
- `docs`: 文档
- `test`: 测试相关
- `chore`: 构建/工具链
- `perf`: 性能优化

示例：
```
feat(mcp): 注册首批 file_read 工具

添加 file_read MCP 工具，支持白名单路径校验和审计日志记录。

Closes #12
```

### 2.3 PR 规范

每个 PR 必须包含：
- 清晰的标题和描述
- 关联的 Issue/Milestone
- 变更类型标记（feat/fix/refactor/docs/test）
- 自测结果说明
- 截图（UI 变更）

---

## 3. CI/CD 流程

### 3.1 GitHub Actions Workflow

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - name: Python Lint
        run: |
          pip install ruff
          ruff check apps/runtime/
          ruff format --check apps/runtime/
      - name: TypeScript Lint
        working-directory: apps/desktop
        run: |
          npm ci
          npm run lint
      - name: Rust Lint
        working-directory: crates/mcp-gateway
        run: |
          cargo fmt --check
          cargo clippy -- -D warnings

  test:
    runs-on: windows-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4
      - name: Python Tests
        working-directory: apps/runtime
        run: |
          pip install -e ".[dev]"
          pytest -v --cov=src --cov-report=xml
      - name: TypeScript Tests
        working-directory: apps/desktop
        run: npm test
      - name: Rust Tests
        working-directory: crates/mcp-gateway
        run: cargo test

  e2e:
    runs-on: windows-latest
    needs: test
    if: github.event_name == 'pull_request'
    steps:
      - uses: actions/checkout@v4
      - name: Setup & Run E2E
        run: |
          # 安装依赖、启动服务、运行 E2E
          ./scripts/run-e2e.sh
```

### 3.2 CI 检查清单

每个 PR 合并前必须通过：
- [ ] Lint 全部通过（Python/TS/Rust）
- [ ] 单元测试通过率 >= 80%
- [ ] 集成测试通过
- [ ] 无新增的高危依赖漏洞
- [ ] 如果是 UI 变更，附带截图

---

## 4. 项目配置

### 4.1 Python 项目

```toml
# apps/runtime/pyproject.toml
[project]
name = "local-auto-runtime"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "langgraph>=0.2.0",
    "langchain>=0.3.0",
    "httpx>=0.27.0",
    "pydantic>=2.0",
    "sqlite-vec>=0.1.0",
    "pywin32>=306",
    "uiautomation>=2.0.18",
    "playwright>=1.44.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "pytest-asyncio>=0.23",
    "ruff>=0.4.0",
]
```

### 4.2 TypeScript 项目

```json
{
  "compilerOptions": {
    "strict": true,
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    }
  }
}
```

### 4.3 Rust 项目

```toml
# crates/mcp-gateway/Cargo.toml
[package]
name = "mcp-gateway"
version = "0.1.0"
edition = "2021"

[dependencies]
axum = "0.7"
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
tokio = { version = "1.38", features = ["full"] }
thiserror = "1.0"
tracing = "0.1"
tracing-subscriber = "0.3"
```

---

## 5. 环境变量管理

### 5.1 配置文件

- 使用 `.env.example` 记录所有需要的环境变量
- `.env` 加入 `.gitignore`，禁止提交
- 本地开发使用 `.env.local`

### 5.2 必要环境变量

```bash
# .env.example

# 模型配置
MODEL_PROVIDER=ollama
MODEL_NAME=qwen2.5:7b
MODEL_BASE_URL=http://localhost:11434/v1

# 数据库
DB_PATH=data/db/local-auto.db

# MCP Gateway
MCP_HOST=127.0.0.1
MCP_PORT=8900

# Ollama Vision
VISION_MODEL_NAME=qwen2.5vl:7b

# 日志
LOG_LEVEL=DEBUG
LOG_DIR=data/logs
```

---

## 6. 安全编码规范

### 6.1 敏感数据处理

- 禁止在日志中记录密码、Token、私钥
- 使用 `secrets` 模块生成安全随机数
- 配置文件中的密钥使用加密存储或系统 Keychain

### 6.2 命令执行安全

- 禁止直接拼接 shell 命令
- 使用参数化方式调用子进程
- 命令执行前必须通过允许名单校验

```python
# 禁止
os.system(f"taskkill /F /IM {user_input}")

# 正确
ALLOWED_COMMANDS = {"tasklist", "start", "taskkill"}
if command not in ALLOWED_COMMANDS:
    raise PermissionError(f"命令 {command} 不在允许名单")
subprocess.run([command, *validated_args], check=True)
```

### 6.3 路径安全

- 所有文件路径必须 resolve 后校验是否在白名单内
- 禁止直接使用用户输入作为文件路径

```python
from pathlib import Path

ALLOWED_DIRS = [Path(r"C:\Users\Public"), Path(r"D:\workspace")]

def validate_path(user_path: str) -> Path:
    resolved = Path(user_path).resolve()
    if not any(resolved.is_relative_to(d) for d in ALLOWED_DIRS):
        raise PermissionError(f"路径 {resolved} 不在白名单")
    return resolved
```

---

## 7. 发布流程

### 7.1 版本号规范

语义化版本：`MAJOR.MINOR.PATCH`

- MVP 阶段：`0.x.y`
- `MINOR`：新功能、里程碑完成
- `PATCH`：bug 修复、文档更新

### 7.2 发布 Checklist

- [ ] 所有测试通过
- [ ] 评测报告达标（见 [02-evaluation-handbook.md](./02-evaluation-handbook.md)）
- [ ] CHANGELOG 更新
- [ ] 版本号更新
- [ ] 数据库 migration 脚本（如有）
- [ ] 已知问题记录到 risk register
