# AUT-03-A03：登录用户名/密码证明与 Session 签发编排

- 日期：2026-09-25；结果：PASS（仅内部服务）；依据：冻结 API-02/User/Session 模型、AUT-03-A01～A02、DEC-20260925-008。
- Changed：登录先预约 PostgreSQL 限流，再规范化用户名并只查询活动 UserId。未知、停用或畸形用户名执行受控 scrypt 假验证；活动身份交既有 SessionService 在写事务中再次锁用户、验证真实密码并签发 Session/CSRF，成功 Audit 同事务。错误密码与未知/停用统一 `AUTH_INVALID_CREDENTIALS`，拒绝 Audit 不含原始用户名/密码；密码可变缓冲区在任何结果后清零。
- Files：`login_service.py`、`login_identity.py`、`missing_identity_verifier.py`、单元测试、`validation/aut-03-a03-login-service/verify.py`、决策/状态/版本说明。Migration：无。API：未挂公开路由。Permission：匿名登录证明，User 必须 ENABLED；SessionService 再次校验凭据版本。
- Tests：Windows 11/Python 3.13 后端 223/223 PASS；登录服务目标覆盖率 100%；PostgreSQL 18.6 临时库真实 scrypt 正确/错误密码、未知/停用用户、Session/CSRF 摘要及审计 PASS；wheel 构建 PASS。Windows Server 2025、Debian 13 本项未运行。
- Known Issues：假验证缩小而不保证完全消除耗时差异；真实客户端地址可信代理策略、限流过期桶清理、Cookie/CSRF、登录 HTTP、正式管理员初始创建仍未完成。当前登录路径仍 404，不能对用户提供登录。
- Next：`AUT-03-A04 登录 HTTP Cookie/CSRF 接线`；需先核对 Origin/Host、请求体上限、固定错误映射和 Session 传输属性。
