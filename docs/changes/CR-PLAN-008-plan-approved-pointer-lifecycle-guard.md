# CR-PLAN-008：Plan Approved Version 指针生命周期守卫

- 日期：2026-10-26
- 状态：`AUTHORIZED_FOR_IMPLEMENTATION_BY_CONTINUOUS_USER_AUTHORIZATION`
- 当前WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06`编码前核查；实现拆分为`...-P05-P06-P01`。
- 基线：Gate 2冻结Data Model/DB Schema/API（原提交`64cdf09`）；后续CR-PLAN-007追加Migration `20261026_0190`。

## 差异与影响

冻结Plan实体具有`current_approved_version_ref`及Review批准流程，但Migration `20261019_0167`创建`ck_pln_plans__approved_pointer_closed`并令`guard_plan_identity_foundation`对所有INSERT/UPDATE/DELETE失败关闭；因此当前Plan不能创建或更新身份数据（既有Owner已另行接通创建），更不能在PlanVersion获Review批准时更新批准指针。ORM仍声明该指针必须为NULL。0190虽允许PlanVersion经同事务不可变结果事件进入`APPROVED`/`SUPERSEDED`，却未授权Plan身份行变更。只实现终态Owner会在数据库提交时失败或诱导绕过触发器。

## 方案与决定

- A：Review批准后仅把PlanVersion状态设为APPROVED，不维护Plan当前批准指针。拒绝：冻结身份投影将长期陈旧，下游Plan读取/版本创建无法安全选择当前Approved版本。
- B：放宽PlanRow通用UPDATE或删除原守卫。拒绝：开放名称、Project归属、状态及历史身份篡改。
- C（选择）：新增`20261026_0200`；只移除`current_approved_version_ref IS NULL`检查，保留Plan身份其它列不可变；新的专属guard只允许Approved指针及`lock_version`共同按预期递增更新，要求指针目标为同Project/Plan且状态`APPROVED`，旧指针在替换时为`SUPERSEDED`。追加延迟提交核验：Plan指针最终必须等于唯一当前`APPROVED`版本；已变更指针必须有本事务匹配的0190 `APPROVED`/`SUPERSEDED`事件事实。普通DML、无事件改变、错Plan目标、多Approved版本、TRUNCATE继续拒绝。

此修订是对CR-PLAN-007已声明的“批准后更新正式指针”实现前置补全，不扩展Review状态图/API或功能Scope。CR-PLAN-007和原冻结提交保留不改写。

## 实施/验收要求

只允许下一独立WBS `...-P05-P06-P01`实施ORM/0200 migration及数据库门；不实现终态应用Owner、Review API或Windows挂载。按Skill完成ORM/migration/code review、空库与已有DRAFT历史升迁、合法首次批准/后续替代的合成事务、无/错事件与多Approved负例、UPDATE/DELETE/TRUNCATE拒绝、空历史降级与有Review历史拒绝降级、Alembic drift=0；在Windows 11隔离PostgreSQL 18验证。成功的批准/替代业务行须由后续Plan终态Owner实现，schema WBS可用受控测试事务满足闭环，不伪造客户签批。

## 风险、兼容、迁移与回滚

- 风险：延迟指针闭环若只查当前状态而不核对应0190事件，会留下无法追溯指针变更；须在提交点关联Project/Plan/Version状态结果。并发审批/版本创建必须通过同一Plan身份行锁串行化。
- 迁移：不回填业务批准事实；已有Plan指针皆为NULL且PlanVersion无批准Review历史时，迁移仅更新约束/触发器。若发现已存在非空指针或非法历史，升级停止，不自动修补。
- 回滚：无指针/终态/状态结果历史时允许降级并恢复`closed`检查/守卫；任何Approval、Supercede或指针历史存在时拒绝降级、保留Schema/历史并向前修复。应用不挂载终态Owner即可回退未装配代码。
- 数据边界：只使用合成隔离数据库；无客户数据、外发、Secret、正式数据库操作或Gate通过结论。

## 授权与追溯

用户2026-09-24持续授权允许在记录CR、风险、迁移/回滚和验证后自主处理原方案不兼容，不需逐项请求批准。此CR据此授权实施，不表示用户单独审阅、数据库迁移已完成或Gate已通过。
