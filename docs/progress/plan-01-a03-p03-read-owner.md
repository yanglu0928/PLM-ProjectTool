# PLAN-01-A03-P03：Plan 身份当前授权读取 Owner

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`PLAN_01_A03_P03_READ_OWNER_PG_PASS`；只证明内部当前授权读取，未开放 HTTP/页面。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `PLAN-01-A03-P03`|
|输入基线|冻结 PLAN_LIST/GET、Project member 权限、0167 Plan 身份、P02 内部创建 Owner|
|前置任务|P02 真实 PG/Auth/License/并发/回滚与全量通过；PlanVersion 尚未建立且批准指针由0167强制为空|
|涉及模块/实体|Plan 只读 Application/Repository，Project 当前成员与 Session/License|
|涉及 API/权限|本项仅内部 get/list；四类当前项目成员可读，跨项目/撤权/失效许可拒绝，HTTP仍关闭|
|验收|真实当前行与强 ETag，列表稳定有界，错误/畸形投影关闭、零写 Audit，PG隔离与撤权、全量测试|
|风险|把首次 CREATE 快照作为当前状态、提前展示无版本证明的批准指针、跨项目 ID 探测、缓存授权|

当前批准版本指针在0167约束下只能为空；待 PlanVersion/Review Owner 实装后再增同 Project FK 和受控读取校验，不能凭临时字符串伪造 `APPROVED`。列表/详情不读取 `pln_plan_create_results`，它只供首次 CREATE 重放。

## 实施与验证

- 新增 `PLAN_GET/PLAN_LIST` 当前项目成员只读策略、内部 Service/SQL Repository；真实 `pln_plans` 行提供当前 name/state/强 ETag，按 plan_id 有界 keyset 列表，Project/Session/License 每次重验。当前批准指针必须为空；结果身份、项目、顺序、页边界与安全投影异常均失败关闭，不读取首次创建快照，也不写 Audit。
- Windows 11/可弃 PostgreSQL 18.6 的真实 Session/Project/License 环境中，经理及实施成员读取、两条计划分页、跨项目和未知 ID 隐藏、无效 Session/License 拒绝、成员暂停后立即拒绝、所有读取零新增 Plan Audit 通过；复用上游真实 PG/Auth fixture，退出0。
- 定向策略/读取 `15 passed / 822 subtests`；后端全量 `3794 passed / 3 skipped / 5945 subtests`。开发 wheel 1434 项，含 Plan 读取 Service/Repository，SHA-256 `88c7293cfe2f66669f84f97d64681122f14207e108e352804de50ffa452789fc`；不是 Pilot/Release 包。

## 兼容、升级与遗留

- 无 Migration、公开 API、License、依赖或历史变更；仅当前内部读取和 Project 只读操作策略。可撤内部读取组合且不删除 Plan 历史；冻结 PLAN_LIST/GET 的网络边界仍待单独实现。
- PlanVersion/WBS/正式批准输入、Output、真实服务账户信任、安装/升级与 Gate3/Pilot/发行未通过。当前列表是内部位置分页，公开 cursor 必须另行满足 API-01 的范围/完整性合同。

Next：`PLAN-01-A04-P01` 冻结 PLAN_CREATE HTTP 前置与默认关闭实现。
