# OUT-01-A01-P18：Output取消HTTP显式Windows write组合编码前检查

- 日期：2026-11-04
- 结果：PASS_WITH_LIMITATION
- 变更：CR-OUT-014
- 前置：P17以PASS_SCOPE_LIMITED通过Hosted run 41799812913
- 本任务代码尚未实施；开发及测试仅在GitHub托管运行器执行，不使用本机C盘

## 单一问题

把P16已存在的OUTPUT_REQUEST_CANCEL HTTP adapter接入显式Windows write composition，使受控Write模式能通过冻结HTTP路径调用已经由P17验收的Owner；保持登录/默认及平台只读模式不挂载。

## 编码前检查证据

- modules/output/api/cancel_request.py已严格解析Session/CSRF/Origin、If-Match、Idempotency及仅含reason的JSON，并调用注入Service；URL/响应不需变化。
- entrypoints/api.py:create_app使用默认None的可选router注入模式，但没有output cancel参数或include_router逻辑。
- entrypoints/production_login.py当前构造runtime、sessions、origins、license guard、Audit及receipts；写路由在include_secret_write显式分支装配，但没有Output Cancel service/router。
- SqlAlchemyProjectWriteAccess可做同事务登录Session身份校验；ProjectAuthorizationService/SQL仓库可做当前Project角色核验，现有策略只有OUTPUT_REQUEST_LIST，尚无取消策略。
- P17已直接在PG18.6验证Output/Jobs双行、Job绑定、If-Match、幂等、Audit回滚及数据库时钟，故无需新Migration。

## 选定实现与边界

新增Output Cancel Access与Windows Composition factory：在Service同一UOW重新核验Session，允许请求创建者或仅ProjectManager，调用正式LicenseGuard、Output/Jobs repository、receipt和Audit依赖；通过可选Router参数只在显式Windows include_secret_write路径挂载。默认和只读模式保持404。ImplementationMember、CustomerManager、跨Project及无权用户不因普通写权限而取得取消权。

无Schema/API变化，不接其他Output端点或Worker；未提供正式信任时write模式仍必须fail closed。独立验收为PG18 HTTP/Service组合的合成数据测试及完整Hosted回归，不能宣称Win11实机/Pilot/Gate/Release通过。
