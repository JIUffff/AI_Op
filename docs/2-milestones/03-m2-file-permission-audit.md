# 03 - M2 文件系统与权限审计

对应总文档第 11 节 M2（第 4-5 周）
前置文档：[../1-standards/00-project-overview.md](../1-standards/00-project-overview.md)、[../2-milestones/02-m1-app-process-aware.md](../2-milestones/02-m1-app-process-aware.md)

---

## 0. 本阶段目标

实现 File System Engine（白名单读写）、Permission Engine（L0-L7 授权）、Audit Engine（审计日志 + 回滚元数据）。交付物：所有文件写操作可追踪、可回滚、L5+ 操作触发确认。

---

## 1. 全局规则速查

- 默认拒绝，按任务临时授权
- L5-L7 操作必须用户确认
- 敏感目录默认屏蔽：Cookie、密码库、私钥、凭据、认证 Token
- 所有写操作记录可逆元数据，支持回滚
- 控制路径优先级：文件系统 > Accessibility > DOM/CDP > Vision > 鼠标键盘

---

## 2. 本阶段架构

```
apps/runtime/
  src/
    engines/
      file_engine.py         # 文件系统引擎（白名单读写 + 回滚）
      permission_engine.py   # 权限引擎（L0-L7 授权）
      audit_engine.py        # 审计引擎（日志 + 回滚记录）
      security_policy.py     # 安全策略（黑名单 + 白名单）
    mcp_tools/
      file_read.py           # MCP 工具: 读取文件
      file_write.py          # MCP 工具: 写入文件
      file_list.py           # MCP 工具: 列出目录
      file_move.py           # MCP 工具: 移动/重命名
```

---

## 3. 安全策略

### 3.1 目录白名单

```python
# apps/runtime/src/engines/security_policy.py

from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger("runtime.security_policy")

# MVP 白名单（可根据用户配置扩展）
DEFAULT_WHITELIST = [
    Path.home() / "Desktop",
    Path.home() / "Documents",
    Path.home() / "Downloads",
    Path.home() / "workspace",
    Path(r"C:\workspace"),
    Path(r"D:\workspace"),
]

# 敏感目录黑名单（绝对禁止）
SENSITIVE_PATHS = [
    # 浏览器 Cookie / 密码
    Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data" / "Default" / "Login Data",
    Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data" / "Default" / "Cookies",
    # SSH / Git 凭据
    Path.home() / ".ssh",
    Path.home() / ".git-credentials",
    # Windows 凭据
    Path.home() / "AppData" / "Local" / "Microsoft" / "Credentials",
]

# 敏感文件后缀
SENSITIVE_EXTENSIONS = {".key", ".pem", ".pfx", ".p12", ".keystore", ".crt", ".csr"}

class SecurityPolicy:
    """安全策略：白名单 + 黑名单 + 权限映射。"""
    
    def __init__(self, whitelist: list[Path] = None):
        self.whitelist = whitelist or DEFAULT_WHITELIST.copy()
    
    def validate_path(self, path: str | Path, action: str = "read") -> tuple[bool, Optional[str]]:
        """验证路径是否允许操作。
        
        Returns:
            (allowed, reason) - 如果 allowed=False，reason 说明原因
        """
        resolved = Path(path).resolve()
        
        # 1. 检查黑名单
        for sensitive in SENSITIVE_PATHS:
            try:
                if resolved.is_relative_to(sensitive):
                    return False, f"路径 {resolved} 在敏感目录中，已拦截"
            except ValueError:
                pass
        
        # 2. 检查敏感扩展名
        if resolved.suffix.lower() in SENSITIVE_EXTENSIONS:
            return False, f"文件类型 {resolved.suffix} 被安全策略拦截"
        
        # 3. 检查白名单
        for wl_dir in self.whitelist:
            try:
                if resolved.is_relative_to(wl_dir):
                    return True, None
            except ValueError:
                pass
        
        return False, f"路径 {resolved} 不在白名单内"
    
    def add_whitelist(self, path: Path):
        """添加白名单目录。"""
        resolved = path.resolve()
        if resolved not in self.whitelist:
            self.whitelist.append(resolved)
            logger.info(f"添加白名单: {resolved}")
    
    def get_permission_level(self, action: str) -> int:
        """根据操作类型返回权限级别。"""
        level_map = {
            "read": 1,        # L1: 非敏感文件读取
            "list": 1,        # L1: 目录列表
            "write": 5,       # L5: 文件修改
            "create": 5,      # L5: 创建文件
            "move": 5,        # L5: 移动文件
            "delete": 7,      # L7: 删除文件（高风险）
            "execute": 6,     # L6: 命令执行
        }
        return level_map.get(action, 7)
```

