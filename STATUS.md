# 项目状态

|字段|当前值|
|---|---|
|Current Phase|Phase 0 技术验证|
|Current WBS|P03-A12-R2：Prompt v2 真实复验与质量 Gate 诊断|
|Current Status|FAIL / BLOCKED_QUALITY_GATE|
|Completed Phases|无|
|Completed WBS|POC-01、POC-02、POC-04 已按批准例外收口；P03-A02~A11、P03-A14、P03-A15 已 PASS|
|Blockers|Prompt v2 真实 DeepSeek 复验已完成，但分类仅 51/120（42.50%），低于 90%；引用仅 62/120（51.67%），低于 98%。诊断显示部分 R6 问题与人工分类/唯一期望 Chunk 之间缺少可由 Prompt 输入推导的判定语义，继续针对同一验收集调 Prompt 会产生过拟合风险|
|Pending User Decisions|L3：是否重新打开 R6 Golden Dataset 的业务语义评审，为每条问题补充可判定的“需求/结论目标”、分类理由及可接受引用集合；未经确认不得修改已冻结 R6 标签、引用或验收门槛|
|Architecture Version|未冻结；正式基线为实施方案 V2.1|
|DB Schema Version|未冻结|
|API Contract Version|未冻结|
|Test Summary|POC-03 124/124 单元测试 PASS；Prompt v2 真实复验 120/120 预测完整、越界引用 0；Embedding 外部调用 0、当前轮 Reranker 外部调用 0、复用 120 条已获批真实重排结果|
|Next WBS|等待 R6 业务语义/引用 Gate 的 L3 决定；在此之前不启动 Prompt v3、不修改 Golden、不降低 90%/98% 门槛，也不新增客户数据外发|

## 自动执行策略

- 模式：默认自主执行 + Gate 确认 + 异常升级。
- 周额度停止线：剩余低于 20%。
- 最后额度检查：2026-09-20，周窗口已使用 52%，剩余 48%，重置时间 2026-09-23 17:51:41 +08:00。
- GitHub：允许在当前 Scope 和正确分支内自动 fetch、commit、push；禁止 force push、直接提交 main、覆盖未知远端修改或提交 Secret/客户数据。

## 最近检查点

- 分支：`poc/poc-03-plm-rag`
- 最近功能检查点：用户明确授权后，Prompt v2 以 `--prediction-only` 完成 120/120 条真实 DeepSeek 复验；两个瞬时空/非约束响应通过逐条缓存断点续跑恢复。Top-5 为 114/120（95.00%），分类为 51/120（42.50%），引用为 62/120（51.67%）；P03-A12/A13 继续 FAIL，且不得以继续同集 Prompt 调优掩盖 Golden 可判定性风险。
- 远端同步状态必须在每次任务结束前通过 Git 实时检查，不在本文件固化可能过期的 ahead/behind 数值。
- 本地用户文件和 Git 忽略的客户资料保持不变。
