# AUT-03-A05：登录 SessionView 真实身份投影

- 日期：2026-09-25；结果：PASS（身份投影与项目 Port；非生产装配）；依据：冻结 API-02 SessionView、AUT-03-A04、DEC-20260925-010。
- Changed：登录 Router 要求显式 `SessionViewPort`，读取 User 显示名、部署角色和 Project-owned 授权项目摘要后才设置 Session Cookie；投影缺失/失败统一 503 且不发 Cookie。Auth SQL 适配器只读取 ENABLED User，不查询密码哈希，不代 Project 模块伪造项目事实。当前业务尚无 ProjectMember Schema/Repository，正式项目摘要提供者仍待对应模块实现。
- Files：Auth SessionView DTO/Port、SQL 身份投影、登录 Router/契约测试、临时 PostgreSQL 验证脚本及追溯文档。Migration：无；API：补齐冻结 SessionView 字段，不增加新端点。Permission：只显示当前 User 与 Project Port 给出的授权摘要；跨项目验收待 Project 模块。
- Tests：Windows 11/Python 3.13 后端 229/229 PASS；临时 PostgreSQL 18.6 验证真实 User 角色、显式 Project Port 和停用拒绝 PASS；HTTP 投影失败无 Cookie PASS；wheel 构建 PASS。Windows Server 2025、Debian 13 本项未运行。
- Known Issues：项目摘要的生产读取器尚不存在，不能使用空项目摘要替代实际权限；生产装配、初始管理员、Session 查询/续期/注销 HTTP 仍未完成。投影在 Session 签发后失败会留下未交付给客户端的短期服务端 Session，后续需补偿撤销或保持短 TTL 并清理。默认应用仍 404。
- Next：`AUT-03-A06 初始 DeploymentAdmin 受控创建与登录生产装配前置`；生产 Router 开放必须等待项目授权投影或经证据确认当前无项目成员数据。
