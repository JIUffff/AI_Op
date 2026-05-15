# 05 - M4 Skill 注册与工作流执行

对应总文档第 11 节 M4（第 8-9 周）
前置文档：[../1-standards/00-project-overview.md](../1-standards/00-project-overview.md)、[../2-milestones/04-m3-ui-browser-control.md](../2-milestones/04-m3-ui-browser-control.md)

---

## 0. 本阶段目标

实现 Skill 存储/检索/版本管理、Workflow 执行器与 Recovery 执行器、VSCode/Chrome/FileManager 三个初版 Skill。交付物：三个 Skill 可执行且有验证步骤。

---

## 1. 全局规则速查

- Skill 必须是"可执行资产"，不是自由文本 Prompt
- 每个 Skill 必须包含：preconditions、steps、expect、verify、recovery、rollback
- 动作后强制验证：每步有 expect + verify，不允许盲操作链
- 失败可恢复：每个 workflow 必须定义 recovery 分支

---

## 2. 本阶段架构

```
apps/runtime/
  src/
    skill/
      registry.py            # Skill 注册/检索/版本管理
      executor.py            # Workflow 执行器
      recovery.py            # Recovery 执行器
      models.py              # Skill 数据模型
      loader.py              # SKILL.md 解析器
data/
  skills/
    vscode/
      run_file/
        SKILL.md
        metadata.json
        workflow.yaml
        permissions.yaml
        recovery.yaml
        eval_cases.yaml
        changelog.md
    chrome/
      search_doc/
        ...
    file_explorer/
      archive_downloads/
        ...
```

---

## 3. Skill 数据模型

### 3.1 workflow.yaml 强约束格式

```yaml
# data/skills/vscode/run_file/workflow.yaml
skill_id: vscode/run_file
version: "1.0.0"

preconditions:
  - app_installed: vscode
  - file_exists: "{file_path}"

steps:
  - id: open_vscode
    action: app_launch
    args:
      app_id: vscode
      cli_args: ["--goto", "{file_path}"]
    expect:
      window_visible: "Visual Studio Code"
    verify:
      type: uia
      method: verify_element
      args:
        window_title: "Visual Studio Code"
        name: "{file_name}"

  - id: run_file
    action: uia_click
    args:
      window_title: "Visual Studio Code"
      control_type: MenuItem
      name: "Run"
    expect:
      process_started: true
    verify:
      type: process
      method: is_process_running
      args:
        exe_name: "python.exe"
    timeout_seconds: 30

  - id: check_output
    action: file_read
    args:
      path: "{output_path}"
    expect:
      file_content_not_empty: true
    verify:
      type: assertion
      method: assert_not_empty
      args:
        value: "{result.content}"

recovery:
  open_vscode:
    - if: "window_not_found"
      then:
        - action: app_launch
          args: { app_id: vscode }
          retry_original: true
    - if: "cli_failed"
      then:
        - action: uia_click
          args: { window_title: "Visual Studio Code", name: "File" }
        - action: file_open_dialog
          args: { path: "{file_path}" }

rollback:
  - action: kill_process
    args: { exe_name: "python.exe" }
    condition: "if process still running"
```

### 3.2 permissions.yaml

```yaml
# data/skills/vscode/run_file/permissions.yaml
required_levels:
  - level: 2  # L2: 启动应用
    action: app_launch
    resource: vscode
  - level: 4  # L4: UI 操作
    action: uia_click
    resource: "Visual Studio Code"
  - level: 6  # L6: 命令执行
    action: cmd_exec
    resource: "python {file_path}"
  - level: 1  # L1: 读取输出文件
    action: file_read
    resource: "{output_path}"

auto_approve:
  - level: 1
  - level: 2

require_user_confirm:
  - level: 4
  - level: 6
```

### 3.3 metadata.json

```json
{
  "skill_id": "vscode/run_file",
  "app": "vscode",
  "name": "run_file",
  "version": "1.0.0",
  "description": "在 VSCode 中打开文件并运行，验证输出结果",
  "author": "system",
  "created_at": "2026-05-15T00:00:00Z",
  "tags": ["vscode", "run", "python"],
  "success_rate": 0.0,
  "execution_count": 0,
  "status": "active"
}
```

