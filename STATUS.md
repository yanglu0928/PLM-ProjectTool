# 项目状态

|字段|当前值|
|---|---|
|Current Phase|Phase 0 技术验证|
|Current WBS|P03-A12-R6：独立留出集问题、分类与引用建议准备|
|Current Status|WAITING_HUMAN_CONFIRMATION / HOLDOUT_REVIEW_R1|
|Completed Phases|无|
|Completed WBS|POC-01、POC-02、POC-04 已按批准例外收口；P03-A02~A11、P03-A14、P03-A15 已 PASS|
|Blockers|50 条 DeepSeek AI 建议和友好确认表已生成，但 AI 建议不得直接成为正式真值；必须先完成人工批量确认或单条例外处理|
|Pending User Decisions|打开本地确认表，在 B5 选择“确认全部AI建议”，填写审核人和日期；仅对不适用条目选择“修改后确认”或“退回”并填写黄色字段|
|Architecture Version|未冻结；正式基线为实施方案 V2.1|
|DB Schema Version|未冻结|
|API Contract Version|未冻结|
|Test Summary|POC-03 146/146、POC-04 12/12 单元测试 PASS；DeepSeek 建议 50/50、问题唯一 50/50、五类全覆盖；原文定位 50/50；工作簿 3/3 表渲染、公式错误 0、批量确认与单条修改回归 PASS；Embedding/Reranker 调用 0|
|Next WBS|等待人工确认；随后严格导入独立留出集、执行 Schema/覆盖审计。最终 DeepSeek 质量复验属于新的数据外发范围，届时须再次取得明确授权|

## 自动执行策略

- 模式：默认自主执行 + Gate 确认 + 异常升级。
- 周额度停止线：剩余低于 20%。
- 最后额度检查：2026-09-20，周窗口已使用 58%，剩余 42%，重置时间 2026-09-23 17:51:41 +08:00。
- GitHub：允许在当前 Scope 和正确分支内自动 fetch、commit、push；禁止 force push、直接提交 main、覆盖未知远端修改或提交 Secret/客户数据。

## 最近检查点

- 分支：`poc/poc-03-plm-rag`
- 最近功能检查点：50 条独立来源锁已生成 DeepSeek AI 预填建议，分类分布为标准满足 23、部分满足 3、非标准 10、资料不足 13、无可靠匹配 1；问题 50/50 唯一。DeepSeek V4 默认思考模式会耗尽结构化输出预算，统一 AIService 已增加显式 `thinking="disabled"`；50 条建议均通过非思考模式受约束恢复，9 条同义改写摘录和 9 条关键词由本地确定性原文片段替换。评审工作簿已生成，等待人工确认。
- 远端同步状态必须在每次任务结束前通过 Git 实时检查，不在本文件固化可能过期的 ahead/behind 数值。
- 本地用户文件和 Git 忽略的客户资料保持不变。
