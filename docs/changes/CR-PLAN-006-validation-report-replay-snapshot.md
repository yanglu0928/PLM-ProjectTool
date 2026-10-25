# CR-PLAN-006：PlanVersion Validate 首次报告不可变重放快照

日期：2026-10-26。状态：`AUTHORIZED_FOR_IMPLEMENTATION_BY_CR-EXEC-001`；非Gate通过。

## 发现

冻结 API-04 的 `PLAN_VERSION_VALIDATE` 要求 `S,L,C,I,A` 并返回 `ValidationReport(valid, blocking_issues, warnings, coverage_summary, checked_at)`。现有 `plt_idempotency_receipts` 有意只存请求指纹、结果引用与HTTP状态，不保存响应正文；`aud_events` 也只有单个受限 `reason_code`/状态摘要。Plan验证报告包含多个稳定问题码、需求/方案覆盖计数和首次检查时间。若同Key重放时重新读取当前Solution/Requirement事实，来源可在首次请求后变化，导致同一个幂等请求返回不同报告；若只靠Audit标量重建，则信息不完整。静默把报告内容塞入reason_code不符合其字段语义，也有长度与校验约束。

## 方案比较

- A：重放时重新执行来源复证并返回新报告。拒绝：与同Key返回首次结果的项目幂等合同冲突，结果会随当前来源改变。
- B：仅扩展 `plt_idempotency_receipts` 增加通用JSON响应快照。拒绝：修改跨模块共享基础设施和既有迁移/所有调用方；扩大到本功能以外的回归与隐私面。
- C：新增Plan模块专用、与Audit和固定PlanVersion绑定的不可变验证结果表，保存精确报告字段；同事务写入Audit、结果快照和通用Receipt。选择：范围最小，重放可复原首次响应，不改变PlanVersion生命周期或公开合同。

## 决定与数据边界

选择 C。追加Migration `20261026_0189`，新增一个 Plan-owned 验证结果表，记录Audit事件关联、Project/Plan/PlanVersion/Actor身份、版本快照指纹、`checked_at`、`valid`、blocking/warning code数组及coverage计数。表不含客户正文、Evidence正文、API Key、License材料或可变当前指针；禁止 UPDATE/DELETE/TRUNCATE。结果行、Audit、通用幂等Receipt必须在一个现有授权事务内原子写入。

必须保留 Gate 2 冻结 Schema V1/提交 `64cdf09`；0189是有追溯的后续CR增量，禁止改写原冻结内容。该表只承载每次已执行Validate的最小首次报告事实，不改变PlanVersion、不自动送审/批准，也不把验证成功等同业务批准。

## 迁移、回滚与验证

- Up：受约束地新增append-only报告表和必要索引/FK；不得重写既有业务行。
- Down：若存在任何验证结果历史则失败关闭，不删除历史；空表可安全移除本Migration对象。升级/空库/带历史回滚保护/重升/drift均在Win11隔离PostgreSQL 18验证。
- Owner验证原子性：报告/Audit/Receipt同事务；Audit或快照写失败无残留；同Key重放逐字段返回原报告和checked_at；不同指纹冲突；来源变化不改写重放；撤权/跨Project仍拒绝；并发同Key只有一条首次结果。
- 限制：0189不得脱离后续受权Plan Validate Owner单独部署；在Owner与安全HTTP接线验收前默认入口保持关闭。

## 授权与兼容性

按用户持续自主执行授权，在此登记偏差后实施。无API/License/架构模块边界变化；增加一个Plan-owned不可变内部报告表及Migration。若实现发现需修改通用Receipt、解锁历史或更改报告字段/API，应停止该项并新增决策/CR，不得扩大本CR。
