# SOL-01-A16-P04：Reference Eligibility 可选 HTTP 合同

日期：2026-10-09。结果：`SOL_01_A16_P04_REFERENCE_ELIGIBILITY_HTTP_PG_PASS`；PROJECT/GLOBAL 真实 ASGI/Session/隔离 PG 合成验收。默认应用不挂载，Windows 平台正式组合尚未接线。

## 编码前检查

- Phase/WBS：Phase 2 / SOL-01-A16-P04；输入冻结 API-04 双 Scope `:set-eligibility`、CR-SOL-014、A16-P03 受控内部 Owner；前置已满足。
- 单一问题：为内部资格命令提供默认关闭的冻结双路径 HTTP 合同。涉及 Solution API 与应用组合的可选路由参数；不变更 DB/ORM/Migration、业务权限或前端。
- 角色：PROJECT ProjectManager、GLOBAL DeploymentAdmin；Owner 在事务内再次核验，HTTP 先校验 Origin/Session/CSRF。验收：严格 JSON 两字段、强 If-Match/Idempotency-Key、历史同号 200 快照、错误码与安全响应、双 Scope 真实 PG。
- 风险：首次响应与当前根状态混淆；因此返回不可变资格事件 ID、固定版本 ID 与当次 ETag，页面后续必须另 GET 当前根，不把历史 200 当现时事实。

## 实施与验证

- 新增 `reference_eligibility.py` 双白名单路由：`/api/v1/projects/{project_id}/reference-solutions/{id}:set-eligibility`、`/api/v1/global/reference-solutions/{id}:set-eligibility`。请求为 `eligibility_state`、`reason`；成功 200 `data` + `trace_id`、`ETag`/`no-store`。禁止自由 Scope、额外 JSON 字段、弱 ETag、查询参数；服务结果投影必须与原请求/首次锁版本精确匹配。
- `create_app` 增加两个可选注入点；普通默认 app 对两路径仍 404。未在本任务修改 Windows 生产装配。
- 合同 4 passed/18 subtests：双路径/默认关闭、历史结果 ETag、不合法请求与错误码、错误投影拒绝。
- Win11 一次性隔离 PostgreSQL 18.6 真实 ASGI/Session：PROJECT 经理成功、实施成员 404、双决定与同号历史回执、强锁/Origin 拒绝，根两事件两审计；GLOBAL 管理员成功、无会话 401、双决定与同号历史回执、强锁/Origin 拒绝，根两事件两审计。两个验证脚本均退出 0，临时资源清理；上游真实来源夹具回归通过。
- 后端全量 `3405 passed, 3 skipped, 5197 subtests passed`。

## 边界与下一任务

没有 DB/Migration/依赖/冻结 API Breaking Change；关闭两个可选路由即可回退新 HTTP 面，已存在资格事件/审计保留。A16-P05 需挂入 Windows 显式 `--platform-write` 并做缺依赖失败关闭；A16-P06 页面/Edge。真人确认、正式 License/账户/HTTPS、Server2025、20 并发、Gate3/UAT/发行未验；Debian13 实机依用户要求跳过。

TraceLink：Gate2 API-04 → CR-SOL-014 → A16-P01～P03 → 本 P04 → P05/P06 → Gate3。
