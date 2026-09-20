# 项目状态

|字段|当前值|
|---|---|
|Current Phase|Phase 0 技术验证|
|Current WBS|P03-A12-R3：R7 Golden 业务语义与引用重新评审|
|Current Status|FAIL / BLOCKED_QUALITY_GATE|
|Completed Phases|无|
|Completed WBS|POC-01、POC-02、POC-04 已按批准例外收口；P03-A02~A11、P03-A14、P03-A15 已 PASS|
|Blockers|R7 重新评审包已生成但尚未人工确认；同一批 120 条已被 Prompt v2 用于诊断，确认后的 R7 只能作为校准集，不能用于关闭 P03-A12/P03-A13，仍须另建独立留出集|
|Pending User Decisions|在本地 R7 工作簿中选择“确认全部AI建议”并填写确认人/日期，或仅对例外项修改后确认；确认前不生成 R7 Golden Dataset|
|Architecture Version|未冻结；正式基线为实施方案 V2.1|
|DB Schema Version|未冻结|
|API Contract Version|未冻结|
|Test Summary|POC-03 129/129 单元测试 PASS；R7 工作簿 4/4 表已渲染、公式错误 0；严格导入预检为 120 PENDING、0 个问题、未输出数据集；本轮外部 AI 调用 0|
|Next WBS|等待 R7 人工确认；确认后严格导入为校准集，再单独设计未被 Prompt v1/v2 使用的独立留出集。任何新外发复验仍须当轮明确授权|

## 自动执行策略

- 模式：默认自主执行 + Gate 确认 + 异常升级。
- 周额度停止线：剩余低于 20%。
- 最后额度检查：2026-09-20，周窗口已使用 54%，剩余 46%，重置时间 2026-09-23 17:51:41 +08:00。
- GitHub：允许在当前 Scope 和正确分支内自动 fetch、commit、push；禁止 force push、直接提交 main、覆盖未知远端修改或提交 Secret/客户数据。

## 最近检查点

- 分支：`poc/poc-03-plm-rag`
- 最近功能检查点：用户批准重新评审后，R6 保留不变；已生成覆盖 120 条的 R7 语义/分类/引用确认包、836 条可选证据和原文定位器。AI 建议变更分类 73 条、引用 58 条，原文定位 120/120；合同、技术协议和调研材料在缺少标准能力交叉证据时保守建议为资料不足。当前仍是未确认状态，R7 数据集未生成，P03-A12/A13 继续 FAIL。
- 远端同步状态必须在每次任务结束前通过 Git 实时检查，不在本文件固化可能过期的 ahead/behind 数值。
- 本地用户文件和 Git 忽略的客户资料保持不变。
