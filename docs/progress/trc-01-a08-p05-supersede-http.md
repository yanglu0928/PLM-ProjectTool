# TRC-01-A08-P05：TraceLink 可选 supersede HTTP

日期：2026-10-02；Phase 2；结果：**显式可选合同/真实 ASGI-PG18 PASS，默认与正式平台未挂载**。输入冻结 API-01/02、P02 原子替换、P04 同事务三字段解析、DEC-20261002-619；Gate 2 原冻结内容不追写。

新增精确 `POST /api/v1/projects/{project_id}/trace-links/{trace_link_id}:supersede` 可选 Router，Body 仅含 `source`/`target` 各自固定 `resource_type/resource_id/version_id` 与 `relation_type`。请求要求可信 Origin/Host、当前 Cookie Session 与 CSRF、强 If-Match、Idempotency-Key、单一 JSON Content-Type、严格 UTF-8/唯一键/8192 字节上限，禁止 query 和内部 Owner/Scope 字段。应用服务在同一事务再次证明许可、项目经理、旧边归属/版本、DOC-02 两端当前版本，随后原子替换。201 只返回新 `trace_link_id`，其强 ETag 为新边 `"v0"`；不泄露两端或内部 Scope。默认应用和正式 Windows 组合均不注入路由。

验证：合同 3 项覆盖默认 404、201/最小投影、新资源 ETag、Origin/Host/Session/CSRF/If-Match/Key、畸形/重复/多余字段、查询及安全错误映射。Windows 11 一次性 PostgreSQL 18 真 ASGI/真实 Session 合成许可验证 PM 201、同 Key 201 重放仅一新边/一旧终态/两 Audit/一收据，非经理 404、缺版本 428、过期许可 403、另 Key 冲突 409；原 Trace 创建/图/撤销与内部替换回归 PASS，临时资源清理。后端 **1900 运行、3 跳过、无失败**；开发 wheel SHA-256 `4442f5503acecfaf616147ed3772fe7c59e3789696d0e46c623162b4dccf1fc1`，不是最终可用安装包。

兼容/升级/回滚：仅新增可选 Trace Router 与应用工厂参数，无 Schema/Migration/新依赖或旧数据改写；不注入 Router 即关闭，不需升级数据，但装配前须既有 0029/0053。历史已替换关系不可反写。关系 Owner 身份/撤权、其他业务 Owner、正式目标账户信任、通用 Trace 列表/创建/图 HTTP、Server2025/Debian、性能/UAT/Gate 3 和可用发行包未完成。Next：`TRC-01-A08-P06` 核查关系 Owner/正式装配前置，若不满足继续关闭并转其他独立 Phase 2 工作。
