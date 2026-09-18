# 项目状态

|字段|当前值|
|---|---|
|Current Phase|Phase 0 技术验证|
|Current WBS|P0.09 / P03-A02：Golden Dataset 人工确认|
|Current Status|BLOCKED_INSUFFICIENT_APPROVED_CASES|
|Completed Phases|无|
|Completed WBS|POC-01、POC-02、POC-04 已按批准例外收口；P03-A03~A10、P03-A14、P03-A15 已 PASS|
|Blockers|R4 严格导入复核得到 1 条 APPROVED、119 条 PENDING；正式 Golden Dataset 最低需要 100 条，当前还差 99 条|
|Pending User Decisions|如需继续 P03-A11~A13，请在 R4 中再确认至少 99 条；“暂不处理”不会被自动视为批准|
|Architecture Version|未冻结；正式基线为实施方案 V2.1|
|DB Schema Version|未冻结|
|API Contract Version|未冻结|
|Test Summary|POC-03 当前 79/79 单元测试 PASS；R4 严格导入 120 行、0 个校验问题、1 条批准、119 条暂缓，未写出正式数据集|
|Next WBS|等待 R4 达到 100~200 条有效人工批准；之后导出正式 Golden Dataset 并执行 P03-A11~A13|

## 自动执行策略

- 模式：默认自主执行 + Gate 确认 + 异常升级。
- 周额度停止线：剩余低于 20%。
- 最后额度检查：2026-09-18，周窗口已使用 37%，剩余 63%，重置时间 2026-09-23 17:51:41 +08:00。
- GitHub：允许在当前 Scope 和正确分支内自动 fetch、commit、push；禁止 force push、直接提交 main、覆盖未知远端修改或提交 Secret/客户数据。

## 最近检查点

- 分支：`poc/poc-03-plm-rag`
- 最近功能检查点：R4 已完成严格导入复核；1 条可转正式记录、119 条暂缓，Golden Dataset 未导出。
- 远端同步状态必须在每次任务结束前通过 Git 实时检查，不在本文件固化可能过期的 ahead/behind 数值。
- 本地用户文件和 Git 忽略的客户资料保持不变。
