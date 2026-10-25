# PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P04-P03-P03-P02：Validate真实HTTP/PG18组合验收

日期：2026-10-26。结果：`PLAN_VERSION_VALIDATE_HTTP_POSTGRESQL_PASS`；Win11一次性PostgreSQL 18合成集成，不是生产/UAT/Gate结论。

## 实施与边界

- 在既有全Approved Outline/Section/Requirement/Trace/Plan/PlanVersion合成PG验证器中，通过Windows Validate router factory挂载API可选路由，再经FastAPI TestClient执行真实HTTP请求。
- 不触碰生产数据库、用户方案库、发行Vault/公钥或真实客户数据；验证器自有一次性PG生命周期，完成后清理。无产品代码/API/Schema/依赖变化。
- 验证角色来自该合成Project的活动ProjectManager或ImplementationMember；另用同项目CustomerMember合成Session检验非写权限。

## 验收结果

- 经当前有效Session/CSRF/Origin/License和服务端批准来源证明返回200；精确报告字段、UTC Z checked_at和no-store正确；PlanVersion始终DRAFT。
- 同Key重放返回完全一致的report data（包含首次checked_at）；每次HTTP envelope有独立trace_id，分别与各自响应头吻合。每次成功只增加一条0189结果、一条PLAN_VERSION_VALIDATED Audit和一条幂等Receipt。
- 跨Project返回404、同项目CustomerMember返回404、不可信Origin返回403；均无验证结果/Audit/Receipt增量。
- 注入Audit失败的HTTP命令返回503，0189结果、Audit与Receipt仍保持原数量；Owner内部Audit失败原子性也再次通过。
- 标记：`PLAN_VERSION_VALIDATION_OWNER_POSTGRESQL_PASS`及`PLAN_VERSION_VALIDATE_HTTP_POSTGRESQL_PASS`；整套上游来源/Plan/版本HTTP合成验证脚本退出0。

## 验证修正记录

首次验收器把每次HTTP外层trace_id也要求跨请求相同，造成测试失败；trace_id按请求变化是平台跟踪合同的预期行为。已将断言收紧到报告data/checked_at完全一致，并分别核对两次trace头；未改产品行为，修正后完整验证退出0。

## 兼容与下一项

- 无Migration/API兼容变化；HTTP route仅由显式Windows平台Write root提供，login-only/只读默认关闭（其组合合同已在前一WBS通过）。
- 已有的全量后端回归：4149 passed、3 skipped、6206 subtests；本次额外Win11隔离PG18完整验证器退出0。
- 下一项：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P01`，核查冻结的PlanVersion SUBMIT_REVIEW及现有Review Subject/Submission/资格策略，确定只有ProjectManager能将具备现时Validate成功与就绪条件的固定DRAFT送入真实统一Review；不得把Validate或AI结果等同业务批准。
- CR-PLAN-006的Owner/HTTP/隔离PG链已验，但不代表Gate 3、Pilot、正式Release。
