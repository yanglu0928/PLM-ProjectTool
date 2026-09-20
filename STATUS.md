# 项目状态

|字段|当前值|
|---|---|
|Current Phase|Phase 0 技术验证|
|Current WBS|P03-A12-R4：R7.1 非标准覆盖例外确认|
|Current Status|FAIL / BLOCKED_QUALITY_GATE|
|Completed Phases|无|
|Completed WBS|POC-01、POC-02、POC-04 已按批准例外收口；P03-A02~A11、P03-A14、P03-A15 已 PASS|
|Blockers|R7 严格导入与 Schema 校验已 PASS，但覆盖审计发现 `NON_STANDARD=0`，未满足五类全覆盖；同一批 120 条已被 Prompt v2 用于诊断，R7/R7.1 只能作为校准集，不能用于关闭 P03-A12/P03-A13，仍须另建独立留出集|
|Pending User Decisions|在本地 R7.1 工作簿中选择“确认本次修正”并填写确认人/日期，或退回修正；AI 不得自动把例外建议写成正式业务事实|
|Architecture Version|未冻结；正式基线为实施方案 V2.1|
|DB Schema Version|未冻结|
|API Contract Version|未冻结|
|Test Summary|POC-03 130/130 单元测试 PASS；R7 严格导入 120/120、Schema 校验 PASS；覆盖审计除 `NON_STANDARD` 缺失外均通过；R7.1 工作簿 2/2 表已渲染、公式错误 0；本轮外部 AI 调用 0|
|Next WBS|等待 R7.1 单条人工确认；确认后生成 R7.1 校准集并重跑覆盖审计，再单独设计未被 Prompt v1/v2 使用的独立留出集。任何新外发复验仍须当轮明确授权|

## 自动执行策略

- 模式：默认自主执行 + Gate 确认 + 异常升级。
- 周额度停止线：剩余低于 20%。
- 最后额度检查：2026-09-20，周窗口已使用 55%，剩余 45%，重置时间 2026-09-23 17:51:41 +08:00。
- GitHub：允许在当前 Scope 和正确分支内自动 fetch、commit、push；禁止 force push、直接提交 main、覆盖未知远端修改或提交 Secret/客户数据。

## 最近检查点

- 分支：`poc/poc-03-plm-rag`
- 最近功能检查点：用户已完成 R7 全局人工确认；严格导入生成 120 条本地 R7 校准数据集，Schema 校验 PASS，0 条待确认、0 条退回。覆盖审计发现五类中缺少 `NON_STANDARD`，因此不伪造 PASS；已基于合同中直接出现的二次开发交付证据生成只含 GD-0060 的 R7.1 例外确认表，等待单条人工确认。P03-A12/A13 继续 FAIL。
- 远端同步状态必须在每次任务结束前通过 Git 实时检查，不在本文件固化可能过期的 ahead/behind 数值。
- 本地用户文件和 Git 忽略的客户资料保持不变。