### 3.4 eval_cases.yaml

```yaml
# data/skills/vscode/run_file/eval_cases.yaml
cases:
  - id: eval_001
    description: "运行简单的 print 脚本"
    input:
      file_path: "C:\\workspace\\test\\main.py"
      output_path: "C:\\workspace\\test\\output.txt"
    expected:
      status: success
      output_contains: "Hello"
  
  - id: eval_002
    description: "运行有语法错误的脚本"
    input:
      file_path: "C:\\workspace\\test\\broken.py"
    expected:
      status: failed
      error_contains: "SyntaxError"
```

### 3.5 recovery.yaml

```yaml
# data/skills/vscode/run_file/recovery.yaml
strategies:
  app_not_installed:
    description: "应用未安装"
    actions:
      - action: notify_user
        message: "VSCode 未安装，请先安装"
      - action: abort

  file_not_found:
    description: "文件不存在"
    actions:
      - action: notify_user
        message: "文件 {file_path} 不存在"
      - action: abort

  ui_element_not_found:
    description: "UI 元素定位失败"
    max_retries: 3
    actions:
      - action: screenshot
      - action: vision_describe
        args: { prompt: "描述当前 VSCode 窗口的状态" }
      - action: retry_with_different_locator
```

### 3.6 changelog.md

```markdown
# Changelog - vscode/run_file

## v1.0.0 (2026-05-15)
- 初始版本
- 支持通过 CLI 打开文件
- 支持通过 UIA 点击 Run 菜单
- 支持读取输出文件验证
- Recovery 策略: 窗口未找到、CLI 失败
```

---

## 4. Skill Registry

```python
# apps/runtime/src/skill/registry.py

import json
import yaml
from pathlib import Path
from typing import Optional
from .models import SkillManifest, SkillStatus
from .loader import SkillLoader

class SkillRegistry:
    """Skill 注册/检索/版本管理。"""
    
    def __init__(self, skills_dir: Path = None):
        self.skills_dir = skills_dir or Path("data/skills")
        self.loader = SkillLoader(self.skills_dir)
        self._cache: dict[str, SkillManifest] = {}
        self._load_all()
    
    def _load_all(self):
        """加载所有 Skill。"""
        for app_dir in self.skills_dir.iterdir():
            if not app_dir.is_dir():
                continue
            for skill_dir in app_dir.iterdir():
                if not skill_dir.is_dir():
                    continue
                manifest = self.loader.load(skill_dir)
                if manifest:
                    key = f"{manifest.app}/{manifest.name}"
                    self._cache[key] = manifest
    
    def get_skill(self, skill_id: str, version: str = None) -> Optional[SkillManifest]:
        """获取 Skill。"""
        manifest = self._cache.get(skill_id)
        if not manifest:
            return None
        
        if version and manifest.version != version:
            # 查找历史版本
            return self._get_version(skill_id, version)
        
        return manifest
    
    def _get_version(self, skill_id: str, version: str) -> Optional[SkillManifest]:
        """获取指定版本的 Skill。"""
        # TODO: 实现版本历史存储
        return None
    
    def list_skills(self, app: str = None, status: SkillStatus = None) -> list[SkillManifest]:
        """列出 Skill。"""
        results = list(self._cache.values())
        if app:
            results = [s for s in results if s.app == app]
        if status:
            results = [s for s in results if s.status == status]
        return results
    
    def update_success_rate(self, skill_id: str, success_rate: float):
        """更新成功率。"""
        if skill_id in self._cache:
            self._cache[skill_id].success_rate = success_rate
            self._save_metadata(self._cache[skill_id])
    
    def _save_metadata(self, manifest: SkillManifest):
        """保存元数据。"""
        meta_path = self.skills_dir / manifest.app / manifest.name / "metadata.json"
        with open(meta_path, "w") as f:
            json.dump(manifest.to_dict(), f, indent=2, ensure_ascii=False)
```

### 4.1 SkillLoader

