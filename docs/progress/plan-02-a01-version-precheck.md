# PLAN-02-A01：PlanVersion 固定快照与输入前置核查

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`PLAN_02_A01_PRECHECK_PASS`；仅通过实施前核查，不表示正式版本或 WBS 已可用。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `PLAN-02-A01`|
|输入基线|Gate 2 冻结 DM-05、SC-01/02/03、API-04 `PLAN_VERSION_*`，以及 PLAN-01 身份实际实现|
|前置任务|Plan 身份0167～0169、Windows/PG HTTP、前端与 Edge 已通过；Solution Outline/Section 版本可创建/读取，但整体 Approved 输入来源尚未完成|
|涉及模块/实体|plan PlanVersion、WbsItem、FS Dependency、Milestone、固定 Solution/Requirement/Evidence 引用；仅核查，不修改实体|
|涉及 API|冻结 VERSION_LIST/CREATE/GET/WBS_LIST/VALIDATE/COMPARE/SUBMIT_REVIEW；本项不挂载 API|
|涉及权限|当前 Project member 读、ProjectManager/ImplementationMember 创建/验证、仅 ProjectManager 送审；每次重验 Session/Project/License/Subject|
|验收标准|确定 Schema/Owner/HTTP/Review 的安全先后、正式输入阻断及最小独立 WBS；不把合成或专项审批冒充整体批准|
|风险|把动态 latest 当固定输入、未批准 Solution 注入正式 Plan、提前放开 approved pointer、跨项目引用、未验证六级/FS DAG、AI 建议直接转承诺|

## 核查结果

1. `pln_plans` 与创建快照/Owner 已实现，当前批准指针仍由数据库 CHECK 强制为空；仓库暂无 `pln_plan_versions`、WBS、Dependency、Milestone 表/Owner/HTTP。不能仅因 Plan 身份页面通过就宣称实施计划可用。
2. 冻结 `PlanVersionInput` 是已批准 Solution 版本集合 + WBS/FS/Milestone/日历/排除的不可变快照；引用不能动态追随 latest。WBS 深度≤6、父子连续、FS 同版本无环、日期/负责人/进入条件/验收与范围覆盖要在送审前验证。正式批准只由统一 Review 指定版本和受控指针获得。
3. 当前 SOL-06 专项 Review 已接线，但 Outline/Section 的整体 Approved 输入链并未形成。因此 `PLAN_VERSION_CREATE` 和送审不能以专项 APPROVED、合成标志或纯 AI 输出放行。数据库根表可以先作为关闭式基础设施建立，应用写口须等真实 Approved 来源/授权验证；批准指针继续为空。
4. 同项目保护以 `(plan_id, project_id)` 复合 FK 为基础；WBS/依赖/里程碑子表必须固定 PlanVersion、同版本关系与历史不可覆写。不同项目的 Solution/Requirement/Evidence 引用应由各自 Owner 授权核查，不直接跨模块读取内部表作为权限来源。

## 下一切片与验收

|顺序|单一问题|客观验收|
|---|---|---|
|`PLAN-02-A02`|关闭式 PlanVersion 根表/ORM|0169 后顺序 Migration；Project/Plan 复合 FK、版本号/状态/不可变边界、禁止未经 Owner 写入和历史删除、指针仍关闭；Win11/PG18.6 空库与有数据 up/down/re-up、负例、drift、定向与全量|
|`PLAN-02-A03`|WBS/FS/Milestone 与固定引用 Schema|版本内复合 FK、深度/类型/同版本完整性、索引及受控写入；同等 Migration 验收|
|后续独立 WBS|真正 Approved Solution 输入证明、PlanVersion 固定创建/读取/验证/Review/Trace、HTTP/前端/Edge、Output|每步保持当前授权、持久幂等、审计/失败回滚；完整批准链未就绪前不开放业务创建|

本项为静态合同/代码交叉核查，未运行功能测试；不改程序、Migration、冻结 API、角色、License、数据或 Gate。无需 Change Request；若后续出现冻结冲突，先记 CR 再按持续授权实施。
