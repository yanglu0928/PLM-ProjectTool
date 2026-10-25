# A06-P05-P06-P02 PlanVersion Review 终态 Owner

- 日期：2026-10-26
- WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P02`
- CR：`CR-PLAN-009`
- 结果：`PASS_SCOPE_LIMITED`

## 实施

- 新增Migration `20261026_0210`：在不改0190/0200历史的前提下，增加内部 `WITHDRAWN` 结果形状；它严格绑定真实PROJECT Review/Round/Actor撤回事实，并把PlanVersion处置为既有公开状态`RETURNED`。探测到已有不完整撤回事实时升级停止；存在撤回事实时降级拒绝。
- 增加Review终态Owner及持久层：同一Review转换事务锁定固定PlanVersion、批准终态复核当前版本来源/校验Proof，原子消费批准/退回/撤回结果、维护Approved唯一指针和旧版`SUPERSEDED`事实，并写Plan Audit；Review既有Owner继续写Review Audit及幂等回执。
- 保持内部Owner范围；没有挂载公共Subject Registry、HTTP、Windows启动根或用户入口；不改冻结API。

## 验收

- 定向单测：17 passed。
- Windows 11 / PostgreSQL 18.6隔离真实数据库：完整迁移到head、`alembic check`无漂移通过；PlanVersion依次送审/批准两版/撤回第三版，真实核验旧Approved→SUPERSEDED、唯一Approved指针切换并在撤回后保留、WITHDRAWN Review/Round→RETURNED PlanVersion结果、Review/Plan Audit、审批/撤回收据和同Key原响应精确重放。注入Plan终态Audit失败后Review、Plan结果、事件和Receipt整体回滚；0210对含真实撤回历史的降级失败且Alembic仍位于0210。
- P06-P01隔离PG脚本再次验证完整迁移/漂移及Draft历史降至0190并重升head。
- 完整后端：`4170 passed, 3 skipped, 6206 subtests passed`。
- PG组合中的Session、License、Project策略、Reviewer资格和当前来源验证Evaluator使用合成替身；Review/Round、Plan、Audit、Receipt、状态结果、迁移和数据库触发器为真实持久化。没有真实用户/客户确认，也没有调用外部AI或正式数据库。

## 偏差与限制

- 首轮PG调试发现验收器授权回调签名错误、Reviewer replay夹具身份不匹配及多版本送审时序违反“仅最新版本可送审”；仅修正合成夹具后全链通过，产品行为未因此放宽。
- 尚未在PG组合逐项伪造错Actor/错误Round/无结果负例；由Migration约束/单元策略覆盖。应用Owner尚未进入Subject Registry、公开API、Windows包、来源真实凭据/资格验收。不得把本结果表述为Gate、Pilot或Release通过。

## 下一项

`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P03`：先做Subject Registry与显式Windows组合入口的编码前核查；确认各终态回调的统一身份/Review Scope契约、授权与依赖来源，确定只完成受控内部Registry装载、不越界接公开HTTP。
