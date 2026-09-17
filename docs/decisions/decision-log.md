# 自主决策记录

## DEC-20260917-001

|字段|内容|
|---|---|
|Decision ID|DEC-20260917-001|
|Date|2026-09-17|
|WBS|Repository Governance|
|Decision|启用“默认自主执行 + Gate 确认 + 异常升级”；自动执行批次和 WBS 边界检查周额度，剩余低于 20% 时保存检查点并停止新任务；允许在正确分支内自主同步 GitHub。|
|Reason|落实用户最新明确规则，减少普通确认和聊天消耗，同时保留重大变更、资源和远端安全边界。|
|Impact|后续 L1 任务自动执行，L2 记录后继续，L3/Gate 才请求确认；新增 `STATUS.md`、最小 Session 入口和额度保护。|
|Rollback|回退本决策对应提交，并恢复原有逐任务启动方式；不影响业务数据或正式技术基线。|

## DEC-20260917-002

|字段|内容|
|---|---|
|Decision ID|DEC-20260917-002|
|Date|2026-09-17|
|WBS|P03-A02|
|Decision|来源资格审计只接受文件标题中明确的“合同”或“技术协议”作为确定性分类证据；历史解决方案不自动映射为标准能力或调研。|
|Reason|保持来源语义真实，避免为满足覆盖率把 AI 推断或目录名称写成已验证业务事实。|
|Impact|确认 20 条 CONTRACT、25 条 TECHNICAL_AGREEMENT；75 条 SOLUTION 排除。P03-A02 需要补充至少 55 条合格记录，并补齐 STANDARD_CAPABILITY、SURVEY。|
|Rollback|删除审计映射和证据，恢复全部记录为待确认；不会修改原始资料或用户工作簿。|

## DEC-20260917-003

|字段|内容|
|---|---|
|Decision ID|DEC-20260917-003|
|Date|2026-09-17|
|WBS|P03-A05|
|Decision|使用百炼 `text-embedding-v4` 768 维作为换模重建验证目标，创建独立 `v2` index identity；保持当前 `v1` 激活，不自动切换。|
|Reason|官方文档和当前华北 2 工作区均支持该模型与维度，可同时验证模型和维度变化；独立索引满足既定不可原地换模规则。|
|Impact|120 条非客户合成记录完成真实全量重建；新增验证制品，不改变正式架构或当前激活绑定。|
|Rollback|删除 `v2` 验证制品即可；`v1` 未被修改。|

## DEC-20260917-004

|字段|内容|
|---|---|
|Decision ID|DEC-20260917-004|
|Date|2026-09-17|
|WBS|P03-A06|
|Decision|所有 PROJECT Vector、Full Text、Hybrid SQL 在各自最内层查询强制使用参数化 `project_id = %(project_id)s`；缺失 ProjectId 在 Repository 调用前拒绝。|
|Reason|只在外层过滤可能让候选集、排序或中间结果接触其他项目数据；参数化内层过滤能同时控制隔离和注入风险。|
|Impact|6 个双项目检索场景跨项目泄漏为 0；形成后续 RetrievalService/Repository 的 PoC 约束。|
|Rollback|回退 PoC 查询实现和证据；不影响正式数据库，因为临时 Schema 已删除。|

## DEC-20260917-005

|字段|内容|
|---|---|
|Decision ID|DEC-20260917-005|
|Date|2026-09-17|
|WBS|P03-A07|
|Decision|PoC Full Text 使用 PostgreSQL `simple` 配置和上游空格分词后的中文术语，并为相同表达式建立 GIN 索引。|
|Reason|PostgreSQL 内置配置不提供可靠中文分词；上游规范化无需引入新第三方组件，且能验证锁定的 PostgreSQL FTS 链路。|
|Impact|4 组 Top-5 Recall 100%，但正式链路必须保留术语规范化，不得把结果解释为数据库原生中文分词。|
|Rollback|删除 PoC FTS 脚本与证据；临时 Schema 已删除。|
