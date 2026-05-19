# MVP 风险清单

## 已知风险

### R001: Chrome CDP 端口冲突
- 级别: LOW
- 影响: 多个 Chrome 实例可能争夺同一个调试端口 (9222)
- 应对: 已实现 --user-data-dir 隔离，每个实例使用独立临时目录
- 状态: 已关闭（修复于 2026-05-18）

### R002: VSCode UIA 元素定位在高分屏上不稳定
- 级别: MEDIUM
- 影响: 4K 或缩放 >100% 时 UIA 元素坐标可能偏移
- 应对: 优先使用 CLI (code.cmd) 路径，UIA 仅作为备选
- 状态: 跟踪中，v3 解决

### R003: Chrome 启动失败后无重试机制
- 级别: LOW
- 影响: 如果 Chrome 首次启动失败（如被安全软件拦截），无自动重试
- 应对: 可增加 launch() 重试逻辑（最多 2 次）
- 状态: 跟踪中

### R004: File 引擎无并发安全
- 级别: LOW
- 影响: 多 Skill 同时操作文件系统可能产生竞态条件
- 应对: MVP 单线程执行，v2 添加文件锁
- 状态: 跟踪中

### R005: WebSocket 连接无心跳保活
- 级别: LOW
- 影响: Chrome CDP WebSocket 可能因超时断开，导致后续命令失败
- 应对: 可添加定期 ping 或断线重连
- 状态: 跟踪中

### R006: 无前端自动化测试
- 级别: MEDIUM
- 影响: 前端重构或新增功能可能引入 UI 回归
- 应对: v2 添加 Vitest + React Testing Library
- 状态: 计划中

### R007: 无 CI/CD 管道
- 级别: HIGH
- 影响: 代码变更无自动化验证，可能引入回归
- 应对: 添加 GitHub Actions 工作流
- 状态: 计划中

## 已关闭风险

### R008: ~Chrome WebSocket 403 Forbidden~
- 级别: ~~P0~~
- 关闭原因: 添加 --remote-allow-origins=* 启动参数
- 关闭日期: 2026-05-18

### R009: ~Chrome CDP 连接到浏览器级而非页面级~
- 级别: ~~P1~~
- 关闭原因: 修改 _get_debug_url() 优先获取 page-level WebSocket URL
- 关闭日期: 2026-05-18

### R010: ~extract_content 返回空文本~
- 级别: ~~P1~~
- 关闭原因: 修复 JS IIFE 语法（箭头函数未调用），改用 ES5 function()
- 关闭日期: 2026-05-18