```python
# apps/runtime/src/skill/loader.py

import json
import yaml
from pathlib import Path
from typing import Optional
from .models import SkillManifest, Workflow

class SkillLoader:
    """Skill 文件加载器。"""
    
    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
    
    def load(self, skill_dir: Path) -> Optional[SkillManifest]:
        """从目录加载 Skill。"""
        meta_path = skill_dir / "metadata.json"
        workflow_path = skill_dir / "workflow.yaml"
        permissions_path = skill_dir / "permissions.yaml"
        recovery_path = skill_dir / "recovery.yaml"
        eval_path = skill_dir / "eval_cases.yaml"
        
        if not meta_path.exists():
            return None
        
        with open(meta_path, "r") as f:
            meta = json.load(f)
        
        workflow = None
        if workflow_path.exists():
            with open(workflow_path, "r", encoding="utf-8") as f:
                workflow = yaml.safe_load(f)
        
        permissions = None
        if permissions_path.exists():
            with open(permissions_path, "r", encoding="utf-8") as f:
                permissions = yaml.safe_load(f)
        
        recovery = None
        if recovery_path.exists():
            with open(recovery_path, "r", encoding="utf-8") as f:
                recovery = yaml.safe_load(f)
        
        eval_cases = None
        if eval_path.exists():
            with open(eval_path, "r", encoding="utf-8") as f:
                eval_cases = yaml.safe_load(f)
        
        return SkillManifest(
            app=meta["app"],
            name=meta["name"],
            version=meta["version"],
            description=meta.get("description", ""),
            status=meta.get("status", "active"),
            success_rate=meta.get("success_rate", 0.0),
            execution_count=meta.get("execution_count", 0),
            workflow=workflow,
            permissions=permissions,
            recovery=recovery,
            eval_cases=eval_cases,
            directory=skill_dir,
        )
```

### 4.2 Models

```python
# apps/runtime/src/skill/models.py

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

class SkillStatus:
    ACTIVE = "active"
    CANDIDATE = "candidate"
    ARCHIVED = "archived"

@dataclass
class SkillManifest:
    """Skill 完整描述。"""
    app: str
    name: str
    version: str
    description: str = ""
    status: str = SkillStatus.ACTIVE
    success_rate: float = 0.0
    execution_count: int = 0
    workflow: Optional[dict] = None
    permissions: Optional[dict] = None
    recovery: Optional[dict] = None
    eval_cases: Optional[dict] = None
    directory: Optional[Path] = None
    
    @property
    def skill_id(self) -> str:
        return f"{self.app}/{self.name}"
    
    def to_dict(self) -> dict:
        return {
            "skill_id": self.skill_id,
            "app": self.app,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "status": self.status,
            "success_rate": self.success_rate,
            "execution_count": self.execution_count,
        }
```

---

## 5. Workflow Executor

