# 项目状态

|字段|当前值|
|---|---|
|Current Phase|Phase 0 技术验证|
|Current WBS|P03-A11-R5：保护性词法融合复验|
|Current Status|P03_A11_PASS_READY_FOR_P03_A12|
|Completed Phases|无|
|Completed WBS|POC-01、POC-02、POC-04 已按批准例外收口；P03-A02~A11、P03-A14、P03-A15 已 PASS|
|Blockers|P03-A12 分类准确率仍为 57/120（47.50%），P03-A13 来源引用准确率仍为 62/120（51.67%）；两项尚未达到 90%/98% Gate，POC-03 不能收口|
|Pending User Decisions|无；进入 P03-A12 前按周额度规则检查后可继续本地 Prompt v2 设计与离线测试，任何新的客户数据外发仍需按当轮范围重新确认|
|Architecture Version|未冻结；正式基线为实施方案 V2.1|
|DB Schema Version|未冻结|
|API Contract Version|未冻结|
|Test Summary|POC-03 117/117 单元测试 PASS；R4 真实百炼纯重排 91/120（75.83%），R5 保护性融合复用 120 条真实重排结果后达到精确 Top-5 114/120（95.00%）、同文档 118/120（98.33%），GIN/HNSW 均命中；R5 复算外部调用 0|
|Next WBS|P03-A12：Prompt v2 本地设计与离线分类评估；不得因 P03-A11 通过而提前改判 P03-A12/P03-A13|

## 自动执行策略

- 模式：默认自主执行 + Gate 确认 + 异常升级。
- 周额度停止线：剩余低于 20%。
- 最后额度检查：2026-09-20，周窗口已使用 51%，剩余 49%，重置时间 2026-09-23 17:51:41 +08:00。
- GitHub：允许在当前 Scope 和正确分支内自动 fetch、commit、push；禁止 force push、直接提交 main、覆盖未知远端修改或提交 Secret/客户数据。

## 最近检查点

- 分支：`poc/poc-03-plm-rag`
- 最近功能检查点：用户明确授权后，R4 完成 120/120 条百炼 `qwen3-rerank` 真实重排，纯语义 Top-5 为 91/120（75.83%）。R5 采用“百炼第 1 名 + OCR 规范化词法前 4 名”的无标签保护性融合，复用同批真实重排缓存得到 114/120（95.00%），P03-A11 PASS；117/117 测试通过。结果无余量且属于同集探索调优，仍需独立留出集验证。
- 远端同步状态必须在每次任务结束前通过 Git 实时检查，不在本文件固化可能过期的 ahead/behind 数值。
- 本地用户文件和 Git 忽略的客户资料保持不变。
