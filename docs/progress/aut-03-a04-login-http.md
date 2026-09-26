# AUT-03-A04：登录 HTTP Cookie/CSRF 接线

- 日期：2026-09-25；结果：PASS（可选 Router，生产默认未开放）；依据：冻结 API-01/API-02、AUT-03-A01～A03、DEC-20260925-009。
- Changed：`POST /api/v1/auth/login` 可选接入真实 LoginService 与显式可信 Origin；先检查 Host/Origin，再解析限长 JSON。登录成功仅把 Session Token 放 HttpOnly、SameSite=Lax、Path=/ Cookie，HTTPS 设置 Secure；CSRF 仅在本次响应返回且禁止缓存。错误密码统一 401，来源失败 403，畸形/过大正文 400，均用固定 Envelope 和 TraceId。默认 `create_app()` 保持 404。
- Tests：Windows 11/Python 3.13 全后端 227/227 PASS；Router 覆盖率 85%；HTTP 契约测试覆盖 opt-in、HTTPS/loopback Cookie、来源/正文拒绝、凭据失败无 Cookie；wheel 构建 PASS。Windows Server 2025、Debian 13 本项未运行。
- Known Issues：当前成功 DTO 仅有 user_id/期限/CSRF，冻结 SessionView 要求的部署角色和授权项目摘要尚未投影；这是尚未向默认应用开放的主要前置。仍无生产依赖装配、真实管理员初态、可信代理地址策略和 Session 查询/续期/注销 HTTP 接口，故不能宣称完整登录可用；Cookie 与 CSRF 值只在页面内存使用，不得写浏览器持久存储。接口 Port 的 PostgreSQL 实链已在 A03 验证，A04 本轮为 HTTP 契约测试。
- Next：`AUT-03-A05 登录生产装配与初始 DeploymentAdmin`；之后逐项实现 Session 查询/续期/注销及安全管理接口。
