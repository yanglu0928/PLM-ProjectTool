# PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P04-P02：PlanVersion Validate HTTP合同边界

日期：2026-10-26。结果：`PLAN_VERSION_VALIDATE_HTTP_CONTRACT_PASS`；仅可选HTTP边界/应用参数合同，不含真实Windows平台运行验收。

## 实施

- 新增冻结POST路径Validate router，拒绝query和非空body；复用trusted Origin、Session Cookie/CSRF、Idempotency-Key及标准平台错误Envelope，通过threadpool调用同步事务Owner。
- 响应严格投影冻结ValidationReport字段，coverage八计数和UTC Z checked_at；不泄漏Audit身份/内部版本指纹，并设置Cache-Control no-store。
- API App仅增加一个可选router入参，默认App未注册端点。
- 增加显式Windows PlanVersion Validate router factory，依赖既有服务端来源Proof/授权/License/Audit组合；本WBS没有在主运行时或生产启动路径挂载它。
- 无Migration、Breaking API、第三方依赖、License变化或客户业务数据写入。

## 验证

- HTTP合同、Owner和权限矩阵定向：18 passed，870 subtests。
- 完整后端回归：4149 passed，3 skipped，6206 subtests passed。
- 契约覆盖可选路由默认404、报告字段/时间投影、Session/CSRF/Origin/Key/path/body/query拒绝及许可/幂等/资源/系统错误Envelope。
- diff-check和定向编译检查通过；Secret扫描无命中；代码已提交并推送至feature/license-runtime-guard。

## 边界与下一项

- 当前只是HTTP模块合同及可选Factory。尚未由实际Windows 11启动根创建并装载router，也尚无真实PG18 HTTP/来源授权组合验收。
- 下一项：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P04-P03-P01`，检查Windows生产启动根是否已有独立PlanVersion组合入口、共用运行时事实依赖/生命周期和显式功能开关；确定最小接线点与隔离PG18验收/回滚计划。不得改变普通默认App的路由集合。
- Gate 3、Pilot、正式三平台Release均未因此通过。
