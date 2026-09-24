# AUT-03-A06：初始 DeploymentAdmin 离线受控创建

- 日期：2026-09-25；结果：PASS（一次性本机初始化，未实际创建用户环境的管理员）；依据：冻结 User/Session 与 Audit 模型、DEC-20260925-011。密码下限参考 [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html) 的无 MFA 建议；scrypt 参数沿用已验证项目配置与 [OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)。PostgreSQL 18 [事务级 advisory lock](https://www.postgresql.org/docs/18/functions-admin.html#FUNCTIONS-ADVISORY-LOCKS) 用于串行化初态检查。
- Changed：新增 `python -m plm_assistant.entrypoints.bootstrap_admin` 本机交互入口，仅无任何 User 的数据库可执行一次。数据库 URL 和两次密码通过终端无回显输入，不接收命令行凭据；初始密码至少 15 个 Unicode 字符且不超过 1024 UTF-8 字节。专用事务锁之后再检查全表空状态，User、固定 scrypt 凭据与 `AUTH_INITIAL_ADMIN_CREATED` 脱敏 Audit 同事务写入；已有 User、审计失败或凭据无效均拒绝。密码可变缓冲区尽力清零。
- Files：Auth 初始化 Service/SQL Repository、离线 CLI、单元测试、临时 PostgreSQL 验证脚本及追溯文档。Migration：无；API：无公开端点；权限：仅空数据库本机初始化，不可用作管理员恢复/添加普通用户。
- Tests：Windows 11/Python 3.13 后端 233/233 PASS；初始化 Service 覆盖率 91%；临时 PostgreSQL 18.6 审计失败全回滚、并发单赢家、真实 scrypt 哈希验证、一次性拒绝 PASS；wheel 构建 PASS；CLI 参数/非交互拒绝 PASS。未在真实客户库创建管理员；Windows Server 2025、Debian 13 本项未运行。
- Known Issues：CLI 依赖部署者现场设置并保管真实密码，不能由 AI 代填；Python 的不可变字符串及密码派生实现可能持有临时副本，清零是尽力而非绝对保证。已有用户但无管理员的部署不能通过此入口恢复，需后续单独设计经身份核验的恢复流程。生产登录装配、Project 授权摘要及 Session HTTP 仍未完成。
- Next：`AUT-03-A07 登录生产依赖装配与端到端验证`，先核对真实 Project 授权摘要来源、受信任 Origin 与数据库配置；不能用测试替身开放默认路由。
