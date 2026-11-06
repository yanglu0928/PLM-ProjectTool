# CR-EXEC-040：OUT-01-A01-P41 PlanVersion 固定来源接入

日期：2026-11-07  
状态：PASS_SCOPE_LIMITED；代码、Owner/Resolver验证和真实 PostgreSQL 18 project-scoped lookup 均通过。完整Output写入/插件执行仍不在本WBS，正式插件信任仍失败关闭。

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

## 实施记录（Hosted 验收待完成）

- Plan Owner 新增事务内授权的精确 PlanVersion Output projection 与 project-scoped Repository 读取，重用既有固定版本快照重建逻辑；没有读取 current/latest。
- Output 新增 PlanVersion 来源分发适配器、独立不可变 DOCX 模板/策略版本和 Windows Composition 接线，原 Requirement 版本及其 policy/template refs 保留。
- 策略仅允许 APPROVED，字段限于 version_no、wbs_items、dependencies、milestones、exclusions；Plugin Operation 仍需已启用且可信的签名能力，信任源缺失时仍失败关闭。
- 增加服务授权/项目边界、Composite Adapter 歧义拒绝、固定 Registry 兼容、Resolver 字段白名单及 DRAFT 拒绝的测试。测试只提交，未在本机执行。
- 为真实 PG18 Owner lookup 增加独立 disposable DB 验收器，覆盖指定 PlanVersion UUID 的 project-scoped lookup、Owner 事务授权和跨项目 miss；嵌入父包 PG18 Hosted smoke。仅查询真实 PostgreSQL，快照构造用隔离 fixture，不涉及正式数据。待 Hosted run。

## 方案决策

选择在 Plan Owner 增加事务内 Output 专用只读 Projection（与 Requirement Owner 的现有调用约定对齐），Repository 对 project_id + 精确 PlanVersion UUID 查询，并从该版本所属 Plan 派生 plan_id 后重用现有 snapshot reconstruction。Output 追加新的不可变模板/策略引用，保留旧版本引用与内容。由 Hosted CI 验收，适用于当前批准 Scope；不宣称信任源、Pilot 或 Gate 已通过。

## 验证与风险关闭条件

实施后先运行 Owner/Resolver 定向测试，再由 GitHub Hosted CI 执行后端完整套件、PG18 集成和包组合检查。若权限隔离、审阅状态或精确引用任一失败，修复后复验，不降验收要求。Secret scan 必须无命中；提交前检查远端 head，并仅以 expected-SHA 快进更新当前 feature 分支。


## Hosted 验收结果

run [42295334125](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42295334125)：后端全量测试与 wheel、Windows Server 2025 父包 PG18 smoke 成功；PG18 smoke 中新增 P41 verifier 成功执行真实 project-scoped PlanVersion UUID 查询，并确认 Owner 派生出的 plan_id 与固定版本一致、同版本跨项目不可见。Plan Owner snapshot reconstruction 在该小型隔离探针中由受控 fixture 替代，因此不宣称完整业务行重建/Output生成已通过。A17/A34/P24/P25/P39/P40/A50与前后端及构建作业成功；整轮仅A08 failure，不能算全绿。P41 仅记 PASS_SCOPE_LIMITED。

该结果不代表 Windows 11 实机、正式 Publisher/License 信任、真实插件执行、Pilot、Gate 或正式 Release。Output 在无正式签名信任时仍 fail-closed。
