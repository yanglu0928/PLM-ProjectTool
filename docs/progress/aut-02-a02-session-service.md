# AUT-02-A02 Session 内部服务验收

- 日期：2026-09-24；结果：PASS；来源：Gate 2 冻结内容 `64cdf09` 的 DM-02/API-02、`DEC-20260924-079`。
- 实现：仅 Auth 内部签发、校验、撤销与 PostgreSQL 适配。签发需外部认证证明 Port 明确许可；数据库只存 32 字节 Token/CSRF 摘要。校验实时检查用户启用状态、当前凭据版本、撤销及期限；撤销需绑定 CSRF 并与 Audit 同事务。
- 验收：Windows 11/Python 3.13 后端 115/115、wheel 构建 PASS；PostgreSQL 18.6 临时独立库真实签发/摘要存储、错误 CSRF 拒绝、Audit 失败撤销回滚、正常撤销、用户停用失效 PASS。单元测试覆盖换密版本失效、空闲超时、拒权、不可靠随机源/时钟和敏感值 repr。
- Migration：无；沿用 `20260924_0007`，无升级操作。API：无新增公开路由；不代表真实登录可用。Windows Server 2025/Debian 13 本任务未验证。
- 遗留：生产认证证明/License 适配、Cookie/Origin/Host/限流、续期轮换、管理员全会话撤销、跨平台验证尚未完成；Gate 3/UAT 未通过。
