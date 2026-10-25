# PLAN-01-A03：Plan 身份 Owner 前置核查

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`PLAN_01_A03_PRECONDITION_BLOCKED`；A03 的创建/读取 Owner 尚不能直接编码，先补首次响应快照持久层。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `PLAN-01-A03`|
|输入基线|冻结 PLAN_CREATE/GET、API-01 持久幂等、PLAN-01-A02 0167、现有 SolutionOutline 创建 Owner/平台通用收据|
|前置任务|0167 Plan 身份闭锁表通过；创建服务的不可变首次响应来源缺失，前置未满足|
|涉及模块/实体|plan、project、auth/license、platform receipt、audit；Plan 与创建结果快照|
|涉及 API/权限|本项仍为内部 Owner；后续冻结 PLAN_CREATE 只允许 ProjectManager/ImplementationMember，读取按当前成员授权|
|验收|同 Key 重放仍返回首次 201 内容、修改名称/归档后不漂移，当前权限复验，写入/快照/收据/Audit 同事务|
|风险|通用收据仅保存操作/对象 ID/status；若直接回读可变 `pln_plans`，未来 PATCH/ARCHIVE 后重放不再是首次结果|

## 证据与拆分

现有 `OutlineCreateService` 在同一事务写逻辑身份、独立 `SolutionOutlineCreateResultRow`、Audit 和通用收据；重放从不可变结果表读首次响应。Plan 冻结合同同时含 CREATE、PATCH 和 ARCHIVE；0167 仅有 `pln_plans`，通用收据不能单独重建首次名称/时间。直接实施原 A03 会破坏冻结幂等语义。

依同形已验证模式，将原 A03 分成：`PLAN-01-A03-P01` 增加关闭式 Plan 首次创建结果快照 Schema/ORM及真实 PG 升降验证；`P02` 再实现当前 Session/Project/License 授权、同事务创建/快照/收据/Audit 的内部 Owner；`P03` 独立实现当前授权读取 Owner。后续 HTTP/Windows/UI 仍分项。此为实现依赖细化，无冻结 API/实体语义或 Scope 变更；若后续发生不兼容再建立正式 CR。

当前未编写 A03 Owner、未开放 API、未运行功能测试；Gate 3/Pilot/发行不变。