---

## 4. File System Engine

### 4.1 核心功能

| 功能 | 权限级别 | 说明 |
|------|---------|------|
| 读取文件 | L1 | 白名单内读取 |
| 写入文件 | L5 | 白名单内写入，记录回滚元数据 |
| 创建文件 | L5 | 白名单内创建，记录回滚元数据 |
| 移动/重命名 | L5 | 白名单内移动，记录回滚元数据 |
| 删除文件 | L7 | 移动到回收站或备份目录，记录回滚元数据 |
| 列出目录 | L1 | 白名单内列出 |

### 4.2 实现骨架

```python
# apps/runtime/src/engines/file_engine.py

import hashlib
import shutil
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime
from .security_policy import SecurityPolicy
from .audit_engine import AuditEngine

logger = logging.getLogger("runtime.file_engine")

BACKUP_DIR = Path("data/backups/files")
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

class FileEngine:
    """文件系统引擎：白名单读写 + 回滚支持。"""
    
    def __init__(self, security: SecurityPolicy = None, audit: AuditEngine = None):
        self.security = security or SecurityPolicy()
        self.audit = audit or AuditEngine()
    
    def read_file(self, path: str, task_id: str = "", step_id: str = "") -> dict:
        """读取文件。权限 L1。"""
        allowed, reason = self.security.validate_path(path, "read")
        if not allowed:
            return {"success": False, "error": {"code": "E4001", "message": reason}}
        
        try:
            file_path = Path(path).resolve()
            content = file_path.read_text(encoding="utf-8")
            file_hash = self._compute_hash(file_path)
            
            self.audit.log_action(
                task_id=task_id, step_id=step_id,
                actor="agent", action="read", resource=str(file_path),
                after_hash=file_hash, permission_level=1,
                result="success",
            )
            
            return {
                "success": True,
                "result": {
                    "content": content,
                    "size_bytes": file_path.stat().st_size,
                    "hash": file_hash,
                    "modified_at": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
                }
            }
        except Exception as e:
            return {"success": False, "error": {"code": "E4001", "message": str(e)}}
    
    def write_file(self, path: str, content: str, task_id: str = "", step_id: str = "") -> dict:
        """写入文件。权限 L5，需审计 + 回滚。"""
        file_path = Path(path).resolve()
        allowed, reason = self.security.validate_path(path, "write")
        if not allowed:
            return {"success": False, "error": {"code": "E4002", "message": reason}}
        
        # 备份原文件（用于回滚）
        before_hash = None
        if file_path.exists():
            before_hash = self._compute_hash(file_path)
            self._backup_file(file_path)
        
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            after_hash = self._compute_hash(file_path)
            
            self.audit.log_action(
                task_id=task_id, step_id=step_id,
                actor="agent", action="write", resource=str(file_path),
                before_hash=before_hash, after_hash=after_hash,
                permission_level=5, result="success",
            )
            
            return {
                "success": True,
                "result": {
                    "size_bytes": file_path.stat().st_size,
                    "hash": after_hash,
                    "rollback_available": before_hash is not None,
                }
            }
        except Exception as e:
            return {"success": False, "error": {"code": "E4001", "message": str(e)}}
    
    def delete_file(self, path: str, task_id: str = "", step_id: str = "") -> dict:
        """删除文件。权限 L7，强制备份。"""
        file_path = Path(path).resolve()
        allowed, reason = self.security.validate_path(path, "delete")
        if not allowed:
            return {"success": False, "error": {"code": "E4001", "message": reason}}
        
        if not file_path.exists():
            return {"success": False, "error": {"code": "E4002", "message": "文件不存在"}}
        
        before_hash = self._compute_hash(file_path)
        backup_path = self._backup_file(file_path)
        
        try:
            file_path.unlink()
            
            self.audit.log_action(
                task_id=task_id, step_id=step_id,
                actor="agent", action="delete", resource=str(file_path),
                before_hash=before_hash, after_hash=None,
                permission_level=7, result="success",
            )
            
            return {
                "success": True,
                "result": {
                    "backup_path": str(backup_path),
                    "rollback_available": True,
                }
            }
        except Exception as e:
            return {"success": False, "error": {"code": "E4003", "message": str(e)}}
    
    def rollback(self, resource_path: str, task_id: str = "") -> dict:
        """回滚文件到上一次操作前的状态。"""
        file_path = Path(resource_path).resolve()
        backup = self.audit.find_last_backup(str(file_path))
        
        if not backup:
            return {"success": False, "error": {"code": "E4003", "message": "无可用备份"}}
        
        try:
            if file_path.exists():
                self._backup_file(file_path)  # 当前状态也备份
            
            shutil.copy2(backup["backup_path"], file_path)
            
            self.audit.log_action(
                task_id=task_id, step_id="",
                actor="agent", action="rollback", resource=str(file_path),
                before_hash=self._compute_hash(backup["backup_path"]),
                after_hash=self._compute_hash(file_path),
                permission_level=5, result="success",
            )
            
            return {"success": True, "result": {"message": "回滚成功"}}
        except Exception as e:
            return {"success": False, "error": {"code": "E4003", "message": str(e)}}
    
    def _compute_hash(self, file_path: Path) -> str:
        """计算文件 SHA256。"""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def _backup_file(self, file_path: Path) -> Path:
        """备份文件到 data/backups/files/。"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "_".join(file_path.parts[1:])  # 去掉盘符的冒号
        backup_path = BACKUP_DIR / f"{timestamp}_{safe_name}"
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, backup_path)
        return backup_path
```

