# 项目状态

|字段|当前值|
|---|---|
|Current Phase|Phase 0 技术验证|
|Current WBS|P03-A12-R6：独立留出集问题、分类与引用建议准备|
|Current Status|READY / SOURCE_LOCK_PASS；等待新一轮客户内容外发授权|
|Completed Phases|无|
|Completed WBS|POC-01、POC-02、POC-04 已按批准例外收口；P03-A02~A11、P03-A14、P03-A15 已 PASS|
|Blockers|来源锁已通过；为减少人工逐条编写，下一步拟对 50 条锁定候选生成 AI 问题、五类分类和引用建议，涉及新的客户内容外发，须当轮明确授权后才能执行|
|Pending User Decisions|明确是否同意本轮仅将 50 条已锁定候选内容发送至 DeepSeek，用于生成待人工确认的建议；不调用 Embedding/Reranker，不把 AI 建议直接写成正式真值|
|Architecture Version|未冻结；正式基线为实施方案 V2.1|
|DB Schema Version|未冻结|
|API Contract Version|未冻结|
|Test Summary|POC-03 141/141 单元测试 PASS；R7.1 严格导入与覆盖 PASS；49 份实际客户调研记录本地解析与文件/正文 Hash 去重 PASS；50 条独立来源锁 PASS，配额 33/7/8/2，调研类 2/2 仅来自实际记录；本轮外部 AI 调用 0|
|Next WBS|取得当轮数据外发授权后，为 50 条来源锁生成 AI 预填建议与友好确认包；严格人工确认后才能导出独立留出集并执行真实质量复验|

## 自动执行策略

- 模式：默认自主执行 + Gate 确认 + 异常升级。
- 周额度停止线：剩余低于 20%。
- 最后额度检查：2026-09-20，周窗口已使用 56%，剩余 44%，重置时间 2026-09-23 17:51:41 +08:00。
- GitHub：允许在当前 Scope 和正确分支内自动 fetch、commit、push；禁止 force push、直接提交 main、覆盖未知远端修改或提交 Secret/客户数据。

## 最近检查点

- 分支：`poc/poc-03-plm-rag`
- 最近功能检查点：R7.1 校准数据集及覆盖审计 PASS。49 份新增资料已按“实际客户调研记录”本地解析，506 个内容块、282,819 字符，文件 Hash 与正文 Hash 均未与历史语料重复。50 条来源锁已完成，配额为标准能力/合同/技术协议/调研 33/7/8/2；历史调研表单的 13 个块因仅供参考被排除，2 条调研候选均来自新实际记录。
- 远端同步状态必须在每次任务结束前通过 Git 实时检查，不在本文件固化可能过期的 ahead/behind 数值。
- 本地用户文件和 Git 忽略的客户资料保持不变。
