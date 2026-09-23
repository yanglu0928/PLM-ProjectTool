# 项目状态

|字段|当前值|
|---|---|
|Current Phase|Architecture / Data Model / API Contract Freeze|
|Current WBS|SC-01：逻辑到物理 Schema 映射（待执行）|
|Current Status|ARCHITECTURE_CANDIDATE_V1_COMPLETE / DATA_MODEL_CANDIDATE_V1_COMPLETE / DATABASE_SCHEMA_NEXT|
|Completed Phases|Phase 0 技术验证（`COMPLETE_WITH_APPROVED_ALTERNATIVES`）|
|Completed WBS|POC-01、POC-02、POC-04、POC-05、POC-06、POC-08、POC-09 已按验证或批准例外收口；POC-03 以批准替代方案收口；Gate 1 已通过；AF-01～AF-05、DM-01～DM-06 PASS|
|Blockers|正式业务编码仍由 Gate 2 阻塞；POC-03 质量失败转为 Gate 3/UAT 阻塞项，Server Office 与 Debian 未验证范围转为 Release 约束|
|Pending User Decisions|Architecture、Data Model、DB Schema V1 与 API Contract V1 候选完成后需执行 Gate 2 正式确认；任何新的客户数据外发仍需当轮明确授权|
|Architecture Version|`ARCH-CANDIDATE-V1`；AF-01～AF-05 PASS，待 Gate 2 正式冻结|
|Data Model Version|`DATA-MODEL-CANDIDATE-V1`；DM-01～DM-06 PASS，待 Gate 2 正式冻结|
|DB Schema Version|未冻结；SC-01 NEXT|
|API Contract Version|未冻结|
|Test Summary|Phase 0 证据已汇总；POC-03 Top-5 98.00% PASS、分类 48.00% FAIL、引用 74.00% FAIL；POC-06 Windows 11 Office PASS、Server 包结构/Hash PASS；其余 PoC 详见 `docs/progress/phase-0-summary.md`|
|Next WBS|SC-01 将 65 个客户运行 Aggregate Root 映射为 PostgreSQL 18 物理 Schema，并建立命名、Scope/ProjectId 和版本约束基线|

## 自动执行策略

- 模式：默认自主执行 + Gate 确认 + 异常升级。
- 代决策授权：后续普通业务确认、资料缺口补全、候选项取舍和可回滚方案选择，由 AI 按证据优先、保守默认、最小范围原则直接决定并登记；不再逐项打断用户。该授权不替代正式 Gate、客户数据外发、安全/License、已锁定基线变更、删除 Scope 或不可逆外部操作的专项确认。
- 周额度停止线：剩余低于 20%。
- 最后额度检查：2026-09-23，周窗口已使用 77%，剩余 23%，重置时间 2026-09-23 17:51:41 +08:00；存在 1 次可用 reset credit，但未获逐次授权，未使用。
- GitHub：允许在当前 Scope 和正确分支内自动 fetch、commit、push；禁止 force push、直接提交 main、覆盖未知远端修改或提交 Secret/客户数据。

## 最近检查点

- 分支：`feature/data-model-freeze`
- 最近功能检查点：DM-06 已汇总 `DATA-MODEL-CANDIDATE-V1`：22 个模块、65 个客户 Root、3 个隔离 Developer Workbench Root、统一 Scope/关系/生命周期、9 类候选保留策略、25 条完整性不变量、14 项风险和 Schema V1 交接清单；正式业务编码继续由 Gate 2 阻塞。
- 远端同步状态必须在每次任务结束前通过 Git 实时检查，不在本文件固化可能过期的 ahead/behind 数值。
- 本地用户文件和 Git 忽略的客户资料保持不变。