---

## 5. Permission Engine

### 5.1 授权流程

```
Agent 需要执行 L5+ 操作
  -> Permission Engine 检查是否已有授权
    -> 有授权: 放行
    -> 无授权: 向前端发送授权请求
      -> 用户确认 -> 记录授权 -> 放行
      -> 用户拒绝 -> 返回 PERMISSION_DENIED
```

### 5.2 实现骨架

```python
# apps/runtime/src/engines/permission_engine.py

import logging
import asyncio
from typing import Optional
from datetime import datetime
from .audit_engine import AuditEngine

logger = logging.getLogger("runtime.permission_engine")

# 需要用户确认的权限级别
CONFIRM_LEVELS = {5, 6, 7}

class PermissionEngine:
    """权限引擎：临时授权 + 用户确认。"""
    
    def __init__(self, audit: AuditEngine = None):
        self.audit = audit or AuditEngine()
        self._active_grants: dict[str, dict] = {}  # task_id -> {level, resource, expires}
        self._request_queue: asyncio.Queue = asyncio.Queue()
    
    async def check_permission(self, task_id: str, level: int, resource: str, action: str) -> tuple[bool, Optional[str]]:
        """检查权限。
        
        Returns:
            (granted, reason)
        """
        # L0-L4 默认允许
        if level < 5:
            return True, None
        
        # 检查已有授权
        grant = self._active_grants.get(task_id)
        if grant and grant["level"] >= level and grant["resource"] == resource:
            if datetime.now() < grant["expires"]:
                return True, None
            else:
                del self._active_grants[task_id]
        
        # L5-L7 需要用户确认
        if level in CONFIRM_LEVELS:
            granted = await self._request_user_confirm(task_id, level, resource, action)
            if granted:
                self._active_grants[task_id] = {
                    "level": level,
                    "resource": resource,
                    "expires": datetime.now().replace(hour=23, minute=59, second=59),
                }
                return True, None
            else:
                return False, "用户拒绝授权"
        
        return False, "权限不足"
    
    async def _request_user_confirm(self, task_id: str, level: int, resource: str, action: str) -> bool:
        """请求用户确认。
        
        实现方式：
        1. 向前端 WebSocket/EventSource 发送授权请求
        2. 等待用户响应（超时 60s）
        3. 记录授权事件
        """
        logger.info(f"请求授权: task={task_id}, level=L{level}, action={action}, resource={resource}")
        
        # TODO: 实际实现需要异步通信机制
        # MVP 阶段可用 polling 或简单返回 True（自动确认）
        await self._request_queue.put({
            "task_id": task_id,
            "level": level,
            "resource": resource,
            "action": action,
        })
        
        # MVP: 超时默认拒绝
        try:
            response = await asyncio.wait_for(
                self._wait_for_user_response(task_id),
                timeout=60.0,
            )
            return response.get("approved", False)
        except asyncio.TimeoutError:
            logger.warning(f"授权请求超时: task={task_id}")
            return False
    
    async def _wait_for_user_response(self, task_id: str) -> dict:
        """等待用户响应（由前端 API 调用填充）。"""
        # 实际实现通过 WebSocket 或 EventSource
        ...
    
    async def approve(self, task_id: str, approved: bool):
        """前端调用：批准/拒绝授权。"""
        # 填充到 _wait_for_user_response 的等待队列
        ...
    
    def revoke(self, task_id: str):
        """撤销任务授权。"""
        self._active_grants.pop(task_id, None)
```

