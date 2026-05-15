# 07 - M6 MVP 闭环验收

对应总文档第 11 节 M6（第 12 周）
前置文档：所有 M0-M5 阶段文档、[../1-standards/02-evaluation-handbook.md](../1-standards/02-evaluation-handbook.md)

---

## 0. 本阶段目标

完成三大场景完整演示、生成评测报告与审计报告、整理风险清单与 v3 规划。交付物：达到"10.3 出厂门槛"的 MVP 系统。

---

## 1. 全局规则速查

### 1.1 出厂门槛（总文档 10.3）

| 指标 | 门槛 | 验证方式 |
|------|------|---------|
| 三大场景端到端成功率 | >= 80% | 评测脚本，每场景执行 10 次 |
| 高风险误执行 | = 0 | 审计日志检查 |
| 恢复成功率 | >= 60% | 注入故障后统计 recovery 成功率 |
| 可回滚动作覆盖率 | >= 90% | 审计日志中 writable_actions vs rollbackable_actions |

### 1.2 三大场景

1. **VSCode**: 打开项目并运行 `main.py`，验证结果，沉淀 Skill
2. **Chrome**: 检索指定技术文档，提取正文，生成本地 Markdown 笔记
3. **File Manager**: 下载目录按类型归档，生成日志，支持一键回滚

---

## 2. 验收流程

### 2.1 第一阶段：全量评测（第 1-2 天）

运行完整评测套件：

```bash
# 1. 安装依赖
cd apps/runtime && pip install -e ".[dev]"
cd apps/desktop && pnpm install
cd crates/mcp-gateway && cargo build

# 2. 启动服务
./scripts/dev.sh

# 3. 运行评测
python tests/benchmarks/run_benchmark.py --suite internal --iterations 10

# 4. 查看报告
cat tests/benchmarks/results/$(date +%Y-%m-%d)/report.md
```

输出报告应包含：
- 7 项核心指标
- 每个场景的详细执行结果
- 与历史基线的对比
- 回归项标注

### 2.2 第二阶段：故障注入测试（第 3-4 天）

注入以下故障，验证 recovery 和 rollback：

| 故障 | 注入方式 | 期望行为 |
|------|---------|---------|
| VSCode 未启动 | 关闭 VSCode 后执行 run_file Skill | 自动启动 VSCode 并继续 |
| Chrome 页面加载超时 | 断网 10s 后恢复 | 尝试备用搜索引擎 |
| 文件被占用 | 用记事本打开目标文件后执行写入 | 重试 3 次后返回错误，不覆盖 |
| UIA 元素定位失败 | 修改 VSCode 主题使菜单名称变化 | 触发 Vision 兜底或 recovery |
| 磁盘空间不足 | 创建大文件占满磁盘 | 返回错误，不产生脏数据 |
| 敏感路径访问 | 尝试读取 .ssh/id_rsa | 立即拦截，返回 E4001 |

### 2.3 第三阶段：安全审计（第 5 天）

1. 检查审计日志完整性：
   ```sql
   -- 所有写操作都应有审计记录
   SELECT COUNT(*) FROM audit_log WHERE action IN ('write', 'delete', 'move');
   -- 应与 file_engine 的操作次数一致
   ```

2. 检查权限执行：
   ```sql
   -- 检查是否有 L5-L7 操作未经用户确认
   SELECT * FROM audit_log WHERE permission_level >= 5 AND approval_event IS NULL;
   ```

3. 检查敏感路径拦截：
   ```sql
   -- 检查是否有敏感路径被放行
   SELECT * FROM audit_log WHERE resource LIKE '%.ssh%' OR resource LIKE '%.git-credentials%';
   ```

4. 检查回滚能力：
   - 随机选取 5 个写操作，执行 rollback
   - 验证文件恢复成功

### 2.4 第四阶段：演示准备（第 6-7 天）

制作演示脚本：

```
演示 1: VSCode run_file
  用户输入: "打开 main.py 并运行"
  预期: 打开 VSCode -> 打开文件 -> 运行 -> 显示输出 -> 沉淀 Skill

演示 2: Chrome search_doc
  用户输入: "搜索 Python async/await 教程，生成笔记"
  预期: 打开 Chrome -> 搜索 -> 提取内容 -> 保存 Markdown -> 验证内容

演示 3: File Manager archive_downloads
  用户输入: "整理下载目录"
  预期: 扫描下载目录 -> 创建分类文件夹 -> 移动文件 -> 生成日志 -> 验证
```

