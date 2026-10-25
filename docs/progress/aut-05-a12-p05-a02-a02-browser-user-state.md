# AUT-05-A12-P05-A02-A02 Windows11 隔离浏览器 User 启停

2026-09-28 / 0.1.0.dev0 / PASS（仅一次性合成用户与本机隔离环境）。

编码前检查：当前 Phase2，Gate2/Phase1 前置通过；冻结 API-02 `AUTH_USER_ENABLE/DISABLE`、既有 Windows11 后端状态链和 A01 初始 `"v0"` 前端修补为输入。DEC-426 先登记任务/风险/回滚/验收；只扩展验证夹具显式模式，不改生产 Auth 代码、实体、权限、API、数据库 Schema/Migration、依赖。

验证夹具新增 `--user-state-browser`：随机本机端口、独立临时 PostgreSQL 库/角色、合成 License 与密钥来源，显式装配现有 Windows write Factory；原只读模式保持原样。浏览器实际登录合成 Member 后确认用户管理不可读；用合成 Admin 登录，从列表进入目标详情见初始 `ENABLED/"v0"`。勾选核对后点停用，页面展示首次 `DISABLED/"v1"` 回执，并通过独立 GET 展示当前停用；再次勾选点启用，展示首次 `ENABLED/"v2"` 与独立 GET 当前启用。未操作真实账户或客户数据。

夹具 `VERIFY` exit0：目标 SQL 终态 `ENABLED/lock_version=2`，原 Member 测试会话至少一条撤销，UserState 不可变结果恰两条；2 项目、3 测试 Session、1 有效成员；自有服务、数据库/角色和 Vault 测试凭据清理均通过。旧 `--api-only` 回归 exit0：成员只读列表/详情、跨项目 404、管理员空项目及独立资源清理通过。前端 323 测试/typecheck/build 由 A01 同轮通过，未修改前端代码。

限制：正向 License/密钥均为合成材料，HTTP loopback 非正式 TLS/目标运行账户；没有验证生产安装、Windows Server 2025、Debian 13、20 并发/CR008、POC-03 质量或 Gate3。兼容当前 0049，无升级步骤。回滚可撤本测试显式模式，不涉及生产数据；浏览器写链证据将用于后续真实发行验收，而不能替代该验收。
