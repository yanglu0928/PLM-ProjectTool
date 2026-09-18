# 项目状态

|字段|当前值|
|---|---|
|Current Phase|Phase 0 技术验证|
|Current WBS|P03-A11~A13-R3：R6 质量复验|
|Current Status|AWAITING_EXTERNAL_DATA_PROCESSING_APPROVAL|
|Completed Phases|无|
|Completed WBS|POC-01、POC-02、POC-04 已按批准例外收口；P03-A02~A10、P03-A14、P03-A15 已 PASS|
|Blockers|R6 已严格导入并完成本地复验；完整真实链路会把 R6 查询和候选文档片段发送至百炼与 DeepSeek，安全审查要求本轮显式的数据外发授权。拦截发生在进程启动前，尚未发送任何 R6 数据|
|Pending User Decisions|是否明确允许把 R6 的 120 条查询及各自检索候选片段发送至阿里云百炼（Embedding/Reranker）和 DeepSeek（分类/引用预测），仅用于 P03-A11~A13 质量复验；输出继续只保存在本地并提交脱敏汇总|
|Architecture Version|未冻结；正式基线为实施方案 V2.1|
|DB Schema Version|未冻结|
|API Contract Version|未冻结|
|Test Summary|POC-03 107/107 单元测试 PASS；R6 严格导入 120/120、待确认 0、问题 0，覆盖审计 PASS；本地 OCR 规范化检索 Top-5 116/120（96.67%），P03-A11 PASS；P03-A12/A13 真实复验未启动|
|Next WBS|取得本轮外部数据处理明确授权后运行 120 条真实百炼/DeepSeek 质量复验；若不授权，则只能保留本地 P03-A11 结果，P03-A12/A13 不形成通过结论|

## 自动执行策略

- 模式：默认自主执行 + Gate 确认 + 异常升级。
- 周额度停止线：剩余低于 20%。
- 最后额度检查：2026-09-18，周窗口已使用 48%，剩余 52%，重置时间 2026-09-23 17:51:41 +08:00。
- GitHub：允许在当前 Scope 和正确分支内自动 fetch、commit、push；禁止 force push、直接提交 main、覆盖未知远端修改或提交 Secret/客户数据。

## 最近检查点

- 分支：`poc/poc-03-plm-rag`
- 最近功能检查点：用户已确认 R6；严格导入生成 120 条 R6 Golden Dataset，6 条按获批建议更新问题/引用，114 条及全部分类保持不变。覆盖审计 PASS；本地确定性检索 Top-5 为 116/120（96.67%）。外部真实复验因缺少本轮客户数据处理明确授权而在进程启动前停止，未发送数据。
- 远端同步状态必须在每次任务结束前通过 Git 实时检查，不在本文件固化可能过期的 ahead/behind 数值。
- 本地用户文件和 Git 忽略的客户资料保持不变。
