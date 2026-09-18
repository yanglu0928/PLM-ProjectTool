# 项目状态

|字段|当前值|
|---|---|
|Current Phase|Phase 0 技术验证|
|Current WBS|P03-A11~A13-R3：R6 质量复验|
|Current Status|BLOCKED_QUALITY_GATE|
|Completed Phases|无|
|Completed WBS|POC-01、POC-02、POC-04 已按批准例外收口；P03-A02~A10、P03-A14、P03-A15 已 PASS|
|Blockers|R6 真实端到端复验三项均未达到 Gate：Top-5 72/120（60.00%）、分类 57/120（47.50%）、引用 62/120（51.67%）。分层诊断表明端到端 Hybrid/Reranker 未采用本地已验证的来源类型过滤与确定性词法 IDF 路径，造成 25 条通道召回缺失、15 条融合丢失和 8 条重排丢失|
|Pending User Decisions|无；先在既定模型、门槛和 R6 Golden Dataset 不变的前提下，按 DEC-20260918-009 对齐正式检索链与已验证本地检索策略。再次外发复验前重新取得明确授权|
|Architecture Version|未冻结；正式基线为实施方案 V2.1|
|DB Schema Version|未冻结|
|API Contract Version|未冻结|
|Test Summary|POC-03 107/107 单元测试 PASS；R6 真实链路完成 120/120 百炼重排和 120/120 DeepSeek 预测，预测缺失 0、越界引用 0、GIN/HNSW 均命中；三项指标为 60.00% / 47.50% / 51.67%，均 FAIL|
|Next WBS|P03-A11-R4：让端到端 Hybrid Retrieval 显式采用来源类型过滤、OCR 空白规范化和确定性词法 IDF 候选通道，先执行无外部调用的回归与本地排名验证|

## 自动执行策略

- 模式：默认自主执行 + Gate 确认 + 异常升级。
- 周额度停止线：剩余低于 20%。
- 最后额度检查：2026-09-18，周窗口已使用 49%，剩余 51%，重置时间 2026-09-23 17:51:41 +08:00。
- GitHub：允许在当前 Scope 和正确分支内自动 fetch、commit、push；禁止 force push、直接提交 main、覆盖未知远端修改或提交 Secret/客户数据。

## 最近检查点

- 分支：`poc/poc-03-plm-rag`
- 最近功能检查点：用户明确授权后完成 R6 真实质量复验。百炼 Embedding/Reranker 与 DeepSeek 预测均按授权执行；120 次重排、120 次预测完整，数据库正常关闭。正式端到端指标为 Top-5 60.00%、分类 47.50%、引用 51.67%，三项均 FAIL；本地逐条缓存和客户内容继续由 Git 忽略。
- 远端同步状态必须在每次任务结束前通过 Git 实时检查，不在本文件固化可能过期的 ahead/behind 数值。
- 本地用户文件和 Git 忽略的客户资料保持不变。
