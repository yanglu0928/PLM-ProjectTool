# PRT-01-A08-A04：RequirementPrototypeLink REVOKE/SUPERSEDE Owner

日期：2026-10-08。结论：`PRT_01_A08_A04_LINK_LIFECYCLE_PASS`；`PRT-01-A08`完成。下一项：
`PRT-01-A09-A01` 冻结 HTTP 与 Windows 组合前置核查。

## 实现

- 新增内部REVOKE/SUPERSEDE命令、Repository行锁与持久生命周期操作；两类写操作复用A03已冻结的
  ProjectManager/ImplementationMember策略、License、Session/CSRF、Audit及幂等收据。
- REVOKE只允许强版本0的ACTIVE Link一次性进入REVOKED；不要求已经漂移的业务端点恢复，确保受权人员仍能
  安全终止失效Link。重放从持久终态恢复原200结果并核验Link身份。
- SUPERSEDE只允许相同Requirement/Prototype逻辑身份和相同purpose；新固定Version或Coverage必须至少一项
  变化，并重新执行A03当前Approved双端、批准Manifest、owned RequirementRef、Validator及验收条件全集证明。
- 为兼容0134 ACTIVE逻辑唯一键，单一事务先锁定并把旧Link终结为SUPERSEDED、绑定预生成UUIDv7，再插入
  replacement；延迟FK与replacement闭包在提交时证明同身份/同purpose/有效载荷变化。新Link和旧Link审计、
  receipt同事务提交，插入、审计或闭包失败均回滚旧行。

## 验证

- Windows 11 / PostgreSQL 18.6隔离数据库验证相同载荷拒绝、输入漂移拒绝、旧行先终结后插入、延迟闭包、
  replacement持久重放、REVOKE持久重放、防枚举权限、Audit与收据计数，以及注入replacement插入故障时旧
  ACTIVE行完整回滚。父级批准事实使用合成数据库夹具；A07已独立验证当前事实Validator，本项不冒充客户
  批准或完整UAT。
- 新增生命周期单元5项；Link/授权定向20项通过；后端全量3170项通过、3项既有环境条件跳过；compileall与
  Alembic drift通过。开发wheel共1216项，SHA-256
  `2de46ebe31dfd6b3c6fd5c081f3eb39bc6d658d42346cd4b02648e9ae8245026`，不是正式发行包。

无Migration、公开API、依赖、Secret、客户数据或外发变化；Schema head保持0134。停止装配Service可关闭新
生命周期入口，历史Link/Audit/receipt必须保留。A09 HTTP/Windows组合、A10前端、A11 Workflow、
Server 2025、Gate 3、UAT和正式发行仍待；Debian 13按用户指令跳过。
