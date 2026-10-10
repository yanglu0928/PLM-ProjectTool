# AUT-02-A01 Session 存储验收

- 日期：2026-09-24；结果：PASS；来源：Gate 2 冻结内容 `64cdf09` 的 DM-02/SC-01～03/API-02、`DEC-20260924-078`。
- 实现：`plm.auth_sessions` ORM 与 Alembic `20260924_0007`；Token/CSRF 只存摘要，关联 User 凭据版本历史，限制时间顺序、撤销原因及单调/不可替换字段。无公开路由或 Cookie 处理。
- 验收：Windows 11/Python 3.13 后端 110/110；PostgreSQL 18.6 临时独立库空库 up/down/re-up、已有 User/Credential 升级、ORM drift=0、摘要长度/唯一、凭据版本 FK、时间/撤销负例、含数据 downgrade 拒绝、备份恢复 PASS。测试发现并修复 CHECK 中 NULL 原因可能被放行的问题。入口：`validation/aut-02-a01-session-schema/verify.py`。
- 升级：先备份，执行 `upgrade head`；含 Session 数据不能普通回退。Windows Server 2025/Debian 13 本任务未验证。
- 遗留：Session 签发/校验/续期/撤销、Cookie/CSRF、真实用户状态/License/项目权限、登录限流尚未完成，数据库行本身不能证明当前认证有效。下一项为 `AUT-02-A02 Session 签发/校验/撤销内部服务`；Gate 3/UAT 未通过。
