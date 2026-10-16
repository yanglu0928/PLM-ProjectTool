# AUT-05-A10-P04-A01 Windows11 用户创建 ASGI/PG 合同复验

2026-09-28 / 0.1.0.dev0 / `WINDOWS11_SYNTHETIC_PASS`（隔离PostgreSQL与ASGI Windows显式写组合；浏览器提交未运行）。

编码前检查：Phase2/Gate2已批准；输入冻结API-02 `AUTH_USER_CREATE`/CR-AUT-005及前端P01～P03，原后端Windows显式写验证链可复用。DEC-416先登记；仅扩`validation/aut-04-a09-p05-windows-user-create/verify.py`响应合同断言，不改生产实体/Schema/API/权限/依赖或Migration。风险/回滚为撤验证增量，无数据升级；验证完成后只读外部复查自有临时库。

证据：原Windows `platform-write` Factory在全新唯一临时PG/合成License/Vault中，当前Admin Session-CSRF创建201、同Key重放与异密码/用户名冲突、真实Scrypt新账户登录/HttpOnly Cookie/Session、普通角色创建拒绝、readonly POST405、默认/login404、缺正式信任失败关闭及构造故障安全拒绝，整脚本exit0。新增断言确认首次201固定八公开字段、ENABLED/NONE/credential1、强`"v1"`与Location、no-store、无Set-Cookie、UTC时间、无密码/Hash；重放响应数据及ETag/Location不变。七表快照验证拒绝/重放无额外写；原原子/HTTP/文件发布依赖链同轮通过。退出后外部只读查询`publication_%`临时数据库0，未提交运行日志或合成凭据。

限制：使用ASGI TestClient+真实PG，并非浏览器实际创建或对外TLS监听。Computer Use对新认证凭据的UI操作须交用户完成，故本项不声称浏览器提交通过。合成License不是正式发行信任；目标账户/Server2025/Debian、20并发性能、Gate3、安装升级和可用程序包仍待。下一独立任务可先推进不依赖UI新凭据提交的管理员只读管理界面，再安排安全的浏览器人工验收。
