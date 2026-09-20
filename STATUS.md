# 项目状态

|字段|当前值|
|---|---|
|Current Phase|Phase 0 技术验证|
|Current WBS|P03-A12-R5：独立留出集设计与来源锁定|
|Current Status|IN PROGRESS / CALIBRATION_PASS|
|Completed Phases|无|
|Completed WBS|POC-01、POC-02、POC-04 已按批准例外收口；P03-A02~A11、P03-A14、P03-A15 已 PASS|
|Blockers|R7.1 严格导入、Schema 与覆盖审计均 PASS，但 R7/R7.1 已用于 Prompt v2 诊断，只能作为校准集；P03-A12/P03-A13 必须由未被 Prompt v1/v2 使用的独立留出集关闭|
|Pending User Decisions|无；在出现新的数据外发复验前仍须取得当轮明确授权|
|Architecture Version|未冻结；正式基线为实施方案 V2.1|
|DB Schema Version|未冻结|
|API Contract Version|未冻结|
|Test Summary|POC-03 134/134 单元测试 PASS；R7.1 严格导入 1/1、Schema 校验 PASS；120 条覆盖审计 PASS（五类齐全、重复问题 0、四类来源齐全）；本轮外部 AI 调用 0|
|Next WBS|建立未被 Prompt v1/v2 使用的独立留出集方案、来源锁定规则和验收包；任何新外发复验仍须当轮明确授权|

## 自动执行策略

- 模式：默认自主执行 + Gate 确认 + 异常升级。
- 周额度停止线：剩余低于 20%。
- 最后额度检查：2026-09-20，周窗口已使用 55%，剩余 45%，重置时间 2026-09-23 17:51:41 +08:00。
- GitHub：允许在当前 Scope 和正确分支内自动 fetch、commit、push；禁止 force push、直接提交 main、覆盖未知远端修改或提交 Secret/客户数据。

## 最近检查点

- 分支：`poc/poc-03-plm-rag`
- 最近功能检查点：用户已确认 R7.1 单条例外；严格导入生成新的本地 R7.1 校准数据集，Schema 校验 PASS，覆盖审计 120 条 PASS，五类结论与四类来源齐全、重复问题 0。R7 与 R7.1 均保留且不覆盖；因同批数据已参与 Prompt v2 诊断，P03-A12/A13 仍不能据此关闭，已进入独立留出集设计。
- 远端同步状态必须在每次任务结束前通过 Git 实时检查，不在本文件固化可能过期的 ahead/behind 数值。
- 本地用户文件和 Git 忽略的客户资料保持不变。
