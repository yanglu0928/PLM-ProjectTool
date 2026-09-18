# 项目状态

|字段|当前值|
|---|---|
|Current Phase|Phase 0 技术验证|
|Current WBS|P0.09 / P03-A02：Golden Dataset 人工确认|
|Current Status|AWAITING_HUMAN_REVIEW|
|Completed Phases|无|
|Completed WBS|POC-01、POC-02、POC-04 已按批准例外收口；P03-A03~A10、P03-A14、P03-A15 已 PASS|
|Blockers|来源数量与四类覆盖缺口已解除；120 条新候选仍须人工确认，未经确认不得成为 Golden Dataset 真值或用于质量指标|
|Pending User Decisions|完成本地 R4 确认清单；AI 建议不能替代人工业务确认|
|Architecture Version|未冻结；正式基线为实施方案 V2.1|
|DB Schema Version|未冻结|
|API Contract Version|未冻结|
|Test Summary|POC-03 当前 75/75 单元测试 PASS；标准能力库 20/20 解析 PASS；29 份四类来源文档生成 120 条候选并覆盖 29/29 文档；R4 工作簿公式错误 0|
|Next WBS|导入人工确认后的 100~200 条正式 Golden Dataset，再执行 P03-A11~A13 真实质量指标|

## 自动执行策略

- 模式：默认自主执行 + Gate 确认 + 异常升级。
- 周额度停止线：剩余低于 20%。
- 最后额度检查：2026-09-18，周窗口已使用 37%，剩余 63%，重置时间 2026-09-23 17:51:41 +08:00。
- GitHub：允许在当前 Scope 和正确分支内自动 fetch、commit、push；禁止 force push、直接提交 main、覆盖未知远端修改或提交 Secret/客户数据。

## 最近检查点

- 分支：`poc/poc-03-plm-rag`
- 最近功能检查点：标准能力库 20 份 DOCX 已只读接入；四类来源 R4 人工确认包已在本地生成并通过工作簿检查。
- 远端同步状态必须在每次任务结束前通过 Git 实时检查，不在本文件固化可能过期的 ahead/behind 数值。
- 本地用户文件和 Git 忽略的客户资料保持不变。
