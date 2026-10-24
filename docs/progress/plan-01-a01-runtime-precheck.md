# PLAN-01-A01：Plan/WBS 正式实现前置核查

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`PLAN_01_A01_PRECHECK_PASS`；仅说明冻结合同与实现依赖，不表示 Plan/WBS 已可用。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `PLAN-01-A01`|
|输入基线|Gate 2 冻结模块边界、DM-05 `PLN-01/02/03`、SC-01/02、API-04 `PLAN_*`、API-03 Output、CR-EXEC-002|
|前置任务|Project/Session/Review/Trace 平台及 Solution 已有分项；Gate 2 通过，Plan 编码可开始，完整正式 Plan 送审仍受批准输入与 Owner 限制|
|涉及模块/实体|plan，及只读 project/solution/review/trace/audit 接口；Plan、PlanVersion、WbsItem、Dependency、Milestone|
|涉及 API/权限|冻结 PLAN_LIST/CREATE/GET/PATCH/ARCHIVE、VERSION_LIST/CREATE/GET/WBS_LIST/VALIDATE/COMPARE/SUBMIT_REVIEW；ProjectManager/ImplementationMember 写，当前成员读，送审仅 ProjectManager|
|验收|找到实际缺口、固定每个分片的前置/验收和边界；不放宽六级、FS DAG、批准方案固定版本及人工确认|
|风险|用 SOL-06 单项审批代替整体方案、AI 建议直接写正式计划、动态 latest 引用、过早接送审、缺当前成员/License/审计和持久幂等|

## 差距与边界

1. 冻结 SC-01 明确 `pln_plans`、`pln_plan_versions`、`pln_wbs_items`、`pln_wbs_dependencies`、`pln_milestones` 及固定业务/证据引用；当前仓库没有 `modules/plan`、前端 Plan 目录或任何 `pln_*` Migration。Schema、Owner、HTTP、UI、真实 PG/Edge 均待实施。
2. `PLAN_VERSION_CREATE` 只接受当前有权项目内已批准 Solution Outline/Section/StructuredSpec 的固定版本集合；ReferencePlan 是参考，不形成项目承诺。现有 SOL-06 专项已有 Review 闭环，但 Outline/Section 送审与批准尚未实现。可独立实现 Plan 身份和 Draft 保存基础设施，正式 PlanVersion 输入与送审必须等真实批准来源，不用合成批准冒充生产事实。
3. `PlanVersion` 是不可变快照；WBS 至多六级、父子 level 连续、仅 FS 依赖且无环，日期/工期、负责人、进入条件、验收、Requirement/Solution 覆盖或显式排除均为验证门槛。AI 的 PLAN_GENERATE 只能建议 Draft，正式事实仍由业务 Owner/人工确认。
4. 复用统一 Review、Trace、Evidence、Audit、Job/AI 服务边界，Plan 不新增平行审批表、不直接读取其他模块表或调用厂商 SDK；当前 Project/Subject 权限要在读写/送审时重新验证。
5. 本项无冻结合同冲突，暂不新增 CR。若后续实现必须偏离字段/状态、冻结 `/api/v1` 或安全边界，应先建立独立 CR，记录影响、迁移/回滚和验证；不能借 Pilot 加速静默改写。

## 可执行分片

|顺序|单一问题|客观验收|
|---|---|---|
|`PLAN-01-A02`|Plan 逻辑身份 Schema/ORM|追加 Migration 0167，空库与有数据 up/down/re-up、约束/指针边界/drift、定向和全量测试；不提前开放 API|
|`PLAN-01-A03`|Plan 身份内部创建/读取 Owner|真实 PG 项目隔离、成员/License、名称约束和 Audit/失败回滚；不创建版本|
|后续独立 WBS|Plan 身份冻结 HTTP/Windows/前端；随后 PlanVersion/WBS/FS/Milestone Schema 与固定输入、验证、Review/Trace、AI 建议、输出桥|每项分开编码前检查、迁移/合同/权限测试，里程碑前真实 Edge/PG 完整链|

PLAN-01-A02 仅具备设计/数据库前置，不等于整个 Plan 可送审；Outline/Section 批准链、正式信任、Output 和 Pilot UAT 仍为独立阻断。当前仅静态阅读冻结基线与仓库代码，不运行功能测试，不改变程序、API、Migration、用户数据或 Gate。
