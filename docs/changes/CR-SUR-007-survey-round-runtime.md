# CR-SUR-007：Survey Round 运行时与完整性 Owner 分段实施

日期：2026-10-06。状态：依据 `CR-EXEC-001` 持续授权批准实施。Gate 2 原冻结提交 `64cdf09`、SRV-03 Root、两张物理表、四态枚举和七个 Round Operation 均保留；本 CR 不表示任何客户调研已发生、Round 已完成、Workflow Gate、Gate 3 或 UAT 已通过。

## 来源与冲突

冻结基线只规定 `srv_rounds`、`srv_round_source_records`、`PLANNED/OPEN/CLOSED/CANCELLED`、ScheduleMetadata 和七个 Round Operation，没有固定 Schedule 的物理字段、现场记录追加时点或 CLOSE 完整性报告的 Owner。当前运行仓库只实现 SRV-01/SRV-02 六表与定义/Review/读取/来源定位，Alembic head 为 `20261006_0106`；没有 SRV-03 ORM、Migration、Application、HTTP、前端或 Windows 组合。

若在 SRV-04 Assignment/Response 尚不存在时允许 CLOSE，空 Assignment 集会被错误描述为“完整”，原始 PROJECT_RECORD 也会被误当结构化回答。若把面对面记录限制为 Round 创建时一次性提交，实际会议后形成的记录无法纳入；若让 Survey 直接读取 Evidence/Document 私表，又违反模块 Owner 边界。

## 选择

- `srv_rounds` 使用 M-PRJ：固定 `survey_id/survey_version_id/round_no`，状态、可空 UTC 计划起止、可空受控地点说明、生命周期 actor/time、取消原因和强 `lock_version`。Round number 由服务端在 Survey 锁下按 Survey 单调分配。
- 创建时只允许绑定当前 ACTIVE Survey 的当前 `APPROVED` SurveyVersion；Round 一经创建保持固定 Version，即使后续定义升版也不追写历史。PATCH 只修改 PLANNED 的计划元数据。
- `srv_round_source_records` 是 Round-owned 追加记录：固定 PROJECT_RECORD Evidence、Document/DocumentVersion、可空 Question、记录人、序号及观测 fingerprint/版本。只允许受权 Round Owner 在 OPEN 期间追加；不 UPDATE/DELETE。SRV-04 的 `FACILITATED_RECORD` Response 将在同一事务调用该 Owner，不能伪装为客户自填。
- 现场记录证明由 Evidence/Document Owner 提供 caller-transaction Port，必须是同项目、当前 ELIGIBLE、非 TEMPLATE 且 `document_category=PROJECT_RECORD` 的固定 Evidence/DocumentVersion；Survey 不直查跨模块私表。
- 状态严格为 `PLANNED -> OPEN -> CLOSED` 或 `PLANNED -> CANCELLED`。OPEN/CANCEL 只允许 ProjectManager；创建/PATCH 允许 ProjectManager、ImplementationMember；所有 Project member 可读。
- CLOSE 端点和命令可以先保留合同/接口位置，但在 SRV-04 提供真实 Assignment/Response completeness Owner 前不装配成功路径。不得以“尚无 Assignment”、客户端布尔值、原始记录数量或 AI 建议生成 PASS。完成后 CLOSE 在同一事务锁定 Round 与全部当前 Assignment/Response，复算条件、必填、Evidence 和退回状态，持久化结果摘要并原子关闭。

## 实施拆分

1. `SUR-02-A01`：本 CR、冻结基线/现状核查和任务拆分。
2. `SUR-02-A02`：两表 ORM 与 Migration `20261006_0107`；完成 up/down、空库/有数据、drift、生命周期与追加保护。
3. `SUR-02-A03`：Evidence/Document-owned PROJECT_RECORD 固定来源证明和 Round source append Port，不开放 HTTP。
4. `SUR-02-A04`：Round create/list/get 与稳定 cursor；当前 APPROVED Version、授权、Audit、持久幂等和隔离 PostgreSQL 验证。
5. `SUR-02-A05`：PLANNED schedule PATCH、OPEN、CANCEL 状态 Owner；CLOSE 继续显式失败关闭。
6. `SUR-03`：实现 SRV-04 Assignment/Response/Answer/Evidence 与 facilitated record 同事务追加，并提供 Round completeness Owner。
7. `SUR-02-A06`：接通 CLOSE、七个冻结 HTTP、Windows 组合、前端和真实浏览器/PG 闭环。若实施中需要新增冻结请求必填字段或改变状态语义，另走 API Change Request。

## 迁移、兼容、回滚与验证

0107 只新增冻结已有的两张表，不修改 SRV-01/SRV-02、现有 `/api/v1` JSON、角色、依赖或 Scope。空历史可降至0106；有 Round/source/lifecycle/Audit/receipt 历史时拒绝物理降级并向前修复。应用回滚可停止 Router/Owner 注入，但不删除业务历史。

测试必须覆盖：同 Survey round_no 并发分配、跨项目/撤权/归档/License、非当前或非 APPROVED Version、计划字段边界、状态全矩阵、强 ETag、Audit/幂等回滚、PROJECT_RECORD Evidence 的 Scope/类别/eligibility/fingerprint、Question 属于固定 Version、追加记录不可变、CLOSED/CANCELLED 后拒绝追加，以及未注册 completeness Owner 时 CLOSE 失败关闭。Windows 11/PostgreSQL 18.6 为当前实际验证环境；Windows Server 2025 留发行矩阵复验，Debian 13 按用户指令跳过实机但继续保持正式兼容目标。

## 实施记录

- 2026-10-06 / `SUR-02-A02`：完成两表 ORM 与 Migration `20261006_0107`。Schema 验证了当前批准定义边界、Round 状态机、PROJECT_RECORD 固定快照、append-only 与历史拒降；应用 CLOSE 仍失败关闭。Windows 11/PostgreSQL 18.6 真库、后端全量和开发 wheel 均通过，详见 `docs/progress/sur-02-a02-round-schema.md`。
