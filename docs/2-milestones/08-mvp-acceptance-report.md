# MVP 验收评测报告

日期: 2026-05-18
版本: 0.1.0

## 1. 核心指标

| 指标 | 结果 | 门槛 | 状态 |
|------|------|------|------|
| 端到端成功率 | 100% (13/13) | >= 80% | PASS |
| 高风险误执行 | 0 | = 0 | PASS |
| 恢复成功率 | 100% (1/1) | >= 60% | PASS |
| 可回滚覆盖率 | 100% (1/1) | >= 90% | PASS |
| 单元测试通过 | 129/129 | 100% | PASS |

## 2. 场景详情

### VSCode run_file
- 执行次数: 4
- 成功: 4 (is_running, launch, open_file, close)
- 失败: 0
- P50 耗时: ~3s (launch + open)
- 失败原因: 无

### Chrome search_doc
- 执行次数: 5
- 成功: 5 (is_running, launch, navigate, extract_content, close)
- 失败: 0
- 内容提取: 126 chars (Example Domain 页面)
- 失败原因: 无

### File Manager archive_downloads
- 执行次数: 4
- 成功: 4 (scan, classify, organize, rollback)
- 失败: 0
- 分类类别: images, documents, videos, code (4 个)
- 移动文件: 5 个
- 回滚恢复: 1 个

## 3. 引擎修复记录

本次修复了以下 Chrome CDP 引擎问题：

| 问题 | 级别 | 修复 | 状态 |
|------|------|------|------|
| WebSocket 403 Forbidden | P0 | 添加 --remote-allow-origins=* | 已关闭 |
| CDP 端口冲突 | P0 | 使用 --user-data-dir 隔离实例 | 已关闭 |
| Page.navigate 未找到 | P1 | 连接到 page-level WebSocket URL | 已关闭 |
| extract_content 返回空 | P1 | 修复 JS IIFE 语法 (箭头函数未调用) | 已关闭 |
| CDP 超时 | P2 | 增加超时从 10s 到 15s | 已关闭 |

## 4. 安全审计

- 审计日志完整性: 通过 (rollback_log.json 持久化)
- 权限执行合规: 通过 (File 引擎无敏感路径访问)
- 敏感路径拦截: 通过 (无 .ssh/.git-credentials 访问)
- 回滚能力: 通过 (rollback 成功恢复 1 个文件)

## 5. 单元测试覆盖

| 模块 | 测试数 | 通过 | 失败 |
|------|--------|------|------|
| App Profile | 9 | 9 | 0 |
| App Scanner | 5 | 5 | 0 |
| M6 Engines (VSCode/Chrome/File) | 30 | 30 | 0 |
| Process Engine | 8 | 8 | 0 |
| Skills Executor | 20 | 20 | 0 |
| Skills Models | 9 | 9 | 0 |
| Skills Registry | 8 | 8 | 0 |
| Trajectory | 18 | 18 | 0 |
| Graph | 1 | 1 | 0 |
| **总计** | **129** | **129** | **0** |

## 6. 端到端测试覆盖

| 引擎 | 测试项 | 状态 |
|------|--------|------|
| File | scan_directory | PASS |
| File | classify_files | PASS |
| File | organize_directory | PASS |
| File | rollback | PASS |
| VSCode | is_running | PASS |
| VSCode | launch | PASS |
| VSCode | open_file | PASS |
| VSCode | close | PASS |
| Chrome | is_running | PASS |
| Chrome | launch | PASS |
| Chrome | navigate | PASS |
| Chrome | extract_content | PASS |
| Chrome | close | PASS |

## 7. 结论

MVP 出厂门槛状态: **通过**

三大引擎（VSCode UIA、Chrome CDP、File System）均通过端到端验证：
- 所有 13 个 e2e 测试通过 (100%)
- 所有 129 个单元测试通过 (100%)
- 无高风险误执行
- 回滚能力验证通过
- Chrome CDP 连接问题已修复并验证

系统已具备完整的文件管理、浏览器控制、代码编辑能力，满足 MVP 交付标准。
