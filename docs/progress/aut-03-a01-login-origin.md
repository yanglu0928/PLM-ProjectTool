# AUT-03-A01：登录可信 Host/Origin 边界

- 日期：2026-09-25；结果：PASS（仅未挂路由的 HTTP 边界组件）；依据：冻结 API-01/API-02、CR-PLT-003、DEC-20260925-006。OWASP [CSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html) 建议校验来源与目标并对缺失来源采取拒绝策略。
- Changed：明确配置 1～16 个可信 Origin；非 loopback 仅允许 HTTPS，HTTP 仅允许 loopback；请求必须有且仅有一个 Host/Origin，两者严格匹配且存在于允许集合。拒绝 `null`、重复/畸形头、前缀混淆、路径/用户信息及不受信任转发 Host；错误仅返回固定 `AUTH_CSRF_INVALID`。无默认通配源。
- Files：`auth/api/login_origin_policy.py`、`auth/api/__init__.py`、单元测试、决策/状态/版本说明。Migration：无。API：未挂公开路由。Permission：匿名登录请求来源校验组件。
- Tests：Windows 11/Python 3.13 后端 211/211 PASS；目标组件覆盖率 96%；wheel 构建 PASS。HTTP 路由端到端测试未运行，因为登录路由尚未装配。
- Known Issues：反向代理必须保留配置的对外 Host 并显式管理可信源；本组件忽略转发头，不从请求动态学习可信域。登录限流、用户名/凭据编排、Cookie/CSRF 和真实部署配置仍未完成，不得声称登录可用。
- Next：`AUT-03-A02 登录限流策略与持久化边界`。