---

## 3. 评测报告模板

```markdown
# MVP 验收评测报告

日期: 2026-XX-XX
版本: 0.1.0

## 1. 核心指标

| 指标 | 结果 | 门槛 | 状态 |
|------|------|------|------|
| 端到端成功率 | {value}% | >= 80% | {PASS/FAIL} |
| 高风险误执行 | {value} | = 0 | {PASS/FAIL} |
| 恢复成功率 | {value}% | >= 60% | {PASS/FAIL} |
| 可回滚覆盖率 | {value}% | >= 90% | {PASS/FAIL} |

## 2. 场景详情

### VSCode run_file
- 执行次数: 10
- 成功: {count}
- 失败: {count}
- P50 耗时: {value}s
- P95 耗时: {value}s
- 失败原因: ...

### Chrome search_doc
- 执行次数: 10
- 成功: {count}
- ...

### File Manager archive_downloads
- 执行次数: 10
- 成功: {count}
- ...

## 3. 故障注入结果

| 故障 | Recovery 触发 | Recovery 成功 | Rollback 可用 |
|------|-------------|-------------|-------------|
| VSCode 未启动 | 是 | 是 | N/A |
| Chrome 超时 | 是 | 是 | N/A |
| 文件被占用 | 是 | {是/否} | 是 |
| ... | ... | ... | ... |

## 4. 安全审计

- 审计日志完整性: {通过/未通过}
- 权限执行合规: {通过/未通过}
- 敏感路径拦截: {通过/未通过}
- 回滚能力: {通过/未通过}

## 5. 风险清单

| 风险 | 级别 | 状态 | 负责人 | 预计解决时间 |
|------|------|------|--------|-------------|
| UI 自动化在高分屏不稳定 | HIGH | 跟踪中 | - | v3 |
| ... | ... | ... | ... | ... |

## 6. 结论

MVP 出厂门槛状态: **{通过 / 未通过}**

{通过的理由或未通过的改进建议}
```

---

## 4. 风险清单模板

```markdown
# MVP 风险清单

## 已知风险

### R001: UI 自动化在高分屏上不稳定
- 级别: HIGH
- 影响: VSCode/Chrome 的 UIA 元素定位在 4K 屏上可能偏移
- 应对: 优先使用 CLI/CDP 路径，UIA 仅作为备选
- 状态: 跟踪中，v3 解决

### R002: sqlite-vec 向量检索稳定性
- 级别: MEDIUM
- 影响: Skill 检索可能返回不相关结果
- 应对: MVP 阶段用文件名匹配回退
- 状态: 跟踪中，二期切 Qdrant

### R003: Ollama Vision 推理速度
- 级别: MEDIUM
- 影响: 兜底方案延迟可能 > 30s
- 应对: 设置超时降级策略
- 状态: 已实现超时处理

### R004: Chrome 多 profile CDP 冲突
- 级别: LOW
- 影响: 多 profile 同时使用可能连接失败
- 应对: MVP 只支持默认 profile
- 状态: 已记录

## 已关闭风险

### R005: ~Rust MCP Gateway 部署复杂度~
- 级别: ~~HIGH~~
- 关闭原因: MVP 用 HTTP 模式，stdior 延迟到二期
- 关闭日期: 2026-XX-XX
```

---

## 5. v3 规划建议

### 5.1 优先级排序

| 优先级 | 特性 | 理由 |
|--------|------|------|
| P0 | macOS 支持 | 用户群体覆盖 |
| P0 | 错误处理与边界条件加固 | 提升稳定性 |
| P1 | Linux 支持 | 开发者需求 |
| P1 | Skill 市场（内部） | 团队内分享 |
| P2 | A2A 多 Agent 协同 | 复杂任务场景 |
| P2 | 云端设备同步 | 多设备用户 |
| P3 | 插件生态 | 第三方扩展 |

### 5.2 技术债清单