```python
# apps/runtime/src/skill/executor.py

import logging
import time
from typing import Optional
from .models import SkillManifest
from ..engines.permission_engine import PermissionEngine
from ..engines.audit_engine import AuditEngine

logger = logging.getLogger("runtime.workflow_executor")

class WorkflowExecutor:
    """Workflow 执行器。"""
    
    def __init__(self, permission_engine: PermissionEngine = None, audit_engine: AuditEngine = None):
        self.permission = permission_engine or PermissionEngine()
        self.audit = audit_engine or AuditEngine()
        self._action_handlers = {}  # action_name -> handler function
    
    def register_handler(self, action_name: str, handler):
        """注册动作处理器。"""
        self._action_handlers[action_name] = handler
    
    async def execute(self, skill: SkillManifest, context: dict, task_id: str: str) -> dict:
        """执行 Skill 工作流。
        
        Args:
            skill: Skill 描述
            context: 运行时上下文（用户输入的参数）
            task_id: 任务 ID
            step_id: 步骤 ID
        
        Returns:
            执行结果
        """
        workflow = skill.workflow
        if not workflow:
            return {"success": False, "error": {"code": "E2001", "message": "Skill 无工作流定义"}}
        
        # 检查前置条件
        preconditions = workflow.get("preconditions", [])
        for cond in preconditions:
            if not self._check_precondition(cond, context):
                return {"success": False, "error": {"code": "E2001", "message": f"前置条件不满足: {cond}"}}
        
        steps = workflow.get("steps", [])
        results = []
        
        for i, step in enumerate(steps):
            step_id = f"{task_id}/step_{i+1}"
            logger.info(f"执行步骤 {i+1}/{len(steps)}: {step['id']}")
            
            # 检查权限
            perm_level = self._get_step_permission_level(step)
            granted, reason = await self.permission.check_permission(
                task_id, perm_level, step.get("action", ""), step.get("args", {})
            )
            if not granted:
                return {"success": False, "error": {"code": "E3003", "message": reason}}
            
            # 执行动作
            step_result = await self._execute_step(step, context, task_id, step_id)
            results.append(step_result)
            
            if not step_result["success"]:
                # 触发 recovery
                recovery_result = await self._try_recovery(step, skill.recovery, context, task_id, step_id)
                if not recovery_result["success"]:
                    return {"success": False, "error": step_result.get("error"), "recovery_attempted": True}
            
            # 验证结果
            verify_result = await self._verify_step(step, context, task_id, step_id)
            if not verify_result["success"]:
                logger.warning(f"步骤 {step['id']} 验证失败")
                return {"success": False, "error": {"code": "E2005", "message": f"验证失败: {step['id']}"}}
        
        return {
            "success": True,
            "results": results,
            "steps_executed": len(steps),
        }
    
    async def _execute_step(self, step: dict, context: dict, task_id: str, step_id: str) -> dict:
        """执行单一步骤。"""
        action_name = step.get("action")
        handler = self._action_handlers.get(action_name)
        
        if not handler:
            return {"success": False, "error": {"code": "E2001", "message": f"未知动作: {action_name}"}}
        
        # 解析参数中的变量
        args = self._resolve_args(step.get("args", {}), context)
        
        start_time = time.time()
        try:
            result = await handler(**args, task_id=task_id, step_id=step_id)
            duration_ms = int((time.time() - start_time) * 1000)
            
            self.audit.log_action(
                task_id=task_id, step_id=step_id,
                actor="agent", action=action_name,
                resource=str(args.get("path", args.get("window_title", ""))),
                permission_level=self._get_step_permission_level(step),
                result="success" if result.get("success") else "failed",
                duration_ms=duration_ms,
            )
            
            return result
        except Exception as e:
            return {"success": False, "error": {"code": "E2001", "message": str(e)}}
    
    async def _verify_step(self, step: dict, context: dict, task_id: str, step_id: str) -> dict:
        """验证步骤结果。"""
        verify = step.get("verify")
        if not verify:
            return {"success": True}  # 无验证要求，直接通过
        
        verify_type = verify.get("type")
        method = verify.get("method")
        
        # 根据 verify_type 调用对应的验证方法
        if verify_type == "uia":
            from ..engines.uia_engine import UIAEngine
            engine = UIAEngine()
            return engine.verify_element(**self._resolve_args(verify.get("args", {}), context))
        elif verify_type == "process":
            from ..engines.process_engine import ProcessEngine
            engine = ProcessEngine()
            handler = getattr(engine, method, None)
            if handler:
                result = handler(**self._resolve_args(verify.get("args", {}), context))
                return {"success": result}
        elif verify_type == "assertion":
            value = self._resolve_args(verify.get("args", {}), context).get("value", "")
            if method == "assert_not_empty":
                return {"success": bool(value)}
        
        return {"success": True}  # 默认通过
    
    async def _try_recovery(self, step: dict, recovery_config: dict, context: dict, task_id: str, step_id: str) -> dict:
        """尝试恢复。"""
        if not recovery_config:
            return {"success": False}
        
        strategies = recovery_config.get("strategies", {})
        step_recovery = recovery_config.get(step.get("id"), [])
        
        for recovery_action in step_recovery:
            if_condition = recovery_action.get("if")
            then_actions = recovery_action.get("then", [])
            
            logger.info(f"尝试恢复策略: {if_condition}")
            
            for action in then_actions:
                handler = self._action_handlers.get(action.get("action"))
                if handler:
                    try:
                        await handler(**self._resolve_args(action.get("args", {}), context))
                    except Exception:
                        continue
            
            if recovery_action.get("retry_original"):
                return await self._execute_step(step, context, task_id, step_id)
        
        return {"success": False}
    
    def _check_precondition(self, cond: dict, context: dict) -> bool:
        """检查前置条件。"""
        if "app_installed" in cond:
            from ..engines.app_scanner import AppScanner
            scanner = AppScanner()
            return scanner.get_app(cond["app_installed"]) is not None
        if "file_exists" in cond:
            from pathlib import Path
            path = self._resolve_arg(cond["file_exists"], context)
            return Path(path).exists()
        return True
    
    def _get_step_permission_level(self, step: dict) -> int:
        """获取步骤的权限级别。"""
        action_perms = {
            "app_launch": 2,
            "uia_click": 4,
            "uia_type": 4,
            "file_read": 1,
            "file_write": 5,
            "cmd_exec": 6,
            "browser_navigate": 3,
            "browser_click": 4,
        }
        return action_perms.get(step.get("action", ""), 7)
    
    def _resolve_args(self, args: dict, context: dict) -> dict:
        """解析参数中的 {variable}。"""
        resolved = {}
        for key, value in args.items():
            if isinstance(value, str) and "{" in value:
                resolved[key] = value.format(**context)
            else:
                resolved[key] = value
        return resolved
    
    def _resolve_arg(self, arg, context: dict):
        """解析单个参数。"""
        if isinstance(arg, str) and "{" in arg:
            return arg.format(**context)
        return arg
```

