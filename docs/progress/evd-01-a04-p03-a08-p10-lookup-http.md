# EVD-01-A04-P03-A08-P10：资格操作收据可选 HTTP

日期：2026-10-01；Phase 2 Platform Core；结果：`OPTIONAL_HTTP_PG_PASS / WINDOWS_COMPOSITION_OPEN`。

编码前检查：输入 CR-EVD-004/API 增量与 P09 内部服务，前置已通过。范围仅 Evidence 可选 Router、`create_app` 可选注入、HTTP 合同和隔离 PG 验证；无 ORM/Migration、角色、默认路由、依赖变化。验收双 Scope、严格同源 Origin/Session/CSRF、Key 仅在受限 JSON Body、成功最小响应、失败安全 Envelope、默认 404；真实平台组合另项。

新增只读 POST 项目/全局路径。请求体只接受 `operation_key`，请求体沿用限 8 KiB/重复 JSON key 拒绝的读取器；Key 格式在服务创建前校验。禁止查询参数，避免 Key 误入 URL。无新 `Idempotency-Key`/`If-Match`，因为端点不改变业务状态也不预留收据；必须提供可信 Origin、Cookie Session 和 CSRF。响应只返回 `UNCONFIRMED` 或 `COMPLETED`+EvidenceId/首次200，不返回 Key、理由、指纹或当前资格。Router 仅显式注入时存在，默认 404。

4项 HTTP 合同测试通过；Windows11/Python3.13 后端全量1,814项 PASS、3项既有环境跳过，开发 wheel SHA-256 `db6f5e596eebb1d1d42df6d9f1a54a9ceb13374c3aea761423566745505a6226`。全新临时 PostgreSQL18/pgvector 脚本在同源 TestClient+真实数据库上完成资格 POST→收据回查 `COMPLETED`、不存在 Key→`UNCONFIRMED`，并回归并发/许可/撤权矩阵退出0；临时实例清理。首次合同测试发现短 Key 在假 Service 下未被 Router 阻断，补 Router 入口校验后重测全绿，未降低约束。

兼容：冻结 V1 的非 Breaking 新增，原 API 不变；无 Migration。升级须保留 `0015` 幂等收据，正式环境还需显式组合和信任源。回滚不注入 Router，既有 Evidence/Audit/收据不删除。Windows 平台写模式尚未挂载；前端和真实浏览器/Gate3仍待，不能标最终可用。
