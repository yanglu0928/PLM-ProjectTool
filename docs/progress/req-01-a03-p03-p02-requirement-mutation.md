# REQ-01-A03-P03-P02：Requirement identity mutation Owner

日期：2026-10-07。结论：`REQ_01_A03_P03_P02_REQUIREMENT_MUTATION_PASS`。A03完成；下一项：
`REQ-01-A04` RequirementVersion 与六类 owned 集合 Schema/Migration。

## 实现与边界

- 新增 PATCH、DEFER、REJECT、ARCHIVE 四类严格内部命令。PATCH由PM/ImplementationMember执行；
  DEFER/REJECT由PM/CustomerManager执行；ARCHIVE仅PM。全部执行Session/CSRF、License、当前角色、
  持久幂等、Audit、Root行锁和ETag版本栅栏。
- PATCH仅允许ACTIVE身份改code并保持项目内大写规范唯一；DEFER/REJECT仅允许ACTIVE进入对应状态，
  reason/impact各1～2000字符，并要求1～100条当前同项目PROJECT/ELIGIBLE Evidence；ARCHIVE允许任一
  非归档状态进入ARCHIVED。没有未延期、恢复或复活命令。
- Migration0115新增不可变命令结果。数据库触发器重证Root、决策、Evidence与结果形状；两个
  DEFERRABLE closure trigger保证Root UPDATE必须有同版本结果、每个决策必须至少一条Evidence。
- Evidence资格是决策发生时证明；后续Evidence撤销不改写历史决策。幂等重放先重证当前权限，再返回
  首成功快照，即使Root之后已归档也不读取当前状态冒充首响应。

## 验证

- Windows 11 / PostgreSQL 18.6：0114→head→0114→head、drift、真实Session/角色/License、PATCH唯一性、
  同项目/跨项目/GLOBAL/REVOKED Evidence、DEFER/REJECT、从DEFERRED归档、首结果跨后续变更重放、
  同ETag双线程竞争、Audit故障回滚恢复、直接SQL无结果提交拒绝、伪造结果拒绝、撤权重放拒绝与历史
  拒降全部通过；临时库清理。
- 定向27项、后端全量2980项通过，3项既有环境跳过；compileall通过。
- 开发wheel共1124项，SHA-256
  `5e53f67928730e2b3568db32e5c732fc0f48e3a7be8d81bff07a6437414e75f4`，不是正式发行包。

无公开API、前端、依赖、Secret、客户数据或外发变化；A04 Version、HTTP/UI/Workflow、Gate3/UAT/发行仍待。
