# REQ-01-A09-A03：RequirementRelation create/list

日期：2026-10-07。结论：`REQ_01_A09_A03_RELATION_CREATE_LIST_PASS`。下一项：
`REQ-01-A09-A04` RequirementRelation revoke/supersede。

## 实现

- 新增create/list内部Service与PostgreSQL Repository；补齐冻结`REQ_RELATION_LIST/CREATE/REVOKE/
  SUPERSEDE`角色策略。LIST允许全部当前项目成员；三项写操作允许ProjectManager、ImplementationMember。
- create在License、Session+CSRF、项目角色验证后取得Project行锁，再共享锁定并证明两端精确
  Requirement+Version+Project组合；端点错配和跨项目均隐藏为资源不存在。
- DUPLICATES/CONFLICTS_WITH在幂等指纹和持久化前按完整端点UUID字节序归一化，反向输入不会形成第二边。
- DEPENDS_ON与PARENT_OF分别以递归CTE检查target到source可达性。Project行锁令同项目所有图写串行，
  防止两笔并发事务各自看不到对方而同时写成环；跨项目不互相阻塞。
- ACTIVE唯一边提供自然幂等；不同Idempotency-Key重复创建返回同一边且各自保存receipt，只有首次物理插入
  写Audit。列表按UUIDv7 relation ID倒序keyset，限定Project且不复制Version正文。

## 验证

- Windows 11 / PostgreSQL 18.6：真实License、Session/CSRF、三种角色、固定端点、直接环拒绝、反向
  对称输入自然幂等、两页无重叠分页、端点错配拒绝和Alembic drift通过。
- 两个线程由不同Actor同时提交互补PARENT_OF边；Project行锁后只有一笔CREATED，另一笔读取已提交边并
  返回`REQUIREMENT_RELATION_CYCLE`，数据库只保留一个方向。
- 定向12项、后端全量3025项通过且3项既有环境跳过；开发wheel共1151项，SHA-256
  `5b44a3c196bbbb16613228617855bbe6e3d9280b8a0116353fdd60c3a911ab6d`，不是正式发行包。

无Schema、公开API、依赖、Secret、客户数据或外发变化。停止Owner可关闭新写入口，既有关系、receipt与
Audit保留。HTTP/Windows显式组合按计划留A10。
