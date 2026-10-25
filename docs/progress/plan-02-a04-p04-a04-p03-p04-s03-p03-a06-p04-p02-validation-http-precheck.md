# PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P04-P02：Validate HTTP合同边界编码前核查

日期：2026-10-26。状态：PRECHECK_COMPLETE；仅检查与实施计划，编码前提交。

## 单一WBS与输入

- 当前任务：将已验收的同步PlanVersion Validation Owner暴露为冻结API-04中的可选HTTP operation，并通过FastAPI契约测试证明安全边界及默认关闭；不做Windows实际PG装配/浏览器验收。
- 输入：P01 HTTP接线前置记录、Plan Validate Owner与0189结果仓储、既有PlanVersion Create路由/应用装配及Solution Validate API模式。
- 冻结合同：空体POST路径；禁止query；标准data与trace_id Envelope及HTTP 200；report精确字段为valid、blocking_issues、warnings、coverage_summary八计数、checked_at；no-store。
- 安全：复用trusted Origin、Session Cookie、CSRF、Idempotency-Key提取和当前Owner授权/License；路径UUID严格规范化；来源范围仅由数据库Owner导出。
- 失败映射：owner的隐藏资源/授权失败映射RESOURCE_NOT_FOUND；项目Archived、License、幂等冲突、验证输入错误按平台既有错误码；其他错误转换为SYSTEM_UNAVAILABLE。
- 装配：API App仅新增可选router；Windows factory须显式接Runtime/Session/Origin/License/Audit及既有文档/解析来源依赖，构造该Validate service并返回router；未配置时不得注册路由。

## 验收计划

- 新API模块：拒绝缺依赖；origin/CSRF/session/key/UUID/空body/query处理；调用同步Owner使用threadpool；报告投影只含冻结字段、UTC Z时间、no-store；异常不得泄露内部内容。
- Contract tests：带与不带可选router的404/200；有效请求全部路径/报告字段；无Session、坏Origin/CSRF、缺Key、query/非空body/非法UUID及Owner错误Envelope；无新增外部副作用。
- Windows组合只验证工厂返回正确可选router，实际数据库端到端留待后续独立WBS。
- 无Migration、API版本升级、License/架构调整、依赖新增或CR需求；冻结API不变。

## 结论

现有边界足以承载此可选接口，无阻断。先新增Plan HTTP模块与定向契约测试及应用/router组合参数；随后在独立WBS以Win11真实PG18验完整平台组合，保持默认应用关闭。
