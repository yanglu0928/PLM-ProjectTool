# P06-P01 Plan Approved Pointer Schema 实施记录

- 日期：2026-10-26
- WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P01`
- CR：`CR-PLAN-008`
- 结果：`PASS_SCOPE_LIMITED`

## 实施内容

- ORM 移除了 Plan Approved 指针恒为 NULL 的旧约束，保留同 Plan/Project 复合外键。
- 新增 Migration `20261026_0200`：仅允许 Approved 指针与 `lock_version + 1` 同时更新；Plan 其他身份字段保持不可变，首次创建仍由0169限定为ACTIVE、无Approved指针、版本0。
- 在 Plan、PlanVersion Review状态更新及0190结果插入上安装延迟提交一致性核查，要求每个Plan的Approved版本至多一个且与当前指针完全一致；指针变化还要求匹配0190 Approved/Superseded结果。
- 无当前生命周期历史时允许降级恢复旧关闭守卫；存在指针、Review关联或非DRAFT状态时拒绝降级。

## 验证

- 定向单元测试：7 passed。
- Windows 11 隔离 PostgreSQL 18.6：完整迁移链至head、`alembic check` 无漂移；创建含Plan与DRAFT PlanVersion的合成数据；普通Plan列更新、DRAFT指针、Review结果TRUNCATE均拒绝；保留DRAFT数据降级至0190并升级回head通过。
- 完整后端：`4163 passed, 3 skipped, 6206 subtests passed`。
- `git diff --check` 通过。

## 偏差、限制与后续

- 首轮PG夹具暴露0200替换旧触发函数时误拒绝0169已允许的安全初始INSERT。已在0200保留原有ACTIVE/NULL指针/lock_version=0限制，并以PG真实迁移重新验证；不是开放普通Plan写入。
- 本WBS尚未由终态Subject Owner产生真实Review Approved结果并完成合法指针更新，也未测试历史批准数据下拒绝降级。该正向闭环依赖下一项P06-P02终态Owner，故本结果不表示Approved业务流程已通过或Gate关闭。
- 0200升级发现已有Approved/Review历史会停止，不自动回填或重写；必须先做可审计迁移决策。
- 本次只使用本机临时合成数据库；未访问正式数据库、客户数据或外部AI。

## 下一项

`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P02`：Review终态PlanVersion Owner编码前检查；必须复用统一Review转换事务，确保结果、Version状态、Approved指针、Audit及Receipt原子提交。正向闭环验证将连同该Owner验收。