| 项目 | 当前方案 | 目标方案 | 工作量 |
|------|---------|---------|--------|
| MCP 传输 | HTTP | stdio + SSE | 1 周 |
| 蒸馏算法 | 取第一条轨迹 | 序列对齐 + 泛化 | 2 周 |
| 权限通信 | Polling | WebSocket | 3 天 |
| 向量检索 | sqlite-vec | Qdrant | 1 周 |
| 数据库备份 | 手动脚本 | 自动定时备份 | 2 天 |
| 日志滚动 | 按天手动 | loguru 自动滚动 | 1 天 |

---

## 6. 实现步骤

| 序号 | 任务 | 预计耗时 | 依赖 |
|------|------|---------|------|
| 1 | 全量评测脚本执行 | 1d | 评测体系手册 |
| 2 | 故障注入测试 | 2d | M4-M5 所有功能 |
| 3 | 安全审计 | 1d | M2 审计引擎 |
| 4 | 回滚能力验证 | 1d | M2 FileEngine |
| 5 | 评测报告生成 | 0.5d | 1-4 |
| 6 | 风险清单整理 | 0.5d | 全部 |
| 7 | 演示脚本编写 | 1d | 全部 |
| 8 | v3 规划文档 | 1d | 全部 |
| 9 | 演示演练 | 1d | 7 |

---

## 7. 验收标准

### 7.1 硬性标准（必须全部通过）

- [ ] 端到端成功率 >= 80%（每场景 10 次，至少 8 次成功）
- [ ] 高风险误执行 = 0（审计日志验证）
- [ ] 恢复成功率 >= 60%（故障注入测试）
- [ ] 可回滚动作覆盖率 >= 90%（审计日志验证）
- [ ] 三大场景均可端到端演示
- [ ] 评测报告已生成并归档
- [ ] 审计报告已生成
- [ ] 风险清单已整理

### 7.2 软性标准（建议达到）

- [ ] P50 总耗时 < 60s
- [ ] P95 总耗时 < 180s
- [ ] 人工接管率 < 10%
- [ ] 至少有 1 个 Skill 通过蒸馏 + 回放晋升
- [ ] 前端 UI 可完整展示任务流

---

## 8. 交付物清单

| 交付物 | 路径 | 状态 |
|--------|------|------|
| 评测报告 | tests/benchmarks/results/{date}/report.md | - |
| 审计报告 | data/audit-reports/{date}/ | - |
| 风险清单 | docs/risk-register.md | - |
| v3 规划 | docs/v3-roadmap.md | - |
| 演示脚本 | scripts/demo/ | - |
| CHANGELOG | CHANGELOG.md | - |
| MVP 发布标签 | git tag v0.1.0 | - |

---

## 9. 演示 Checklist

### VSCode 场景

- [ ] 用户输入 "打开 main.py 并运行"
- [ ] 系统识别意图，路由到 vscode/run_file
- [ ] 弹出 L6 权限确认（命令执行）
- [ ] 用户确认后执行
- [ ] VSCode 打开并运行文件
- [ ] 输出验证通过
- [ ] 审计日志完整

### Chrome 场景

- [ ] 用户输入 "搜索 Python 异步编程教程，生成笔记"
- [ ] 系统路由到 chrome/search_doc
- [ ] Chrome 打开并导航到搜索引擎
- [ ] 搜索结果提取成功
- [ ] Markdown 笔记生成到 Documents
- [ ] 内容长度验证通过
- [ ] 审计日志完整

### File Manager 场景

- [ ] 用户输入 "整理下载目录"
- [ ] 系统路由到 file_explorer/archive_downloads
- [ ] 弹出 L5 权限确认（文件移动）
- [ ] 下载目录被分类归档
- [ ] 归档日志生成
- [ ] 回滚测试通过
- [ ] 审计日志完整

---

## 10. 相关文档

- [../1-standards/00-project-overview.md](../1-standards/00-project-overview.md) - 全局规范
- [../0-specs/00-project-requirements.md](../0-specs/00-project-requirements.md) - 总文档
- [../1-standards/02-evaluation-handbook.md](../1-standards/02-evaluation-handbook.md) - 评测流程
- [../1-standards/01-dev-conventions.md](../1-standards/01-dev-conventions.md) - 代码/提交规范
