# PLAN-01-A02：Plan 逻辑身份 Schema

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`PLAN_01_A02_IDENTITY_SCHEMA_PASS`；只证明逻辑身份闭锁 Schema，不表示 Plan/WBS 已可用。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `PLAN-01-A02`|
|输入基线|Gate 2 冻结 PLN-01、SC-01/02、API-04；PLAN-01-A01 前置核查|
|前置任务|Plan/Output 模块缺失已实查，Gate 2 批准；本项只建立逻辑身份，不要求已批准 Solution 输入|
|涉及模块/实体|plan.infrastructure ORM、Alembic；仅 `pln_plans`|
|涉及 API|无公开 API 或运行组合变化|
|涉及权限|Schema 所有 DML 在 Owner 装入前关闭；项目/创建人 FK 约束，不能以 DB 行代表已授权事实|
|验收标准|0167 顺序迁移、ORM/drift、一致约束；Win11/PG18.6 空库/有既有数据 up/down/re-up、跨项目/名称/指针/Owner/历史拒绝；定向及全量后端测试|
|风险|未有 PlanVersion 表，approved pointer 不能悬空；Migration 降级误删历史；测试插入被误当正式计划|

设计：`current_approved_version_ref` 暂存 nullable 列，但 0167 约束它始终为 NULL；后续 PlanVersion Migration 须在建立同 Project 复合 FK 与统一 Review 终态窄门后才可放开非空。Plan 身份 `ACTIVE/ARCHIVED` 与 Solution 身份同形，创建/修改必须等 A03 Owner，以关闭式 trigger 拒绝 DML 与 TRUNCATE。此处不实施版本、WBS、批准指针更新或用户界面。

## 结果与验证

- 新增 `pln_plans` ORM 与顺序 Migration `20261019_0167`：Project/创建人 FK、同 Project 复合身份键、名称/状态/lock 约束、批准指针关闭约束及 Project/state 索引。Owner 安装前触发器拒绝 INSERT/UPDATE/DELETE，历史 TRUNCATE 拒绝；有 Plan 行时降级拒绝，不能静默抹除历史。
- Windows 11/可弃 PostgreSQL 18.6 从 0166 既有用户/两个项目升级至 head，验证数据保留、Owner关闭、无效 Project/创建人、名称/状态/指针/锁拒绝；非空 Plan 降级拒绝、清空合成 Plan 后降至 0166 并重升，原项目行仍在；两次 Alembic `check` 无漂移。验收输出 `PLAN_01_A02_IDENTITY_SCHEMA_PASS`，进程退出 0，临时集群停止清理。
- 定向 Schema/Metadata/Migration 合同 `9 passed`。第一次全量因固定头断言仍为 0166，得到 `1 failed / 3782 passed / 3 skipped`；更新断言至 0167 后重跑全量 `3783 passed / 3 skipped / 5924 subtests`。开发 wheel 1427 项，包含新 ORM 和 0167 Migration，SHA-256 `be4b6859827316bc4aef301e7328c61e4c731c7fe28be949f6b99eda6485e1bd`；该 wheel 不是 Pilot/Release 包。

## 兼容、升级与遗留

- 从 0166 正向升级只增关闭式 Plan 身份表，不改旧数据/冻结 API/角色/License/依赖。执行正式升级前仍须按既有流程备份；Plan 身份为空可降回 0166，有历史则拒绝降级，应向前修复或人工从备份恢复。无自动数据清理。
- A03 需安装真正 Project/Session/License 授权的身份 Owner 与同事务 Audit/收据；不能通过移除触发器直接开放应用写入。PlanVersion/WBS、批准 Solution 输入、Review/Trace、前端/Output 及正式信任/安装仍未完成。Gate 3、Pilot、发行维持未通过。

Next：`PLAN-01-A03` Plan 逻辑身份内部创建/读取 Owner。
