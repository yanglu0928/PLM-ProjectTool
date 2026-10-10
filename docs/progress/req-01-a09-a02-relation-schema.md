# REQ-01-A09-A02：RequirementRelation Schema

日期：2026-10-07。结论：`REQ_01_A09_A02_RELATION_SCHEMA_PASS`。下一项：
`REQ-01-A09-A03` RequirementRelation create/list Owner。

## 实现

- 新增Migration0121与`RequirementRelationRow`，端点同时保存Requirement、RequirementVersion和Project，
  以复合外键证明两端是同项目固定版本；replacement使用relation+project复合自引用。
- 固定五类关系和`ACTIVE / REVOKED / SUPERSEDED`；领域基线使用`relation_state`，SC索引示例中的`state`
  是谓词简写，本实现不另造重复状态列。
- DUPLICATES/CONFLICTS_WITH要求完整端点UUID tuple升序；所有类型禁止同Version自环。ACTIVE边按
  project/source-version/type/target-version唯一，并提供冻结SC要求的入/出邻接partial indexes。
- Trigger只接受初始ACTIVE/lock0，之后仅允许一次ACTIVE→REVOKED或ACTIVE→SUPERSEDED/lock1；所有
  端点、类型、创建人/时间不可改，终态不能恢复，删除和截断失败关闭。
- 本Schema不执行DAG递归。并发无环证明必须由A03/A04在Project写锁下完成；Owner前没有业务写入口。

## 验证

- Windows 11 / PostgreSQL 18.6：0120→0121升降重升、同项目复合FK、ACTIVE重复、自环、跨项目、对称
  反序、合法规范边、同项目ACTIVE replacement、合法撤销/替代、终态恢复/内容改写/删除/截断拒绝、
  历史拒降及Alembic drift通过。
- 定向21项、后端全量3020项通过且3项既有环境跳过。首轮全量中既有RAG crypto测试把随机密文末字节
  固定替换为`x`，恰逢原值也是`x`而没有实际篡改；该测试独立10次及全量复跑均通过。本WBS未修改RAG。
- 开发wheel共1149项，SHA-256
  `c87c9c8d1af8baefee2c709fd7e17f15fbcac0104765b6854ef360aabaa0ff97`，不是正式发行包。

Schema head升至0121；无公开API、依赖、Secret、客户数据或外发变化。空历史可降0120；存在关系历史后
拒绝物理降级并要求向前修复。
