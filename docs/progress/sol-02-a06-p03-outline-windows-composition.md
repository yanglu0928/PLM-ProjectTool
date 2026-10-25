# SOL-02-A06-P03 Windows 显式方案大纲详情读取组合

日期：2026-10-09。状态：Windows 11 隔离 ASGI/PostgreSQL 合成组合通过；正式发行未验。

## 编码前检查

- 当前 Phase/WBS：Phase 2 Platform Core / SOL-02-A06-P03。
- 输入基线：冻结 `SOL_OUTLINE_GET`、P01 内部读取 Owner、P02 可选 HTTP；Windows 显式 `--platform`/`--platform-write` 组合模式。
- 前置任务：P01/P02 的权限、合同及真实 PG/ASGI 已通过。
- 模块/实体/API/权限：Windows 组合根、SolutionOutline 详情读取；冻结 GET；有效 Session/License 与当前项目成员，缺任一信任依赖失败关闭。
- 验收标准：默认/登录专用不挂载；两种显式平台模式挂载；构造依赖缺失或路由构造异常拒启动并释放 runtime；Win11 隔离 PG/ASGI 真读取通过。
- 风险：测试用合成 License/Session，不代表正式公钥、服务账户 Vault/ACL/CA、Server2025 或发行已验。

## 变更与验证

新增 `create_windows_outline_read_router`，在只读和写平台组合中共享详情读取 Owner，并由 `create_production_login_app` 显式注入。登录专用模式仍无该路由；创建 POST 仍仅写模式挂载。无 Schema、Migration、依赖或冻结 API 变化；撤下显式注入可回滚，历史保留。

- 定向 Windows/生产模式合同：37 passed / 13 subtests，含读组合缺依赖、双模式构造异常释放 runtime、登录专用 404 与平台匿名 401。
- Windows 11 隔离 PG18.6/ASGI：真实 Session、项目授权与 GET 200/ETag、默认 404、跨项目/暂停成员/Origin/查询拒绝，通过；夹具清理临时数据库/进程。
- 后端全量回归：3374 passed / 3 skipped / 5046 subtests passed。

下一项：`SOL-02-A06-P04` 冻结列表 `SOL_OUTLINE_LIST` 的内部授权 Owner/keyset；独立处理游标、HTTP 与 Windows 组合。正式生产信任源、非空批准链、20 并发与发行仍待。
