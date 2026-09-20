# 项目状态

|字段|当前值|
|---|---|
|Current Phase|Phase 0 技术验证|
|Current WBS|P03-A12-R1：Prompt v2 本地设计与离线评估|
|Current Status|READY_FOR_LIVE_DEEPSEEK_APPROVAL|
|Completed Phases|无|
|Completed WBS|POC-01、POC-02、POC-04 已按批准例外收口；P03-A02~A11、P03-A14、P03-A15 已 PASS|
|Blockers|Prompt v2 离线契约已 PASS，但离线步骤不能测量 DeepSeek 分类准确率；P03-A12 正式状态仍以 v1 的 57/120（47.50%）为 FAIL，必须完成新的真实模型复验|
|Pending User Decisions|是否明确允许把 R6 的 120 条查询及每条 5 个 R5 Context（每段不超过 1000 字）发送至 DeepSeek，仅执行 P03-A12 Prompt v2 分类/引用复验；本轮不调用百炼 Embedding 或 Reranker|
|Architecture Version|未冻结；正式基线为实施方案 V2.1|
|DB Schema Version|未冻结|
|API Contract Version|未冻结|
|Test Summary|POC-03 124/124 单元测试 PASS；Prompt v2 为 120/120 条准备 5 个来源隔离 Context，精确证据 114/120、同文档 118/120、正文截断 0、Golden 字段泄漏 0；Embedding/Reranker/DeepSeek 外部调用均为 0|
|Next WBS|取得本轮明确数据外发授权后，以 `--prediction-only` 复用完整本地 Embedding/R5 检索缓存，只执行 120 条 DeepSeek Prompt v2 复验；未授权前不发送数据|

## 自动执行策略

- 模式：默认自主执行 + Gate 确认 + 异常升级。
- 周额度停止线：剩余低于 20%。
- 最后额度检查：2026-09-20，周窗口已使用 52%，剩余 48%，重置时间 2026-09-23 17:51:41 +08:00。
- GitHub：允许在当前 Scope 和正确分支内自动 fetch、commit、push；禁止 force push、直接提交 main、覆盖未知远端修改或提交 Secret/客户数据。

## 最近检查点

- 分支：`poc/poc-03-plm-rag`
- 最近功能检查点：P03-A12 Prompt v2 已完成本地设计与离线审计。v2 只允许五类正式标签，按“匹配性 → 充分性 → 满足程度”判断，使用 OCR 规范化完整 Chunk，并以 PromptId/Version 绑定预测缓存。120/120 条 payload、来源隔离、零截断和零 Golden 字段泄漏均 PASS；分类准确率尚未真实测量。
- 远端同步状态必须在每次任务结束前通过 Git 实时检查，不在本文件固化可能过期的 ahead/behind 数值。
- 本地用户文件和 Git 忽略的客户资料保持不变。
