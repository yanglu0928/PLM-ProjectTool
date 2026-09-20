# 项目状态

|字段|当前值|
|---|---|
|Current Phase|Phase 0 技术验证|
|Current WBS|P03-A12-R5：独立留出集设计与来源锁定|
|Current Status|BLOCKED / MISSING_INDEPENDENT_SURVEY_SOURCE|
|Completed Phases|无|
|Completed WBS|POC-01、POC-02、POC-04 已按批准例外收口；P03-A02~A11、P03-A14、P03-A15 已 PASS|
|Blockers|独立留出集目标 50 条中，调研类要求 2 条；当前唯一调研文档的全部可用 Chunk/相邻定位均已被历史 Prompt、检索或评审链路暴露，严格检查与仅模型暴露检查的可用量均为 0，不能复用污染样本|
|Pending User Decisions|在 `artifacts/poc-03/holdout/source-drop/` 放入至少 1 份、建议 2 份此前未进入 POC-03 的真实调研业务表单；若明确接受复用已暴露调研内容，将降低独立性，不建议|
|Architecture Version|未冻结；正式基线为实施方案 V2.1|
|DB Schema Version|未冻结|
|API Contract Version|未冻结|
|Test Summary|POC-03 137/137 单元测试 PASS；R7.1 严格导入与覆盖 PASS；留出集锁定两种污染口径均失败关闭，调研类可用 0/2；本轮外部 AI 调用 0|
|Next WBS|等待新调研资料到位；随后本地解析、Hash 去重、污染检查并重新生成 50 条来源锁。任何新外发复验仍须当轮明确授权|

## 自动执行策略

- 模式：默认自主执行 + Gate 确认 + 异常升级。
- 周额度停止线：剩余低于 20%。
- 最后额度检查：2026-09-20，周窗口已使用 55%，剩余 45%，重置时间 2026-09-23 17:51:41 +08:00。
- GitHub：允许在当前 Scope 和正确分支内自动 fetch、commit、push；禁止 force push、直接提交 main、覆盖未知远端修改或提交 Secret/客户数据。

## 最近检查点

- 分支：`poc/poc-03-plm-rag`
- 最近功能检查点：R7.1 校准数据集及覆盖审计 PASS。独立留出集已实现确定性来源锁定、历史暴露并集排除、相邻 Source Locator 排除和失败关闭；目标 50 条配额为 33/7/8/2。现有语料的调研类可用量为 0，未生成伪完整来源锁；已建立本地补充资料入口，等待新调研业务表单。
- 远端同步状态必须在每次任务结束前通过 Git 实时检查，不在本文件固化可能过期的 ahead/behind 数值。
- 本地用户文件和 Git 忽略的客户资料保持不变。
