# PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P04-P03-P03-P01：Validate HTTP/PG18验收器前置核查

日期：2026-10-26。状态：PRECHECK_COMPLETE；本项仅验证器审查，无数据库/业务数据变更。

## 编码前检查

- 当前WBS：PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P04-P03-P03-P01。
- 验证目标：在Win11一次性PostgreSQL 18隔离实例把正式Windows Validate router factory接入FastAPI TestClient，针对合成Approved Outline/Section/Requirement/PlanVersion执行POST；证明真实Session/Project授权/License/来源Proof/Owner/0189/Audit/Receipt贯通。
- 现有fixture：validation/plan-02-a04-p03-owner-transaction-pg/verify.py由已批准Solution全来源合成链派生，启动/销毁自己拥有的临时PG，创建短期合成Session、Project/角色、Outline/Review/Requirement/Trace、Plan/PlanVersion；只用本地合成Storage root，不读取用户方案库/生产数据。
- 现有_verify_http_composition已用SqlAlchemySessionRepository、LoginOriginPolicy、TestClient及同一Win11 PG18验证PlanVersion创建/读取/WBS路由，可复用其临时Session/Token/CSRF/Origin和服务对象。
- 本验收只把Validate加入该合成HTTP harness，不通过主生产服务启动器，不读取正式Windows账户Vault/发行License/生产数据库；与P03-P02已完成的实际启动根路由挂载合同分开陈述。

## 验收/风险计划

- 有效PM/IM Validate：路径与空body成功，Report字段与Owner一致，UTC Z/no-store；只产生一条0189结果、一条PLAN_VERSION_VALIDATED Audit和一条专属幂等Receipt，PlanVersion状态保持DRAFT。
- 同请求同Key：HTTP返回首个Report逐字段相同、checked_at相同，DB仍单行；不同幂等payload在路由层因body非空拒绝，Owner payload冲突边界已由内部测试覆盖。
- 不同项目路径/没有权限的同项目成员/无效Session或CSRF/恶意Origin按HTTP稳定Envelope失败，不能写报告/Audit/Receipt。
- 注入Audit失败时HTTP失败且报告/Receipt无增量；许可失效错误映射保持拒绝。任何PG操作只能发生在验证脚本自建临时PG并由脚本销毁的生命周期内。
- 不使用测试超级用户伪造业务Audit/报告行；业务行通过完整Owner事务产生。此项没有客户数据、外发或生产部署。
- 无代码/依赖/Migration/公开合同变化；若工具链或临时PG不可用则记录客观阻塞并保留已完成的Owner/API范围。

## 结论

验证器已经有正确的合成Session和全来源fixture；无外部依赖阻断。下一项：PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P04-P03-P03-P02，在该一次性PG harness加入真实Validate HTTP正/拒绝/重放/回滚断言并运行。