---

## 6. Audit Engine

### 6.1 实现骨架

```python
# apps/runtime/src/engines/audit_engine.py

import sqlite3
import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

logger = logging.getLogger("runtime.audit_engine")

class AuditEngine:
    """审计引擎：记录所有操作的审计日志。"""
    
    def __init__(self, db_path: str = "data/db/local-auto.db"):
        self.db_path = db_path
        self._ensure_table()
    
    def _ensure_table(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT,
                step_id TEXT,
                skill_id TEXT,
                actor TEXT,
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
            )
        """)
        conn.commit()
        conn.close()
    
    def log_action(
        self,
        task_id: str,
        step_id: str,
        actor: str,
        action: str,
        resource: str,
        before_hash: str = None,
        after_hash: str = None,
        permission_level: int = 0,
        approval_event: str = None,
        result: str = "",
        error_code: str = None,
        duration_ms: int = 0,
    ):
        """记录审计事件。"""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """INSERT INTO audit_log 
               (task_id, step_id, actor, action, resource, before_hash, after_hash,
                permission_level, approval_event, result, error_code, duration_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (task_id, step_id, actor, action, resource, before_hash, after_hash,
             permission_level, approval_event, result, error_code, duration_ms),
        )
        conn.commit()
        conn.close()
        
        # 同时写入 AUDIT 日志文件
        audit_logger = logging.getLogger("security.audit")
        audit_logger.info(
            f"[{task_id}] {actor} {action} {resource} "
            f"L{permission_level} result={result}"
        )
    
    def find_last_backup(self, resource_path: str) -> Optional[dict]:
        """查找资源的最后一次备份记录。"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            """SELECT before_hash, created_at FROM audit_log
               WHERE resource = ? AND before_hash IS NOT NULL
               ORDER BY created_at DESC LIMIT 1""",
            (resource_path,),
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {"hash": row[0], "created_at": row[1]}
        return None
    
    def get_task_audit(self, task_id: str) -> list[dict]:
        """获取任务的所有审计记录。"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM audit_log WHERE task_id = ? ORDER BY created_at",
            (task_id,),
        )
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows
```

---

## 7. MCP 工具

### 7.1 file_read

