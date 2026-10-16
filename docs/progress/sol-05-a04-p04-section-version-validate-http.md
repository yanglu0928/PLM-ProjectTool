# SOL-05-A04-P04：SectionVersion VALIDATE 可选 HTTP 合同

- 日期/版本：2026-10-12 / `0.1.0-dev.0`。承接冻结 API-04、A04-P02 报告合同及 A04-P03 真实 Owner；Trace 分离决策见 `DEC-20261012-1190`。
- 范围：新增冻结路径的 opt-in POST Router，默认应用 404。请求必须可信 Origin、当前 Session/CSRF、Idempotency-Key、合法 Project/Section/Version 路径、无 Query 与零字节正文；Owner 再核对 License/项目权限/来源并提交审计。200 仅表示报告已审计，不表示可评审。`data.observation_trace_id` 是首次观察；外层/响应头 Trace 是本次请求。
- 验证：HTTP 合同8通过/30子测试，覆盖六维响应、重放两个 Trace、默认关闭、身份/CSRF/参数/正文拒绝、Owner 错误码和跨项目结果失败关闭；后端全量3585通过/3跳过/5601子测试，开发 wheel 构建通过。
- 兼容/升级/回滚：无 Schema/Migration/依赖/冻结路径或角色变化，无现有响应 Breaking；移除可选 Router 参数/装配即可关闭，历史 Audit/收据保留。
- 限制/下一项：本项仅合同测试，未完成真实 ASGI/PG、Windows 组合、Edge 页面；Trace/Spec 仍 UNAVAILABLE，正式信任/Server2025/性能/Gate3/Pilot 未通过。下一项 `SOL-05-A04-P05` Windows 显式组合与真实 HTTP/PG 验收。
