# 项目状态

|字段|当前值|
|---|---|
|Current Phase|Architecture / Data Model / API Contract Freeze|
|Current WBS|API-03：AI、RAG、Job、Plugin 与 Output Contract（下一任务）|
|Current Status|ARCHITECTURE_CANDIDATE_V1_COMPLETE / DATA_MODEL_CANDIDATE_V1_COMPLETE / DB_SCHEMA_CANDIDATE_V1_COMPLETE / API_CONTRACT_IN_PROGRESS|
|Completed Phases|Phase 0 技术验证（`COMPLETE_WITH_APPROVED_ALTERNATIVES`）|
|Completed WBS|POC-01、POC-02、POC-04、POC-05、POC-06、POC-08、POC-09 已按验证或批准例外收口；POC-03 以批准替代方案收口；Gate 1 已通过；AF-01～AF-05、DM-01～DM-06、SC-01～SC-05、API-01～API-02 PASS|
|Blockers|正式业务编码仍由 Gate 2 阻塞；POC-03 质量失败转为 Gate 3/UAT 阻塞项，Server Office 与 Debian 未验证范围转为 Release 约束|
|Pending User Decisions|Architecture、Data Model、DB Schema V1 与 API Contract V1 候选完成后需执行 Gate 2 正式确认；任何新的客户数据外发仍需当轮明确授权|
|Architecture Version|`ARCH-CANDIDATE-V1`；AF-01～AF-05 PASS，待 Gate 2 正式冻结|
|Data Model Version|`DATA-MODEL-CANDIDATE-V1`；DM-01～DM-06 PASS，待 Gate 2 正式冻结|
|DB Schema Version|`DB-SCHEMA-CANDIDATE-V1`；SC-01～SC-05 PASS，待 Gate 2 正式冻结；SC-04 Migration 仅为验证性实现|
|API Contract Version|API-01～API-02 PASS；公共协议及平台/安全/文档治理 Contract 已形成，尚未汇总/冻结|
|Test Summary|API-02 一致性：10/10 Owner、22/22 Root、86 个 Operation ID 无重复、42 个错误码无重复、所有受检状态写操作具备 CSRF、12/12 风险、14/14 验收 PASS；既有结论保持不变|
|Next WBS|API-03：细化 AI/RAG/Job/Plugin/Output 的异步、外发授权、状态、取消、SSE、权限和错误码|

## 自动执行策略

- 模式：默认自主执行 + Gate 确认 + 异常升级。
- 代决策授权：后续普通业务确认、资料缺口补全、候选项取舍和可回滚方案选择，由 AI 按证据优先、保守默认、最小范围原则直接决定并登记；不再逐项打断用户。该授权不替代正式 Gate、客户数据外发、安全/License、已锁定基线变更、删除 Scope 或不可逆外部操作的专项确认。
- 周额度规则：用户已于 2026-09-23 取消自动检查和 20% 停止线；后续仅在用户明确要求时查询。额度重置或购买仍需逐次明确确认。
- GitHub：允许在当前 Scope 和正确分支内自动 fetch、commit、push；禁止 force push、直接提交 main、覆盖未知远端修改或提交 Secret/客户数据。

## 最近检查点

- 分支：`feature/api-contract-v1`
- 最近功能检查点：API-02 已为 Platform/Auth/Project/Workflow/Review/Document/Evidence/Trace/Audit/License 的 22 个 Root 定义 86 个 Operation、DTO、权限、42 个错误码、强制 Audit 与测试矩阵；三步流式上传、固定版本 Viewer、Review 锁、最小 License 恢复面和内部 Root 不直出已明确。尚未创建 FastAPI/Pydantic；正式业务编码继续由 Gate 2 阻塞。
- 远端同步状态必须在每次任务结束前通过 Git 实时检查，不在本文件固化可能过期的 ahead/behind 数值。
- 本地用户文件和 Git 忽略的客户资料保持不变。
