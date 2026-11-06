# CR-EXEC-040：OUT-01-A01-P41 PlanVersion 固定来源接入

日期：2026-11-07  
状态：编码前记录；实施与 Hosted 验证待进行。

## 当前阶段与 WBS

Phase 2 Platform Core / Windows 11 Pilot 纵向业务链。WBS：OUT-01-A01-P41。

## 输入基线与前置

基线：冻结 Architecture、Data Model、DB Schema V1、API Contract V1；CR-EXEC-002 优先 Pilot 顺序；Output 固定来源解析器及 OUT-01-A01-P04 Registry precheck。现有 Requirement Owner 的 Output 来源投影模式作为实现参考。SUR-07-A08 Hosted Windows Server 2025 initdb 阻塞独立保留，A08 不通过，不作为此 WBS 前置。

## 编码前检查

- 问题：Output Resolver 目前仅接入 Requirement Owner 的固定版本来源；冻结 PlanVersion 已保存完整 WBS/依赖/里程碑快照，但当前 Output 模板与策略目录仅登记 Requirement 来源，导致已批准纵向链中的计划成果无法作为明确版本的 Output 输入。
- 涉及模块：Plan（只读授权投影 Owner）、Output（来源适配器及新不可变模板/策略版本）、Windows Output Create Composition、相应测试。
- 涉及实体：既有 Plan、PlanVersion、WBS 快照；不新增 ORM 或数据库实体。
- 涉及 API：不新增、不改变任何 API Contract；使用现有 Output Create source_version_refs。
- 涉及权限：由 Plan Owner 在 Output 创建事务中，使用 actor_id/project_id 对精确版本调用冻结 PLAN_VERSION_GET 授权；跨项目/不存在统一不可见。仅接受 APPROVED 的 PlanVersion；绝不解析 current/latest。
- 投影边界：只选择模板/策略明确列出的不可变 JSON 安全字段；不输出 session、凭据、内部 ORM、跨项目关联或自由扩展内容。
- 验收：Owner 单测覆盖精确版本/项目隔离/未授权/状态拒绝；Output resolver 测试覆盖模板和策略版本保留、字段白名单和错误关闭；Hosted PG18 合成集成与后端全量测试通过。签名 Publisher 信任缺失时，Plugin Operation 继续拒绝，Output 不生成文件。
- 风险：Plan 引用目前仅传 PlanVersion UUID，Owner Repository 必须通过 project-scoped 精确版本查询派生所属 plan_id 后重用现有 snapshot reconstruction；若实现必须更改冻结合同或猜测“当前计划”，立即停止 P41，记录阻塞并转独立任务。
- 回滚：删除新增 adapter、Plan Output projection、内置模板/策略新增版本与测试；原 Requirement 版本与既有行为保持不变，无 Migration 回滚。
- 数据：仅 Hosted 合成数据；不外发客户数据；本机/C 盘不运行。

## 方案决策

选择在 Plan Owner 增加事务内 Output 专用只读 Projection（与 Requirement Owner 的现有调用约定对齐），Repository 对 project_id + 精确 PlanVersion UUID 查询，并从该版本所属 Plan 派生 plan_id 后重用现有 snapshot reconstruction。Output 追加新的不可变模板/策略引用，保留旧版本引用与内容。由 Hosted CI 验收，适用于当前批准 Scope；不宣称信任源、Pilot 或 Gate 已通过。

## 验证与风险关闭条件

实施后先运行 Owner/Resolver 定向测试，再由 GitHub Hosted CI 执行后端完整套件、PG18 集成和包组合检查。若权限隔离、审阅状态或精确引用任一失败，修复后复验，不降验收要求。Secret scan 必须无命中；提交前检查远端 head，并仅以 expected-SHA 快进更新当前 feature 分支。
