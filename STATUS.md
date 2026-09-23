# 项目状态

|字段|当前值|
|---|---|
|Current Phase|Architecture / Data Model / API Contract Freeze|
|Current WBS|SC-05：DB Schema Candidate 汇总|
|Current Status|ARCHITECTURE_CANDIDATE_V1_COMPLETE / DATA_MODEL_CANDIDATE_V1_COMPLETE / DATABASE_SCHEMA_IN_PROGRESS|
|Completed Phases|Phase 0 技术验证（`COMPLETE_WITH_APPROVED_ALTERNATIVES`）|
|Completed WBS|POC-01、POC-02、POC-04、POC-05、POC-06、POC-08、POC-09 已按验证或批准例外收口；POC-03 以批准替代方案收口；Gate 1 已通过；AF-01～AF-05、DM-01～DM-06、SC-01～SC-04 PASS|
|Blockers|正式业务编码仍由 Gate 2 阻塞；POC-03 质量失败转为 Gate 3/UAT 阻塞项，Server Office 与 Debian 未验证范围转为 Release 约束|
|Pending User Decisions|Architecture、Data Model、DB Schema V1 与 API Contract V1 候选完成后需执行 Gate 2 正式确认；任何新的客户数据外发仍需当轮明确授权|
|Architecture Version|`ARCH-CANDIDATE-V1`；AF-01～AF-05 PASS，待 Gate 2 正式冻结|
|Data Model Version|`DATA-MODEL-CANDIDATE-V1`；DM-01～DM-06 PASS，待 Gate 2 正式冻结|
|DB Schema Version|SC-01～SC-04 PASS；验证性 Migration/恢复已通过，`DB-SCHEMA-CANDIDATE-V1` 待 SC-05 汇总，未冻结|
|API Contract Version|未冻结|
|Test Summary|SC-04 Windows 11：4/4 unit、空库/有数据 up/down、10/10 负向约束、20/20 Worker、GIN/HNSW、Retention/Hold、65 Root 备份恢复和敏感扫描 PASS；性能不作正式声明。Phase 0/POC-03 质量结论保持不变|
|Next WBS|SC-05 汇总 SC-01～SC-04，形成单一 `DB-SCHEMA-CANDIDATE-V1` 与 API Contract 输入|

## 自动执行策略

- 模式：默认自主执行 + Gate 确认 + 异常升级。
- 代决策授权：后续普通业务确认、资料缺口补全、候选项取舍和可回滚方案选择，由 AI 按证据优先、保守默认、最小范围原则直接决定并登记；不再逐项打断用户。该授权不替代正式 Gate、客户数据外发、安全/License、已锁定基线变更、删除 Scope 或不可逆外部操作的专项确认。
- 周额度停止线：剩余低于 20%。
- 最后额度检查：2026-09-23，周窗口已使用 78%，剩余 22%，重置时间 2026-09-23 17:51:41 +08:00；存在 1 次可用 reset credit，但未获逐次授权，未使用。
- GitHub：允许在当前 Scope 和正确分支内自动 fetch、commit、push；禁止 force push、直接提交 main、覆盖未知远端修改或提交 Secret/客户数据。

## 最近检查点

- 分支：`feature/database-schema-v1`
- 最近功能检查点：SC-04 已建立 `VALIDATION_ONLY` Schema Contract 与两级 Alembic Migration，覆盖 65 Root/70 表；Windows 11 空库/有数据 up/down、10 个直接 SQL 负例、4 类索引计划、20 Worker、Retention/Hold、备份恢复和敏感扫描通过。非关键 Root 仍为 Profile 最小列，不能描述为生产 Schema；正式业务编码继续由 Gate 2 阻塞。
- 远端同步状态必须在每次任务结束前通过 Git 实时检查，不在本文件固化可能过期的 ahead/behind 数值。
- 本地用户文件和 Git 忽略的客户资料保持不变。
