# 项目状态

|字段|当前值|
|---|---|
|Current Phase|Phase 0 技术验证|
|Current WBS|P03-A02-R5：Golden 标签轻量复核|
|Current Status|FAIL / BLOCKED_QUALITY_GATE|
|Completed Phases|无|
|Completed WBS|POC-01、POC-02、POC-04 已按批准例外收口；P03-A02~A10、P03-A14、P03-A15 已 PASS|
|Blockers|R1 质量失败证据保持有效；R5 已将 120 条复核压缩为 62 条明确结论和 58 条/7 组批量确认，但尚未收到工作簿中的最终人工确认，因此不得导出新 Golden Dataset 或启动检索调优|
|Pending User Decisions|打开 R5 工作簿，在“批量规则”B5 选择“确认使用AI建议批量规则”；如有例外，仅在“冲突确认”填写单条最终分类|
|Architecture Version|未冻结；正式基线为实施方案 V2.1|
|DB Schema Version|未冻结|
|API Contract Version|未冻结|
|Test Summary|POC-03 96/96 单元测试 PASS；R5 工作簿 4 张表完成公式扫描和视觉检查，公式错误 0；严格导入验证为 AWAITING_HUMAN_CONFIRMATION、问题 0、未写出数据集|
|Next WBS|收到 R5 人工确认后严格导入并冻结 Golden Dataset R5，然后按 Vector→FTS→融合→Reranker→分类 Prompt 分层诊断与调优|

## 自动执行策略

- 模式：默认自主执行 + Gate 确认 + 异常升级。
- 周额度停止线：剩余低于 20%。
- 最后额度检查：2026-09-18，周窗口已使用 43%，剩余 57%，重置时间 2026-09-23 17:51:41 +08:00。
- GitHub：允许在当前 Scope 和正确分支内自动 fetch、commit、push；禁止 force push、直接提交 main、覆盖未知远端修改或提交 Secret/客户数据。

## 最近检查点

- 分支：`poc/poc-03-plm-rag`
- 最近功能检查点：已按用户批准的 Quality Gate 修复路线生成 R5 轻量确认包；62 条 R4 明确结论无需重复确认，58 条未明确记录归并为 7 组，默认保持“未确认”。严格导入器、覆盖优先级、防篡改和脱敏报告测试通过；未改变门槛、模型或 Hybrid 基线。
- 远端同步状态必须在每次任务结束前通过 Git 实时检查，不在本文件固化可能过期的 ahead/behind 数值。
- 本地用户文件和 Git 忽略的客户资料保持不变。
