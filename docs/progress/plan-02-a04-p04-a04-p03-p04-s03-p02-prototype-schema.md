# PLAN-02-A04-P04-A04-P03-P04-S03-P02：WBS PrototypeVersion 关系 Schema

日期：2026-10-26。结果：`PASS_SCOPE_LIMITED`。按 CR-PLAN-003 增加可证明的 Prototype 固定版本关系；PlanVersion 业务写口仍关闭。

## 编码前检查

|项目|结论|
|---|---|
|Phase / WBS|Phase 2 / `PLAN-02-A04-P04-A04-P03-P04-S03-P02`|
|输入基线|Gate 2冻结DM-05；CR-PLAN-003方案C；CR-PLAN-002；Migration 0186；PrototypeVersion ORM唯一键 `(prototype_version_id, prototype_id, project_id)`|
|前置任务|S03-P01严格内部输入模型完成；审计发现frozen WBS `prototype_refs` 未有Plan关系表，已先登记CR-PLAN-003|
|涉及模块/实体|Plan ORM/Migration与PrototypeVersion固定关系；WbsItem、PlanVersion、Project和PrototypeVersion|
|涉及 API / 权限|无API/权限变化；本片不创建业务行、不开放写入|
|验收标准|在0186后追加复合归属/FK、有序去重表、未安装Owner写保护和历史降级守卫；真实PG升级/降级/重升/drift、完整回归|
|风险|FK仅证明固定Prototype版本身份和Project归属，不能证明Approved/当前指针；未来写Owner必须重新验证Review、当前批准指针和来源资格|

## Changed / Migration

- 新增 ORM `PlanWbsPrototypeRefRow` 与 `pln_item_prototype_refs`：复合WBS owner FK、PrototypeVersion `(prototype_version_id, prototype_id, project_id)` 复合FK、`ordinal>0`、WBS目标去重/顺序唯一约束及项目版本索引。
- 新增 Alembic `20261026_0187`，追加于 `20261026_0186`。新表挂载0186定义的 closed-owner/no-truncate guards；Owner尚未安装，表保持不能写入。表出现任何引用后 downgrade 主动拒绝。
- 没有修改Gate 2冻结提交、外部API、Prototype数据或现有 Plan 业务数据。

## 验收

- 定向 ORM/Migration/输入测试：18 passed。
- Windows 11 临时 PostgreSQL 18.6：升级到0186、升级到0187、降级0186、重升0187；Alembic `command.check` 输出 `No new upgrade operations detected`，结果 `PLAN_SCHEMA_0187_UP_DOWN_REUP_DRIFT_PASS`。
- 后端完整回归：4118 passed、3 skipped、6153 subtests passed。
- drift检查有既存向量表达式索引和computed-default比较告警，但无新增upgrade operations。
- 使用空业务库迁移链；没有植入Plan/WBS/Prototype真实历史行验证跨Project FK负例，也未实测有引用后的downgrade拒绝，故为 `PASS_SCOPE_LIMITED`，不是完整业务数据迁移证明。
- 临时验证目录保留于本机Temp（删除策略拒绝递归删除），临时PostgreSQL已正常停止；不含客户数据。

## Known issues / Next

- 模型/Schema现在可保留Prototype ref，但Plan聚合写Owner仍未接入；未验证Prototype当前Approved指针或Review资格。
- 当前类别、协作角色、Calendar业务白名单及OutputArtifact Owner仍待；非空Output refs继续失败关闭。
- Next：`PLAN-02-A04-P04-A04-P03-P04-S03-P03`，实现完整PlanVersion DRAFT同事务聚合写Owner，覆盖授权/来源锁定或并发复查、Review与Approved版本身份、成员激活、全字段白名单、幂等/Audit、rollback与输出引用失败关闭；真实PG验收后再做HTTP与Windows组合。
- Pilot、Gate 3、正式Release不因Schema完成而改变。