```python
# apps/runtime/src/mcp_tools/file_read.py
from ..engines.file_engine import FileEngine
from ..engines.security_policy import SecurityPolicy

def handle_file_read(path: str, task_id: str = "", step_id: str = "") -> dict:
    """MCP 工具: 读取文件。权限 L1。"""
    engine = FileEngine()
    return engine.read_file(path, task_id, step_id)
```

### 7.2 file_write

```python
# apps/runtime/src/mcp_tools/file_write.py
from ..engines.file_engine import FileEngine
from ..engines.permission_engine import PermissionEngine

async def handle_file_write(path: str, content: str, task_id: str = "", step_id: str = "") -> dict:
    """MCP 工具: 写入文件。权限 L5。"""
    perm_engine = PermissionEngine()
    granted, reason = await perm_engine.check_permission(task_id, 5, path, "write")
    if not granted:
        return {"success": False, "error": {"code": "E4001", "message": reason}}
    
    engine = FileEngine()
    return engine.write_file(path, content, task_id, step_id)
```

---

## 8. 实现步骤

| 序号 | 任务 | 预计耗时 | 依赖 |
|------|------|---------|------|
| 1 | 实现 SecurityPolicy | 2h | 无 |
| 2 | 实现 FileEngine | 4h | 1 |
| 3 | 实现 PermissionEngine | 3h | 无 |
| 4 | 实现 AuditEngine | 2h | 无 |
| 5 | 编写 MCP 工具: file_read/file_write | 2h | 2,3 |
| 6 | 单元测试（SecurityPolicy + FileEngine） | 2h | 1,2 |
| 7 | 集成测试（写操作可追踪 + 可回滚） | 2h | 2,4 |
| 8 | 前端权限确认弹窗 UI | 2h | 3 |

---

## 9. 测试与验收标准

- [ ] L0-L4 操作不需要用户确认即可执行
- [ ] L5 操作（写入文件）触发前端权限确认弹窗
- [ ] 用户拒绝后操作返回 PERMISSION_DENIED
- [ ] 文件写入后 audit_log 表有对应记录
- [ ] 文件写入前有 before_hash
- [ ] `file_engine.rollback()` 可恢复被修改的文件
- [ ] 删除文件后自动备份，回滚可恢复
- [ ] 敏感目录路径被拦截，返回 E4001
- [ ] 白名单外的路径被拦截，返回 E4002

---

## 10. 交付物清单

| 交付物 | 路径 | 状态 |
|--------|------|------|
| SecurityPolicy | apps/runtime/src/engines/security_policy.py | - |
| FileEngine | apps/runtime/src/engines/file_engine.py | - |
| PermissionEngine | apps/runtime/src/engines/permission_engine.py | - |
| AuditEngine | apps/runtime/src/engines/audit_engine.py | - |
| MCP 工具: file_read | apps/runtime/src/mcp_tools/file_read.py | - |
| MCP 工具: file_write | apps/runtime/src/mcp_tools/file_write.py | - |
| 权限确认弹窗 UI | apps/desktop/src/components/PermissionDialog.tsx | - |
| 单元测试 | apps/runtime/tests/test_file_*.py | - |

---

## 11. 风险与注意事项

| 风险 | 级别 | 应对 |
|------|------|------|
| 大文件读写超时 | MEDIUM | 设置 30s 超时，超过返回 TIMEOUT |
| 文件被其他进程锁定 | MEDIUM | 捕获 PermissionError，重试 3 次后返回错误 |
| 备份目录膨胀 | LOW | 定期清理 30 天前的备份 |
| 权限引擎异步通信未实现 | MEDIUM | MVP 用 polling 方案，M3 切 WebSocket |

---

## 12. 相关文档

- [../1-standards/00-project-overview.md](../1-standards/00-project-overview.md) - 全局规范
- [../2-milestones/02-m1-app-process-aware.md](../2-milestones/02-m1-app-process-aware.md) - 前置阶段
- [../2-milestones/04-m3-ui-browser-control.md](../2-milestones/04-m3-ui-browser-control.md) - 下一阶段
