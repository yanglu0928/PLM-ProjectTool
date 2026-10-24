# PLAN-01-A03-P02：Plan 身份内部创建 Owner

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`PLAN_01_A03_P02_CREATE_OWNER_PG_PASS`；仅内部创建 Owner，冻结 PLAN_CREATE HTTP/Windows/UI 尚未开放。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `PLAN-01-A03-P02`|
|输入基线|冻结 PLAN_CREATE、Project 授权、通用持久幂等/Audit；0167/0168 关闭式身份和首次响应表|
|前置任务|P01 快照/PG/全量通过；当前无 Plan Owner，写入 trigger 必须只为原子首次创建开窄门|
|涉及模块/实体|plan identity、Project/Auth/License、Audit、通用收据；不创建 PlanVersion/WBS|
|涉及 API/权限|无公开 HTTP；`PLAN_CREATE` 仅当前 ProjectManager/ImplementationMember，Session/CSRF、License、归档项目均失败关闭|
|验收|初态/快照同事务闭合、同 Key 首次201重放且当前授权复验、碰撞拒绝、Audit/收据原子性、双并发、跨项目/失效License、PG降级拒绝、全量/wheel|
|风险|SQL直接插入绕过快照、变名后重放漂移、审计失败残留、写入时读取旧授权或提前开放冻结 HTTP|

实现采用当前 SolutionOutline 已验证的原子模式；0169 仅把 Plan/首次结果 INSERT 窄门开放，UPDATE/DELETE/未成对提交继续拒绝。没有正式 API 或 Windows 组合，不能声称页面可创建 Plan。

## 实施与验证

- `20261019_0169` 将 Plan 身份/首次结果只开放初态匹配的 INSERT，延期约束触发器要求同事务匹配快照；UPDATE/DELETE/TRUNCATE 和不成对 Plan 仍拒绝。有历史行时拒绝 Owner 降级；无历史可关回 0168。
- 内部 `PlanCreateService` 使用真实 Session/CSRF、License、当前 Project `PLAN_CREATE` 策略，ProjectManager/ImplementationMember 可创建，其他角色/项目失败关闭；规范名称后按 actor/project/operation/key 锁定通用持久收据。新建将 Plan、首次响应、Audit 和收据同事务提交，同 Key 从不可变快照重放并复验当前权限/License，不采纳 AI 建议为正式事实。
- Windows 11/可弃 PostgreSQL 18.6：真实 Project/Auth、跨项目/失效 License、经理与实施成员创建、同 Key 重放/碰撞、两个并发调用一致、Audit 故障全回滚、直接 SQL 非法初态/缺快照/修改删除/历史拒降均通过；将当前 Plan 名称作合成变更后原 Key 返回首次响应。首次验收脚本把父表 TRUNCATE 预期写为 trigger 文案，但 PostgreSQL 先由子表外键拒绝；调整为直接验证子表历史 trigger 后完整重跑退出0。Alembic `check` 无漂移。
- 定向服务/策略/迁移 `18 passed / 822 subtests`；后端全量 `3789 passed / 3 skipped / 5937 subtests`。开发 wheel 1432 项，包含 0169、Plan Service/Repository，SHA-256 `cc0e05bf7750d30b18c65247b915bb8de24d846359fbc702f3fb11936638788a`；不是 Pilot/Release 包。

## 兼容、升级与遗留

- 从 0168 升级只放开受约束的首次创建行，不改冻结 URL/DTO、角色集合、License/依赖或旧行；新 `PLAN_CREATE` 是冻结路径预备的内部能力，尚未对 HTTP 开放。升级前备份；有 Plan 历史不可降回关闭 Owner/0168，应向前修复或人工从备份恢复。
- P03 当前授权 Plan 读取 Owner、后续 HTTP/Windows/UI、PlanVersion/WBS、正式批准 Solution 输入、Output 和正式信任/安装均待。Gate3/Pilot/发行未通过。

Next：`PLAN-01-A03-P03` 当前授权的 Plan 身份内部读取 Owner。
