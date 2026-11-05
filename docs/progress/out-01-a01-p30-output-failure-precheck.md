# OUT-01-A01-P30 编码前检查：Output 不可恢复失败原子终态

- 日期：2026-11-05
- Phase/WBS：Phase 2 Platform Core / OUT-01-A01-P30
- Change Request：CR-OUT-026
- 检查结论：PASS_WITH_LIMITATION，可编码

## 编码前检查

- P29 Owner 已提供 OutputRequest→Jobs 的一致锁序、共享 UnitOfWork、当前 Output lease proof、确定性 execution ref 与 SYSTEM Audit 例式。
- JobLeaseRepository.retry_or_fail 可在调用者传入的 transaction 内锁定并终结当前有效 attempt；Output 层不得直接改 Jobs ORM。
- OutputRequest 已有 GENERATING、FAILED、completed_at、current_execution_ref 与 lock_version；无需Schema或API变化。
- 任务单一目标：只处理受控 worker 报告的一类白名单不可重试结果，原子将 Jobs 与 Output 收敛为 FAILED，并写一条最小 SYSTEM Audit。
- 不实现重试策略、不执行 Plugin/渲染、不写文件、不挂载服务/HTTP、不引入服务账号或正式Publisher信任。
- 失败输入固定为代码白名单，不持久化自由文本；不接受过期lease、错worker、错误Job/request/project/snapshot/execution绑定或非GENERATING状态。
- 验证：单测及同父包PG18 smoke中真实SQLAlchemy/lease事务正向、错绑/旧token拒绝、Audit注入失败回滚；云端全链回归仅D盘runner。
- 变化已先记 CR-OUT-026；P25阻塞与路线切换已按CR-OUT-021记录。没有基线、API、Schema或数据库迁移偏差。
