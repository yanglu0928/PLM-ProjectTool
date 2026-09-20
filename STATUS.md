# 项目状态

|字段|当前值|
|---|---|
|Current Phase|Phase 0 技术验证|
|Current WBS|P03-A11-R4：正式检索链对齐|
|Current Status|READY_FOR_LIVE_RERANK_APPROVAL|
|Completed Phases|无|
|Completed WBS|POC-01、POC-02、POC-04 已按批准例外收口；P03-A02~A10、P03-A14、P03-A15 已 PASS|
|Blockers|R4 检索链本地候选池已达 119/120（99.17%），但候选池不等于 Reranker Top-5；P03-A11 正式状态仍以最近真实结果 72/120（60.00%）为 FAIL。新候选集合必须经百炼 `qwen3-rerank` 重新排序后才能判定|
|Pending User Decisions|是否明确允许把 R6 的 120 条查询及每条 13~59 个候选片段发送至阿里云百炼 `qwen3-rerank`，仅执行 P03-A11-R4 的真实 Top-5 复验；本轮不调用 DeepSeek|
|Architecture Version|未冻结；正式基线为实施方案 V2.1|
|DB Schema Version|未冻结|
|API Contract Version|未冻结|
|Test Summary|POC-03 113/113 单元测试 PASS；R4 本地 PostgreSQL 回放 120 条，候选池精确覆盖 119/120（99.17%）、同文档 120/120、来源越界 0，GIN/HNSW 均命中，外部调用 0|
|Next WBS|取得本轮明确数据外发授权后，只运行百炼 Reranker 的 120 条真实 Top-5 复验；若 P03-A11 通过，再进入 P03-A12 Prompt v2|

## 自动执行策略

- 模式：默认自主执行 + Gate 确认 + 异常升级。
- 周额度停止线：剩余低于 20%。
- 最后额度检查：2026-09-20，周窗口已使用 50%，剩余 50%，重置时间 2026-09-23 17:51:41 +08:00。
- GitHub：允许在当前 Scope 和正确分支内自动 fetch、commit、push；禁止 force push、直接提交 main、覆盖未知远端修改或提交 Secret/客户数据。

## 最近检查点

- 分支：`poc/poc-03-plm-rag`
- 最近功能检查点：R4 正式检索候选链已接入来源类型过滤、OCR 规范化和词法 IDF 通道；旧检索缓存通过 pipeline version 失效。无外部调用的 120 条本地回放为 119/120（99.17%），113/113 测试通过；正式 Top-5 仍等待新的百炼 Reranker 验证。
- 远端同步状态必须在每次任务结束前通过 Git 实时检查，不在本文件固化可能过期的 ahead/behind 数值。
- 本地用户文件和 Git 忽略的客户资料保持不变。
