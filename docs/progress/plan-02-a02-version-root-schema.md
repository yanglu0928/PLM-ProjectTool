# PLAN-02-A02：关闭式 PlanVersion 根表

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`PLAN_02_A02_VERSION_ROOT_SCHEMA_PASS`，仅关闭式数据库基础。

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `PLAN-02-A02`|
|输入基线|Gate 2 冻结 PLN-02、SC-01/02、API-04；PLAN-02-A01 前置核查|
|前置任务|Plan 身份/Owner 至0169；整体 Approved Solution 输入尚未形成，故仅建关闭式根表|
|涉及模块/实体|plan.infrastructure ORM、Alembic；仅 `pln_plan_versions` 和 Plan 当前批准指针的同项目 FK|
|涉及 API/权限|无公开 API/Owner/角色装配变化；新版本表所有 DML/TRUNCATE 拒绝；旧 Plan 指针继续只允许空|
|验收标准|顺序迁移、ORM/drift、项目/Plan/版本/状态约束、关闭写、历史拒降；Win11/PG18.6 空库和有数据 up/down/re-up，定向/全量测试|
|风险|迁移误改已有 Plan、跨项目/悬空指针、提前容许未批准版本、自动降级擦除历史|

范围仅限版本根身份与版本序列、Review 预留引用；WBS/固定输入、Owner、实际写入及状态转换由后续单独 WBS 实现。版本根表本项不能产生正式业务版本，批准指针约束不放开。

## 结果与验收

- 顺序 Migration `20261019_0170` 和 ORM 增加项目内 PlanVersion 身份、Plan+Project 复合 FK、同 Plan 版本号唯一、前驱同 Plan 约束及受控 Review 引用；Plan 的批准指针新增同 Plan/Project 复合 FK，但既有 `IS NULL` CHECK 不放开。版本根表 DML 被关闭式 Owner 触发器拒绝，历史 TRUNCATE 与带数据降级受保护。`use_alter` 仅解决 ORM 循环外键排序，不改变数据库约束。
- Windows 11/可弃 PostgreSQL 18.6：空库先升至0170、检查并降至0169，再建立已有 Plan 行升至0170且保持不变；空版本表写入拒绝、同项目/版本号/版本正数负例、批准指针仍闭锁；有版本历史拒降，清除合成版本后降至0169并重升，原 Plan 保留；三次 Alembic drift 检查无新增升级。`PLAN_02_A02_VERSION_ROOT_SCHEMA_PASS`，进程退出0并清理临时实例。单表 TRUNCATE 先被循环 FK 拒绝，验收还核对保护触发器确实存在。
- 定向 8 项通过。首次全量仅因 ORM 表固定清单遗漏新表失败（`3810 passed / 1 failed / 3 skipped`），补清单后最终全量 `3811 passed / 3 skipped / 5991 subtests`。尝试开发 wheel 校验时终端安全策略拒绝命令，未获得 wheel 验收证据；本项不称包可交付。

## 兼容、升级与遗留

从0169仅增关闭式版本根表和空批准指针同项目 FK，不改现有 Plan、冻结 API、角色、License、依赖或正式版本内容。升级前备份；版本表无历史可降回0169，有历史拒降，须向前修复或由人工使用备份恢复。WBS/FS/Milestone、固定 Approved Solution 输入、PlanVersion Owner/HTTP/UI/Review/Trace/Output、正式信任/安装和 Gate3/Pilot/发行均未通过。
