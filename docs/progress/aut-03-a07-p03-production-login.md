# AUT-03-A07-P03：Windows 生产登录组合根

- 日期：2026-09-25；结果：Windows 11 合成环境 PASS；AUT-03-A07 跨平台/发行总体验收仍未关闭。
- 当前Phase：Phase 2 Platform Core；当前WBS：AUT-03-A07-P03。
- 输入基线：Gate 2 冻结 API-02 登录合同、CR-AUT-002/003；前置任务：AUT-03-A01～A06、P01～P02、PRJ-01-A02 PASS。
- 涉及模块：应用入口、Auth、Project、Platform、Audit；涉及实体：User、PasswordCredential、Session、LoginRateBucket、ProjectMember（读）、AuditEvent；API：仅按既有冻结合同可选开放 `POST /api/v1/auth/login`，普通 `create_app()` 仍 404；权限：匿名提交凭据不授予业务权限。
- 验收标准：缺可信 Origin/安全凭据/数据库连接/当前 Schema 任一项均拒绝启动；真实 PostgreSQL 用户密码、scrypt、跨进程限流、Session Cookie/CSRF、真实 ProjectMember 摘要、拒绝审计与成功审计端到端通过；应用退出释放连接；本机明文入口不得绑定非回环地址。
- 风险：Windows 11 合成环境证据不能替代 Server 2025 实际服务账户、HTTPS 反向代理、Debian 安全来源或 Release/UAT 验收。

Changed：新增 `create_production_login_app` 组合根，从当前 Windows 账户 Credential Manager 读取 URL；先校验可信 Origin，再建立并验证 PostgreSQL 连接及 `plm.alembic_version` 与打包迁移 head 一致，随后注入真实 Auth/Project/Audit 适配器。启动失败统一脱敏并释放引擎，正常关闭也释放引擎。新增 `serve_windows` 本机启动入口，只允许回环 IP 绑定、禁用代理头信任；非回环部署必须由本机 HTTPS 反向代理终止 TLS 后转发并保持 Host，不能直接暴露 Uvicorn 明文端口。

Files：生产组合根、Windows 启动入口、应用关闭钩子、合同测试、一次性 PostgreSQL 验证脚本及决策/进度/版本/状态记录。Migration：无；已有库必须先升级到本包 Alembic head。API：无新增路径或 Breaking Change，普通默认应用仍不挂登录。

Tests：Windows 11/Python 3.13 后端 316/316 PASS；一次性 PostgreSQL 18.6 数据库和角色、唯一合成 Credential Manager 条目、迁移、真实 User/ProjectMember、错误 Origin 403、错误密码 401、成功登录 200/Cookie/CSRF/项目摘要及 Session/Audit 记录 PASS；合成库/角色/凭据已删除，PostgreSQL 已停止；wheel 构建 PASS。Windows Server 2025、Debian 13 此项未验证。

Known Issues：生产真实凭据须由目标运行账户现场录入；HTTPS 代理和服务安装未交付，Session GET/续期/注销及业务路由仍未接线。Server 2025/Debian 13 和 Gate 3/UAT 未通过；POC-03 质量失败仍是独立阻断。

Next：在 Windows Server 2025 目标运行账户与真实 HTTPS 代理下复验；继续实现冻结 Session HTTP 与 License/管理 API 安全装配，并按 Release 计划补 Debian 来源及打包。
