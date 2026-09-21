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
|Test Summary|POC-03 183/183、POC-04 12/12 单元测试 PASS；第一批最终交付包 R6 整合 40 条需求—方案、21 项专项、10 条正式化待办和 30 个调研主题，6/6 页签渲染/回读、71 个证据链接及公式错误扫描 PASS；独立留出集 50/50 APPROVED、问题 0、Schema PASS、12/12 覆盖与隔离检查 PASS；本轮外部调用 0|
|Next WBS|取得本轮明确数据外发授权后，建立独立检索索引并执行 50 条 Embedding、Reranker、DeepSeek 真实复验；未授权则保持当前安全检查点|

## 自动执行策略

- 模式：默认自主执行 + Gate 确认 + 异常升级。
- 代决策授权：后续普通业务确认、资料缺口补全、候选项取舍和可回滚方案选择，由 AI 按证据优先、保守默认、最小范围原则直接决定并登记；不再逐项打断用户。该授权不替代正式 Gate、客户数据外发、安全/License、已锁定基线变更、删除 Scope 或不可逆外部操作的专项确认。
- 周额度停止线：剩余低于 20%。
- 最后额度检查：2026-09-21，周窗口已使用 65%，剩余 35%，重置时间 2026-09-23 17:51:41 +08:00。
- GitHub：允许在当前 Scope 和正确分支内自动 fetch、commit、push；禁止 force push、直接提交 main、覆盖未知远端修改或提交 Secret/客户数据。

## 最近检查点

- 分支：`poc/poc-03-plm-rag`
- 最近功能检查点：已完成第一批项目需求与解决方案交付包 R6。5 个项目的 40 条内部需求—方案、21 项 InterfaceSpec/MigrationSpec/PermissionDesign、10 条工作基线正式化待办和 30 个推荐调研主题已整合，并按 W0 范围收敛、W1 标准配置、W2 差异治理、W3 非标专项、W4 验收正式化形成实施路线。全部对象保持非正式内部草案，不代表客户确认或正式 Gate 通过；客户名称、正文、工作簿和证据页仍只保存在 Git 忽略目录，本轮外部调用 0，独立留出集真实复验授权 Gate 不变。
- 远端同步状态必须在每次任务结束前通过 Git 实时检查，不在本文件固化可能过期的 ahead/behind 数值。
- 本地用户文件和 Git 忽略的客户资料保持不变。
