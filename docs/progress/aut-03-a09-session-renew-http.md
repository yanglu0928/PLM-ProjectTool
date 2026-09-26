# AUT-03-A09：Session 续期 HTTP

- 日期：2026-09-25；结果：PASS（Windows 11 合成环境，冻结续期合同；不代表注销或 Gate 3 PASS）。
- 当前Phase：Phase 2 Platform Core；当前WBS：AUT-03-A09。
- 输入基线：Gate 2 冻结 API-01/API-02 `AUTH_SESSION_RENEW`、AUT-02-A03 原子轮换；前置 AUT-03-A08 与 Windows 登录组合根已完成。
- 涉及模块：Auth API、应用入口、Project 身份投影；实体：Session、User、ProjectMember、AuditEvent；API：可选挂载 `POST /api/v1/auth/session:renew`，无 Breaking Change；权限：有效 Server Session + CSRF + 精确 Origin/Host。
- 验收标准：唯一旧 Cookie 与 `X-CSRF-Token`，无请求正文；预检当前身份/项目投影，再在同一数据库事务中撤销旧 Session、生成新 Token/CSRF 摘要与 Audit。新 Token 只进入 HttpOnly Cookie，CSRF 原值仅在本次响应 DTO；旧 Token/CSRF 立即失效，绝对到期时刻不延长，普通默认应用仍 404。
- 风险：预检投影与轮换处于相邻独立事务，项目成员并发变化可使本次展示摘要短暂过时；后续业务请求必须逐操作重查授权。多标签持有旧 CSRF 的标签需重新登录/同步新凭据，不得静默使用旧令牌。

Changed：新增显式续期 Router，对 Origin/Host、Cookie、CSRF 及空正文严格校验；投影失败前不撤销旧 Session。调用已有 `SessionService.renew` 原子轮换并返回与登录一致的安全 Cookie/到期/CSRF 传输；Windows 生产组合根显式挂载，普通应用不挂载。

Files：Auth Session API、应用工厂/生产组合根、合同测试、一次性 PostgreSQL 验证增强及决策/进度/版本/状态。Migration：无，升级无需数据操作。API：冻结路径按合同实现，无 Breaking Change。

Tests：Windows 11/Python 3.13 后端 322/322 PASS；一次性 PostgreSQL 18.6 + Windows Vault 登录/查询/续期，原绝对到期同一时刻、旧 Token 401、新 Token 200、两条 Session 与 `SESSION_RENEWED` Audit PASS；合成数据库/角色/凭据已清理，PostgreSQL 已停止；wheel 构建 PASS。Windows Server 2025、Debian 13 本项未验证。

Known Issues：注销 HTTP 的持久 Idempotency-Key、管理员/License/Secret 公开接线和最终程序包未完成；POC-03 质量失败及三平台发行约束仍阻断 Gate 3/UAT。

Next：先实现符合冻结 API-01 的持久幂等基础，再接 `POST /api/v1/auth/logout`，并继续跨平台生产部署验证。
