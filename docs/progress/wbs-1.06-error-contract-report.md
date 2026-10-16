# WBS 1.06 Error contract 验收记录

- 日期：2026-09-24
- 阶段：Phase 1 架构冻结与基础工程
- 状态：PASS
- 基线：Gate 2 冻结提交 `64cdf09` 的 API-01 公共错误协议；本任务未修改冻结基线。
- 追溯：WBS 1.06 → API-01 错误 Envelope/通用码/TraceId/权限存在性隐藏 → `DEC-20260924-065` → 平台错误目录与 FastAPI 异常处理 → Unit/Contract 测试。

## 交付与验证

平台层新增受控通用错误码和固定安全消息，FastAPI 统一处理已分类异常、请求校验、HTTP 异常和未分类异常。错误响应只包含 `error.code`、`error.message`、空 `error.details`、`trace_id`，响应头的 `X-Trace-Id` 与正文一致，并设置 `Cache-Control: no-store`。请求头只接受规范 UUID；无效值生成 UUIDv7。普通 403 与不存在资源返回相同 404，显式分类的 CSRF 403 保留。

Windows 11 / Python 3.13.15 环境运行后端全量测试 43/43 PASS。新增测试覆盖码表、未登记码拒绝、UUIDv7、409、403 隐藏与分类、404、400、422、405、500 脱敏和 TraceId 复用。原有健康、App Factory、Session 和 Migration 测试仍通过。公开路由仍只有 `/health/live`、`/health/ready`；业务表、业务 API、Migration 和客户数据外发均为 0。

## 兼容性、升级与剩余风险

当前是未发行的基础工程变更；部署无需数据库升级。新增 405 错误码 `REQUEST_METHOD_NOT_ALLOWED` 属兼容扩展，不改变冻结的已有错误码、状态或 `/api/v1` Envelope。Windows Server 2025 和 Debian 13 未在本任务验证，不据此宣称发行兼容性。

WBS 1.07 将补充服务端 JSON 脱敏日志，WBS 1.08 将装配全请求 TraceId 中间件；本任务的 TraceId 生成仅覆盖错误响应。模块业务错误码需在对应 WBS 登记后接入；健康端点继续使用冻结的最小响应，不套用业务错误 Envelope。
