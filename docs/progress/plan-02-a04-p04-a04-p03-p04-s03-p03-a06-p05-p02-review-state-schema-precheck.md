# A06-P05-P02 PlanVersion Review 生命周期状态 Schema 前置核查

- 日期：2026-10-26
- 状态：`PRECHECK_COMPLETE`
- 变更依据：`CR-PLAN-007` 已先行登记并推送；本 WBS 只实现 Review 状态事件 Schema/Guard，不接 SubmitReview Owner、HTTP、Subject 或终态决定。
- 基线：冻结的 DB Schema V1 保持原样；0188 append-only 根守卫保留为迁移历史；在其后新增 0190。不得通过关闭触发器或复制写入绕开守卫。

## 单一问题与边界

为后续 Plan Review 生命周期提供数据库可证明的状态转换：PlanVersion 内容列继续不可变，仅允许 `version_state`、`review_ref`、`review_round_ref` 在合法状态转换中更新；每次状态更新须在同一事务写入不可变、可追溯的 Review 状态结果事件，并由延迟约束保证根状态与事件闭合。

本 WBS 不创建 Review/ReviewRound，不实现送审/批准服务，不改 `/api/v1`，不宣称已完成 Review 业务功能。

## 编码前检查

1. 迁移链当前到 0189；0188 对 PlanVersion UPDATE 全拒绝，0190 必须显式替换其根守卫，不能弱化内容不变量。
2. PlanVersion 已有版本状态及 Review/Round 引用字段；现存 Review/ReviewRound 为真实 PROJECT 域记录，后续必须以复合身份及主体类型/主体 ID 校验。
3. 按 CR-PLAN-007 建立仅追加状态结果表，事件与 PlanVersion、Review、ReviewRound、Project、Actor 同源绑定；事件插入、状态更新与延迟闭合在同事务。
4. 合法转换限定为 DRAFT→IN_REVIEW，IN_REVIEW→APPROVED/RETURNED，APPROVED→SUPERSEDED；除状态及配对引用外任一 PlanVersion 列变化均拒绝。非法、无事件、错绑及跨项目均由数据库拒绝。
5. 事件表拒绝 UPDATE/DELETE/TRUNCATE；降级仅在无状态历史且所有 PlanVersion 仍为 DRAFT、无生命周期引用时允许，否则拒绝。
6. 验收使用 Windows 11 隔离 PostgreSQL 18 合成数据库：迁移升级/空库降升、合法转换闭合、非法转换、内容变更、缺失/伪造/错绑事件、历史安全降级及事务回滚。不得使用客户数据或复制生产数据。

## 风险与验证

- 风险：迁移触发器可能允许字段更新却未证明它对应实际 Review 状态；通过真实 Review/ReviewRound/主体复合绑定和延迟闭合约束降低风险。
- 风险：迁移降级丢失已发生的审批历史；downgrade 对任何历史状态/引用失败关闭。
- 验证次序：编码前独立检查；迁移与ORM定向测试；Windows 11/PG18隔离验收；后端回归；wheel/安装不在本 WBS；Secret 检查；获取远端并确认无冲突后提交推送。
- 当前尚未实现或验证 0190；本记录不是 Schema PASS 或 Gate 通过证明。

## 下一项

若本 WBS 验收通过，下一项为 `PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P03`：PlanReview Subject 当前就绪性证明；不得提前进入 Owner/HTTP。
