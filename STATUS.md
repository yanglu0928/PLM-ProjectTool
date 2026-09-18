# 项目状态

|字段|当前值|
|---|---|
|Current Phase|Phase 0 技术验证|
|Current WBS|P03-A11~A13：真实 Golden Dataset 质量指标|
|Current Status|BLOCKED_MISSING_BAILIAN_CREDENTIAL|
|Completed Phases|无|
|Completed WBS|POC-01、POC-02、POC-04 已按批准例外收口；P03-A02~A10、P03-A14、P03-A15 已 PASS|
|Blockers|P03-A11~A13 已由 P03-A02 解锁，但当前会话找不到百炼 Embedding/Reranker 密钥；不得用合成向量替代真实 `qwen3.7-text-embedding` / `qwen3-rerank` 指标|
|Pending User Decisions|无需业务决策；需在本机恢复百炼凭据，可将当前有效 Key 放入 Git 忽略的 `secrets/bailian-api-key.txt` 后继续|
|Architecture Version|未冻结；正式基线为实施方案 V2.1|
|DB Schema Version|未冻结|
|API Contract Version|未冻结|
|Test Summary|POC-03 当前 82/82 单元测试 PASS；R4 严格导入 120 条 APPROVED、0 个问题，正式数据集已在本地写出；覆盖审计 120 条、29 份文档、四类来源、六类结果 PASS|
|Next WBS|执行 P03-A11 Top-5 Recall、P03-A12 分类准确率、P03-A13 来源引用准确率|

## 自动执行策略

- 模式：默认自主执行 + Gate 确认 + 异常升级。
- 周额度停止线：剩余低于 20%。
- 最后额度检查：2026-09-18，周窗口已使用 38%，剩余 62%，重置时间 2026-09-23 17:51:41 +08:00。
- GitHub：允许在当前 Scope 和正确分支内自动 fetch、commit、push；禁止 force push、直接提交 main、覆盖未知远端修改或提交 Secret/客户数据。

## 最近检查点

- 分支：`poc/poc-03-plm-rag`
- 最近功能检查点：更新后的 R4 已完成严格导入和覆盖审计；120 条均满足批准 Gate，正式 Golden Dataset 仅保存在 Git 忽略的本地目录，P03-A02 已 PASS。P03-A11~A13 编码前检查完成，等待本地百炼凭据后执行真实 Hybrid/Reranker 指标。
- 远端同步状态必须在每次任务结束前通过 Git 实时检查，不在本文件固化可能过期的 ahead/behind 数值。
- 本地用户文件和 Git 忽略的客户资料保持不变。
