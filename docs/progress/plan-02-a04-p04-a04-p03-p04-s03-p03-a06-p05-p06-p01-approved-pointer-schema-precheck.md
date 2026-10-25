# A06-P05-P06-P01 Plan Approved Pointer Schema 编码前核查

- 日期：2026-10-26
- 结果：`PRECHECK_PASS_IMPLEMENTATION_PENDING`
- 当前Phase：Phase 2：Platform Core
- 当前WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P01`
- 输入基线：Gate 2冻结Plan实体/Schema；CR-PLAN-007/0190 Review状态结果守卫；CR-PLAN-008已授权的Approved pointer实现差异。
- 前置任务：Plan身份、PlanVersion生命周期及0190已实现；P05-P06父项已确认0167指针关闭阻断；尚无终态Owner或真实批准业务历史。

## 编码前检查

|检查项|结论|
|---|---|
|涉及模块|仅`plan`ORM和Alembic migration `20261026_0200`；Review/Plan业务Owner不在本WBS。|
|涉及实体|`PlanRow.current_approved_version_ref/lock_version`、同Plan的`PlanVersionRow.version_state`及0190 `APPROVED/SUPERSEDED`结果；不变更Review表/终态事实。|
|涉及API|无。冻结API-04的SubmitReview/Review决定合同和路径均不修改。|
|涉及权限|本WBS只实现数据库守卫，不向任意调用者授予批准权。引用目标必须同Project/Plan；有真实Review结果的状态事件由0190既有触发器校验。授权/Reviewer资格仍由后续统一Review Owner执行。|
|验收标准|移除0167“永远NULL”检查，但保留Plan其它身份字段不可变；仅允许Approved pointer发生变化时`lock_version`精确+1。提交点无条件保证每Plan恰有0或1个APPROVED版本，且pointer与该版本完全一致；指针首次设置/替换须与匹配0190 APPROVED/SUPERSEDED事件闭环。合法合成状态事务通过，缺指针、错指针、无结果事件、多Approved、任意Plan列更新和TRUNCATE拒绝。Win11/PG18空库/含Draft历史升级、drift、允许无历史降级、含生命周期历史拒绝降级通过。|
|风险|只有Plan指针UPDATE trigger不够：绕开Owner直接使用有效统一Review事实推进Version状态但不改Plan指针时会残留陈旧状态。因此必须对PlanVersion状态更新/0190结果插入和Plan pointer更新都安装延迟提交一致性核验，并要求事件证据。并发归属由现有Plan身份行锁序列化；DB deferred trigger仍须在最终提交面覆盖任意SQL写入顺序。|

## 迁移及闭环策略

迁移只调整`ck_pln_plans__approved_pointer_closed`及Plan identity守卫函数，原Plan identity各字段、DELETE/TRUNCATE门仍保留。新的Approved更新守卫只允许`current_approved_version_ref`变化与`lock_version=old+1`同时发生；另以初始延迟约束检查目标版本同Project/Plan、当前状态唯一为APPROVED，且有0190 APPROVED结果。替换旧指针时还要求旧版本已有SUPERSEDED终态事实。延迟一致性约束同时由PlanVersion状态更新/0190结果插入触发，避免仅靠Owner顺序维持指针正确。

无业务历史时可恢复原0167关闭式守卫和NULL Check；存在pointer、非DRAFT/Review refs或0190历史时，downgrade必须拒绝并保留事实。不会手工操作正式数据库。

## 本次核查结果

核对`0167`明确为Plan身份行所有更新返回异常，并以CHECK禁止非NULL当前批准指针；`orm.PlanRow`保留同一NULL Check。`0190`能验证PlanVersion的Approved/Superseded结果与实际PROJECT Review/Round/Actor，却没有检查Plan指针。CR-PLAN-008已先行记录只追加0200来补该守卫，不改写0167/0190和Gate 2冻结基线。本记录仅编码前核查，尚无Schema/ORM/代码变化。

## 下一项

实施`CR-PLAN-008`：修改ORM、追加0200 migration及迁移测试，执行Win11隔离PG18合法/负例/历史downgrade/drift验证；不实现Review终态Owner、不挂载Subject Registry/HTTP。
