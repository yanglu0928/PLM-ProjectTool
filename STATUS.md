# 项目状态

|字段|当前值|
|---|---|
|Current Phase|Phase 0 技术验证|
|Current WBS|P0.09 / P03-A02：Golden Dataset 来源覆盖|
|Current Status|BLOCKED_PENDING_L3_DECISION|
|Completed Phases|无|
|Completed WBS|POC-01、POC-02、POC-04 已按批准例外收口；P03-A03~A10、P03-A14、P03-A15 已 PASS|
|Blockers|P03-A02 仅有 45 条合格来源，距最低 100 条差 55 条，且缺少 STANDARD_CAPABILITY、SURVEY 真实语料；Phase 0 其余阻塞 PoC 尚未全部完成|
|Pending User Decisions|L3：补充真实标准能力/调研语料，或批准修改 P03-A02 的四类来源覆盖验收标准|
|Architecture Version|未冻结；正式基线为实施方案 V2.1|
|DB Schema Version|未冻结|
|API Contract Version|未冻结|
|Test Summary|POC-03 当前 68/68 单元测试 PASS；P03-A15 的 DB/Reranker/AI 不可用、空结果、低可靠度及正常链路共 6 场景 PASS；P03-A02 为 `BLOCKED_MISSING_SOURCE_CORPORA`|
|Next WBS|等待 P03-A02 L3 决策或补充真实语料；其后执行 P03-A11~A13 真实 Golden Dataset 指标|

## 自动执行策略

- 模式：默认自主执行 + Gate 确认 + 异常升级。
- 周额度停止线：剩余低于 20%。
- 最后额度检查：2026-09-17，周窗口已使用 35%，剩余 65%，重置时间 2026-09-23 17:51:41 +08:00。
- GitHub：允许在当前 Scope 和正确分支内自动 fetch、commit、push；禁止 force push、直接提交 main、覆盖未知远端修改或提交 Secret/客户数据。

## 最近检查点

- 分支：`poc/poc-03-plm-rag`
- 最近功能检查点：POC-03 R3 人工确认 UX 原型已完成并本地提交。
- 远端同步状态必须在每次任务结束前通过 Git 实时检查，不在本文件固化可能过期的 ahead/behind 数值。
- 本地用户文件和 Git 忽略的客户资料保持不变。
