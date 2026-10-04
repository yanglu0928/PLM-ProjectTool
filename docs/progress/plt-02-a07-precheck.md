# PLT-02-A07：Secret 管理 API 前置检查

- 日期：2026-09-25；状态：BLOCKED_BY_PREREQUISITES（仅本项公开接线，项目仍可继续）。输入：冻结 API-01/API-02、DM-02、PLT-02-A01～A06。
- 现状证据：`entrypoints/api.py` 只挂健康路由。Windows 11 本地 TestClient 检查 `/health/live`=200，`POST /api/v1/auth/login`=404，`GET /api/v1/admin/secrets`=404。内部 Session/CSRF/DeploymentAdmin、License Guard、Secret 读写服务存在，但未形成生产 HTTP 身份上下文与装配。
- 缺口：登录须 Origin/Host、限流、Session HttpOnly Cookie 与 CSRF；状态命令须 `If-Match`、持久化 Idempotency-Key、审计和许可；Secret 加密主密钥还需 Windows/Linux 受保护来源与独立恢复验证。不存在可声称生产可用的 Key Provider。仅挂路由会产生未受保护或不可正常使用的接口。
- 决策：依 DEC-20260925-005，先做 AUT-03 HTTP 登录/会话安全基础，再做正式 License/Key Provider 装配、幂等/版本协议，最后恢复 A07 路由实现与 API/权限/异常测试。此为时序调整，不删除冻结端点，也不把 A07 标为 PASS。Secret 值保持 write-only，未完成前不接受真实密钥。
- Changed：本项仅完成前置核查和依赖重排，无程序、Schema、Migration 或公开 API 变更。Tests：仅上述路由存在性检查；A07 功能/安全测试未运行。Known Issues：Gate 3/UAT 与 Release 仍有独立未闭合项。
