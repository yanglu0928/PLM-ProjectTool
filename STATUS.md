# 项目状态

|字段|当前值|
|---|---|
|Current Phase|Phase 0 技术验证|
|Current WBS|P03-A11~A13：真实 Golden Dataset 质量指标|
|Current Status|FAIL / BLOCKED_QUALITY_GATE|
|Completed Phases|无|
|Completed WBS|POC-01、POC-02、POC-04 已按批准例外收口；P03-A02~A10、P03-A14、P03-A15 已 PASS|
|Blockers|P03-A11~A13 首轮真实指标均 FAIL：Top-5 Recall 60.00%、分类准确率 14.17%、来源引用准确率 50.83%；Golden 标签一致性和检索分层诊断需重新打开 Gate|
|Pending User Decisions|是否批准按“先显式复核最终分类并冻结新 Golden Dataset，再分层诊断与调优检索/Prompt”的顺序继续；或接受 POC-03 失败并指定替代方案|
|Architecture Version|未冻结；正式基线为实施方案 V2.1|
|DB Schema Version|未冻结|
|API Contract Version|未冻结|
|Test Summary|POC-03 91/91 单元测试 PASS；R4 120 条全量实测完成，120/120 实时重排、GIN/HNSW 命中、无缺失预测和越界引用，但三项质量门槛均 FAIL|
|Next WBS|等待 POC-03 Quality Gate 决策；未获确认不得启动下一 WBS|

## 自动执行策略

- 模式：默认自主执行 + Gate 确认 + 异常升级。
- 周额度停止线：剩余低于 20%。
- 最后额度检查：2026-09-18，周窗口已使用 41%，剩余 59%，重置时间 2026-09-23 17:51:41 +08:00。
- GitHub：允许在当前 Scope 和正确分支内自动 fetch、commit、push；禁止 force push、直接提交 main、覆盖未知远端修改或提交 Secret/客户数据。

## 最近检查点

- 分支：`poc/poc-03-plm-rag`
- 最近功能检查点：P03-A11~A13 在 Windows 11 完成 120 条真实质量验证并判定 FAIL；脱敏指标与失败分析已保存，原文、查询、向量和逐条响应仍在 Git 忽略目录。未改变阈值、Golden 标签、模型或 Hybrid 基线。
- 远端同步状态必须在每次任务结束前通过 Git 实时检查，不在本文件固化可能过期的 ahead/behind 数值。
- 本地用户文件和 Git 忽略的客户资料保持不变。
