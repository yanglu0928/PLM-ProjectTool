# PLAN-01-A03-P01：Plan 首次创建结果快照 Schema

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`PLAN_01_A03_P01_CREATE_RESULT_SCHEMA_PASS`；只证明关闭式首次响应快照，不表示 Plan 身份创建已开放。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `PLAN-01-A03-P01`|
|输入基线|PLAN_CREATE/GET/PATCH/ARCHIVE 冻结合同、0167、A03 前置核查及现有 SolutionOutline 首次结果模式|
|前置任务|0167 身份 Schema/ORM 与 PG/全量验证通过；平台通用收据仅持有 ref/status|
|涉及模块/实体|Plan 基础设施、创建结果快照；仅附属 `pln_plan_create_results`|
|涉及 API/权限|无公开 API；快照写入在 P02 Owner 实现前关闭|
|验收|0168/ORM 同步，项目复合 FK、首次名称/时间不可变约束，Win11/PG18.6 空/有数据升降重升、drift、关闭写与历史拒降、定向/全量|
|风险|快照与身份不同项目、重放响应漂移、删除历史后降级、提前开放 SQL 写入|

实现只固化首次 `plan_id/project_id/name/created_at`，初态 `ACTIVE` 与 ETag `"v0"` 在后续服务中按冻结合同构造；不复制后续可变名称/状态。P02 将把身份、快照、Audit、通用收据纳入同一事务，并在重放时复验当前授权。

## 实施与验证

- 新增 `pln_plan_create_results` ORM/顺序 Migration `20261019_0168`，以 `plan_id` 唯一保存首次 name/created_at，通过 `(plan_id,project_id)` 复合 FK 锁定项目归属；名称和时间约束、关闭式 DML/TRUNCATE trigger。有任何快照历史时拒绝降级，不静默删除首次结果。
- Windows 11/可弃 PostgreSQL 18.6 从已有用户/两项目/0167 升至 head，验证 Owner 缺失关闭、跨项目 FK、空白名称、无限时间、同 Plan 重复结果拒绝；合成插入后改变 Plan 名称，快照仍为首次内容，UPDATE/DELETE 拒绝；非空降级拒绝，清空合成行后降回0167再重升，原项目数据保留。两次 Alembic `check` 无漂移，输出 `PLAN_01_A03_P01_CREATE_RESULT_SCHEMA_PASS`、退出0，临时 PG 清理。
- 定向 Schema/Metadata/迁移合同 `11 passed`；后端全量 `3785 passed / 3 skipped / 5924 subtests`。开发 wheel 1428 项，包含 0168 和 Plan ORM，SHA-256 `d1f7a43294a166f4978f9eb3bf5c6a10478c91cf4df9d607576fa5ed96b3ad19`；不是 Pilot/Release 包。

## 兼容、升级与遗留

- 从0167升级只追加关闭式结果表；不改旧行、冻结 API、权限、License 或依赖。升级前按既有流程备份；表为空可降至0167，有结果历史则拒降，应向前修复或人工从备份恢复。不可把禁用 trigger 的测试插入用于生产。
- P02 仍需安装当前授权的 Plan 身份创建 Owner，并把身份/快照/收据/Audit 原子化；P03 当前授权读取、PlanVersion/WBS/Output、正式信任/安装均待。Gate3/Pilot/发行未通过。

Next：`PLAN-01-A03-P02` 内部创建 Owner 与真实 PG 同事务重放/回滚。
