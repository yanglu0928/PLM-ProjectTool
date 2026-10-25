# PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P04-P03-P02：Windows显式Write启动根装载Validate

日期：2026-10-26。结果：`PLAN_VERSION_VALIDATE_WINDOWS_WRITE_ROOT_MOUNT_PASS_CONTRACT_ONLY`；未完成真实PG/业务来源链验收。

## 实施

- 将PlanVersion Validate router factory接入Windows生产组合根；仅现有显式`create_production_platform_write_app`分支创建和挂载。使用同一Runtime、Session、Origin、License guard、Audit与当前Document/Download/Parse结果读取服务。
- Login-only与只读Platform分支不创建Validate router；默认`create_app()`仍无此端点。
- 不接入Plan Create/Read/WBS端点，不扩大该WBS到其他业务范围；无Schema/API/依赖/迁移变化。

## 验证

- 定向生产组合/路由合同：6 passed、11 subtests passed。覆盖默认/login-only/只读404和显式Write模式工厂接线、参数生命周期与挂载路径。
- Write根测试用stub router证明组合路由分发，不代表真实Windows Runtime/License/Approved Source业务请求已通过。
- HTTP/Owner全量后端回归：4149 passed、3 skipped、6206 subtests passed。
- 定向compileall、diff-check、Secret scan通过。

## 限制与下一项

- 尚未在Win11以一次性真实PostgreSQL 18完成实际HTTP请求、当前Approved来源证明和Audit/0189/Receipt数据库断言；不标真实生产根或Pilot通过。
- 下一项：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P04-P03-P03-P01`，先检查已有来源完整PlanVersion PG验证器如何装入Validate HTTP请求/真实Windows组合，确认License/Session/Origin夹具均为合成且不触碰生产DB；定义PG行计数、跨项目/非PM/IM与故障回滚断言。
- Gate 3、Pilot和正式Release未变。
