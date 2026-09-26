# AUT-03-A08：当前 Session 查询 HTTP

- 日期：2026-09-25；结果：PASS（Windows 11 合成环境，冻结 GET 合同；不代表续期/注销或 Gate 3 PASS）。
- 当前Phase：Phase 2 Platform Core；当前WBS：AUT-03-A08。
- 输入基线：Gate 2 冻结 API-01/API-02 `AUTH_SESSION_GET`、Session/Cookie/CSRF 与 Project 授权摘要；前置 AUT-02-A02、AUT-03-A05/A07-P03、PRJ-01-A02 PASS。
- 涉及模块：Auth API、应用入口、Project 只读 Port；实体：Session、User、ProjectMember；API：新增可选挂载的 `GET /api/v1/auth/session`，无 Breaking Change；权限：有效 Server Session，License 无效时仍可读取当前身份，不由 GET 授予业务权限。
- 验收标准：只接受唯一、严格 64 位小写十六进制 `plm_session` Cookie；可信 Host，若带 Origin 则精确匹配；有效 Session 返回当前 User/Project 摘要与绝对/空闲到期时间，不返回 Token/CSRF 原值、不设置新 Cookie、不改变持久状态；无效/撤销/过期返回 401；普通默认应用仍 404。
- 风险：多标签 Session/CSRF 轮换、续期和注销尚未接线；GET 摘要不能代替后续每次业务请求重新授权。

Changed：新增 Auth 只读 Session Router、可信 Host 校验和严格 Cookie 提取；生产 Windows 组合根显式挂载，普通应用仍不挂载。`SessionService.validate` 与 `SqlAlchemySessionView` 分别校验当前凭据版本和实时 ProjectMember 状态；服务端错误脱敏。

Files：Auth Session API/来源策略、应用工厂/生产组合根、合同/单元测试、一次性 PostgreSQL 验证增强及决策/进度/版本/状态。Migration：无，升级无需数据操作。API：冻结 GET 路径按合同实现，无新路径或 Breaking Change。

Tests：Windows 11/Python 3.13 后端 320/320 PASS；一次性 PostgreSQL 18.6 + Windows Vault 真实登录后 Session GET、项目成员暂停后即时摘要清空、无 CSRF/新 Cookie、默认 404 PASS；合成数据库/角色/凭据已清理，PostgreSQL 已停止；wheel 构建 PASS。Windows Server 2025、Debian 13 本项未验证。

Known Issues：Session 续期和注销 HTTP、持久幂等、管理员/License/Secret 公开接线与最终程序包未完成；POC-03 质量失败及三平台发行约束仍阻断 Gate 3/UAT。

Next：按冻结合同实现 `POST /api/v1/auth/session:renew` 的 CSRF/Origin/Host 校验、Cookie/CSRF 原子轮换与真实 PostgreSQL 验证；注销另列工作项并满足 `Idempotency-Key`。