---

## 6. 三个初版 Skill

### 6.1 VSCode: run_file

已在第 3 节定义。

### 6.2 Chrome: search_doc

```yaml
# data/skills/chrome/search_doc/workflow.yaml
skill_id: chrome/search_doc
version: "1.0.0"

preconditions:
  - app_installed: chrome

steps:
  - id: open_chrome
    action: app_launch
    args:
      app_id: chrome
    expect:
      window_visible: "Google Chrome"
    verify:
      type: process
      method: is_process_running
      args: { exe_name: "chrome.exe" }

  - id: navigate_to_search
    action: browser_navigate
    args:
      url: "https://www.google.com"
    expect:
      page_loaded: true
    verify:
      type: assertion
      method: assert_not_empty
      args: { value: "{result.url}" }

  - id: search_keyword
    action: browser_fill
    args:
      selector: "textarea[name='q']"
      text: "{keyword}"
    expect:
      input_filled: true
    verify:
      type: assertion
      method: assert_not_empty
      args: { value: "{text}" }

  - id: submit_search
    action: browser_click
    args:
      selector: "input[type='submit']"
    expect:
      page_changed: true
    verify:
      type: browser
      method: wait_for_selector
      args: { selector: "#search", timeout_ms: 10000 }

  - id: click_first_result
    action: browser_click
    args:
      selector: "#search a"
    expect:
      page_navigated: true
    verify:
      type: assertion
      method: assert_not_empty
      args: { value: "{result.url}" }

  - id: extract_content
    action: browser_extract
    args:
      selector: "article, main, .content"
    expect:
      content_length_gt_100: true
    verify:
      type: assertion
      method: assert_not_empty
      args: { value: "{result.content}" }

  - id: save_note
    action: file_write
    args:
      path: "{notes_dir}/{timestamp}_doc.md"
      content: "# {keyword}\n\n{result.content}"
    expect:
      file_created: true
    verify:
      type: assertion
      method: assert_not_empty
      args: { value: "{result.content}" }

recovery:
  navigate_to_search:
    - if: "page_load_timeout"
      then:
        - action: browser_navigate
          args: { url: "https://www.bing.com" }
          retry_original: false

rollback:
  - action: file_delete
    args: { path: "{notes_dir}/{timestamp}_doc.md" }
    condition: "if file was created"
```

### 6.3 File Explorer: archive_downloads

