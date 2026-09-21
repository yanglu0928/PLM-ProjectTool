# 项目状态

|字段|当前值|
|---|---|
|Current Phase|Phase 0 技术验证|
|Current WBS|P03-A11~A13-R8：独立留出集真实质量复验|
|Current Status|WAITING_USER_AUTHORIZATION / HOLDOUT_LIVE_DATA_EGRESS|
|Completed Phases|无|
|Completed WBS|POC-01、POC-02、POC-04 已按批准例外收口；P03-A02~A11、P03-A12-R7、P03-A14、P03-A15 已 PASS|
|Blockers|独立留出集 50/50 已严格导入，Schema 与覆盖审计 PASS；真实质量复验需将独立问题、候选片段发送至百炼 Embedding/Reranker 与 DeepSeek，属于新的数据外发范围|
|Pending User Decisions|明确授权或拒绝本轮独立留出集真实质量复验的数据外发范围；未获授权前不调用任何外部模型|
|Architecture Version|未冻结；正式基线为实施方案 V2.1|
|DB Schema Version|未冻结|
|API Contract Version|未冻结|
|Test Summary|POC-03 165/165、POC-04 12/12 单元测试 PASS；第一批桌面调研 R3 形成 25 条结论和 40 条需求候选，5/5 页签渲染/回读/公式/交互验证 PASS；独立留出集 50/50 APPROVED、问题 0、Schema PASS、12/12 覆盖与隔离检查 PASS；本轮外部调用 0|
|Next WBS|取得本轮明确数据外发授权后，建立独立检索索引并执行 50 条 Embedding、Reranker、DeepSeek 真实复验；未授权则保持当前安全检查点|

## 自动执行策略

- 模式：默认自主执行 + Gate 确认 + 异常升级。
- 周额度停止线：剩余低于 20%。
- 最后额度检查：2026-09-21，周窗口已使用 63%，剩余 37%，重置时间 2026-09-23 17:51:41 +08:00。
- GitHub：允许在当前 Scope 和正确分支内自动 fetch、commit、push；禁止 force push、直接提交 main、覆盖未知远端修改或提交 Secret/客户数据。

## 最近检查点

- 分支：`poc/poc-03-plm-rag`
- 最近功能检查点：因无法安排第一批现场调研，已将第 1 批 5 个项目转换为有证据等级和局限说明的桌面调研，形成 25 条调研结论、40 条需求候选和 10 条未关闭前置假设；29 条可进入需求评审、1 条带工作假设、10 条受前置决策阻塞。未把资料推断写成客户已确认事实，也未进入正式需求冻结；客户名称、原文、工作簿和证据页仍只保存在 Git 忽略目录，本轮外部调用 0，当前独立留出集真实复验授权 Gate 不变。
- 远端同步状态必须在每次任务结束前通过 Git 实时检查，不在本文件固化可能过期的 ahead/behind 数值。
- 本地用户文件和 Git 忽略的客户资料保持不变。
