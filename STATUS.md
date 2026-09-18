# 项目状态

|字段|当前值|
|---|---|
|Current Phase|Phase 0 技术验证|
|Current WBS|P03-A11~A13-R2：R5 质量分层调优与引用基线复核|
|Current Status|BLOCKED_L3_DECISION|
|Completed Phases|无|
|Completed WBS|POC-01、POC-02、POC-04 已按批准例外收口；P03-A02~A10、P03-A14、P03-A15 已 PASS|
|Blockers|R5 标签已确认并严格导入。OCR 规范化词法检索达到 Top-5 114/120（95.00%），但剩余 6 条低区分度问题的唯一目标 Chunk 排名为 8、11、24、27、41、117；当 AI Context 只含 Top-5 时，来源引用准确率理论上限为 95.00%，低于 P03-A13 的 98%，需决定修订 Golden 引用集合/问题或调整引用验收口径|
|Pending User Decisions|L3：选择修订 6 条低区分度 Golden 问题及可接受引用集合（建议），或明确调整 P03-A13 的引用上下文/验收口径；不得由 AI 静默改写冻结真值|
|Architecture Version|未冻结；正式基线为实施方案 V2.1|
|DB Schema Version|未冻结|
|API Contract Version|未冻结|
|Test Summary|POC-03 103/103 单元测试 PASS；R5 严格导入 120/120、Schema/覆盖审计 PASS；真实百炼调优重排 120/120，Top-5 89/120；OCR 规范化确定性检索 Top-5 114/120、Top-20 116/120|
|Next WBS|收到 L3 决策后生成 R6 引用复核包并重跑 P03-A11~A13；受影响任务暂停，未进入分类 Prompt 的新增外部调用|

## 自动执行策略

- 模式：默认自主执行 + Gate 确认 + 异常升级。
- 周额度停止线：剩余低于 20%。
- 最后额度检查：2026-09-18，周窗口已使用 45%，剩余 55%，重置时间 2026-09-23 17:51:41 +08:00。
- GitHub：允许在当前 Scope 和正确分支内自动 fetch、commit、push；禁止 force push、直接提交 main、覆盖未知远端修改或提交 Secret/客户数据。

## 最近检查点

- 分支：`poc/poc-03-plm-rag`
- 最近功能检查点：R5 全局确认已严格导入并冻结 120 条最终业务标签；工作流态 `HUMAN_CONFIRMATION_REQUIRED` 已从最终标签集合排除。分层诊断、72 组候选扫描和 120/120 次真实百炼重排完成；新增中文 OCR 字间空白规范化后，确定性 Top-5 达到 95.00%。未改动引用真值或 98% 门槛，L3 决策前保持安全检查点。
- 远端同步状态必须在每次任务结束前通过 Git 实时检查，不在本文件固化可能过期的 ahead/behind 数值。
- 本地用户文件和 Git 忽略的客户资料保持不变。