```yaml
# data/skills/file_explorer/archive_downloads/workflow.yaml
skill_id: file_explorer/archive_downloads
version: "1.0.0"

preconditions:
  - directory_exists: "{downloads_dir}"

steps:
  - id: list_downloads
    action: file_list
    args:
      path: "{downloads_dir}"
    expect:
      files_listed: true
    verify:
      type: assertion
      method: assert_not_empty
      args: { value: "{result.files}" }

  - id: create_archive_dirs
    action: file_mkdir
    args:
      paths:
        - "{downloads_dir}/images"
        - "{downloads_dir}/documents"
        - "{downloads_dir}/archives"
        - "{downloads_dir}/other"
    expect:
      directories_created: true
    verify:
      type: assertion
      method: assert_not_empty
      args: { value: "ok" }

  - id: classify_and_move
    action: file_classify_move
    args:
      source_dir: "{downloads_dir}"
      rules:
        - extensions: [".png", ".jpg", ".jpeg", ".gif", ".webp"]
          target: "{downloads_dir}/images"
        - extensions: [".pdf", ".doc", ".docx", ".txt", ".md"]
          target: "{downloads_dir}/documents"
        - extensions: [".zip", ".rar", ".7z", ".tar", ".gz"]
          target: "{downloads_dir}/archives"
    expect:
      files_moved: true
    verify:
      type: assertion
      method: assert_not_empty
      args: { value: "{result.moved_count}" }

  - id: generate_log
    action: file_write
    args:
      path: "{downloads_dir}/archive_log_{timestamp}.md"
      content: "{log_content}"
    expect:
      log_created: true
    verify:
      type: assertion
      method: assert_not_empty
      args: { value: "{result.content}" }

rollback:
  - action: file_restore_from_backup
    condition: "if any files were moved"
```

---

## 7. 实现步骤

| 序号 | 任务 | 预计耗时 | 依赖 |
|------|------|---------|------|
| 1 | 实现 SkillLoader + SkillManifest | 2h | 无 |
| 2 | 实现 SkillRegistry | 2h | 1 |
| 3 | 实现 WorkflowExecutor | 4h | M0-M3 所有引擎 |
| 4 | 实现 RecoveryExecutor | 2h | 3 |
| 5 | 编写 VSCode run_file Skill | 1h | 1-4 |
| 6 | 编写 Chrome search_doc Skill | 1h | 1-4 |
| 7 | 编写 File Explorer archive_downloads Skill | 1h | 1-4 |
| 8 | 注册所有动作处理器到 Executor | 2h | M0-M3 |
| 9 | 三个 Skill 端到端集成测试 | 3h | 5-8 |

---

## 8. 测试与验收标准

- [ ] `SkillRegistry.get_skill("vscode/run_file")` 返回完整 Skill 描述
- [ ] `SkillRegistry.list_skills(app="vscode")` 返回 VSCode 相关 Skill
- [ ] `WorkflowExecutor.execute()` 可执行三步骤 workflow
- [ ] 每步执行后 verify 调用成功
- [ ] Recovery 在步骤失败时触发
- [ ] 审计日志记录每个步骤的执行结果
- [ ] 三个 Skill 均可执行且有验证步骤

---

## 9. 交付物清单

| 交付物 | 路径 | 状态 |
|--------|------|------|
| SkillLoader | apps/runtime/src/skill/loader.py | - |
| SkillManifest/Models | apps/runtime/src/skill/models.py | - |
| SkillRegistry | apps/runtime/src/skill/registry.py | - |
| WorkflowExecutor | apps/runtime/src/skill/executor.py | - |
| VSCode run_file Skill | data/skills/vscode/run_file/ | - |
| Chrome search_doc Skill | data/skills/chrome/search_doc/ | - |
| File Explorer archive_downloads Skill | data/skills/file_explorer/archive_downloads/ | - |
| 集成测试 | tests/test_workflow_e2e.py | - |

---

## 10. 风险与注意事项

| 风险 | 级别 | 应对 |
|------|------|------|
| workflow.yaml 格式可能随迭代变更 | MEDIUM | 定义 JSON Schema 校验，版本不兼容时拒绝加载 |
| Recovery 策略覆盖不全 | HIGH | M4 只覆盖已知失败场景，M5 通过轨迹补充 |
| Executor 参数解析错误（{variable} 模板） | MEDIUM | 模板解析前检查所有变量是否在 context 中存在 |
| 三引擎依赖耦合 | MEDIUM | Executor 通过 handler 注册模式解耦，不直接 import 引擎 |

---

## 11. 相关文档

- [../1-standards/00-project-overview.md](../1-standards/00-project-overview.md) - 全局规范
- [../2-milestones/04-m3-ui-browser-control.md](../2-milestones/04-m3-ui-browser-control.md) - 前置阶段
- [../2-milestones/06-m5-trajectory-skill-distillation.md](../2-milestones/06-m5-trajectory-skill-distillation.md) - 下一阶段
