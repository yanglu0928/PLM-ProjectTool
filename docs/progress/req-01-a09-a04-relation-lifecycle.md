# REQ-01-A09-A04：RequirementRelation revoke/supersede

日期：2026-10-07。结论：`REQ_01_A09_A04_RELATION_LIFECYCLE_PASS`。下一项：
`REQ-01-A10-A01` Requirement HTTP/Windows组合前置核查。

## 实现

- 在A03 Service/Repository新增revoke与supersede，复用License、真实Session+CSRF、冻结项目角色、
  Project行锁、幂等receipt和Audit；未新增第二套生命周期。
- Revoke共享锁定同项目ACTIVE边，只允许一次写为REVOKED/lock1；原Key重证固定终态后回放，新Key对终态
  返回资源不存在，不能恢复或重写。
- Supersede共享锁旧ACTIVE边，并从递归DAG查询中排除该旧边；这使A→B原子替换为B→A不会被即将终结
  的旧边误判，同时仍能发现其余ACTIVE图形成的真实环。
- replacement经过端点证明、对称规范化和类型DAG检查；可新建或复用另一条既有ACTIVE边。旧边随后
  原子转为SUPERSEDED/lock1并固定replacement引用；相同内容自替代拒绝。
- receipt固定撤销旧边或replacement ID并在回放时重证状态/引用；撤销保持冻结`200`，替代保持冻结
  `201`。只有物理新边产生CREATED Audit，每条被消费旧边产生REVOKED或SUPERSEDED Audit。

## 验证

- Windows 11 / PostgreSQL 18.6：DEPENDS_ON反向replacement（证明排除旧边）、同Key替代回放、旧终态
  拒撤销、撤销及回放、撤销后拒替代、复用既有RELATED_TO ACTIVE replacement、状态/指针、Audit、
  receipt及Alembic drift通过。
- 首轮仅最终夹具把相同Key重放误计成新增receipt；修正期望为6后从新库复跑，产品规则未改变。
- 定向14项、后端全量3027项通过且3项既有环境跳过；开发wheel共1151项，SHA-256
  `3ecf0f2e670050fca5560af6343bcc955dc702c53a71852980a7e19fbc1f4aa1`，不是正式发行包。

无Schema、公开API、依赖、Secret、客户数据或外发变化。A09内部能力完成；冻结HTTP与Windows显式组合
按计划进入A10。
